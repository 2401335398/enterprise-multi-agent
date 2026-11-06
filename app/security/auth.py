"""
鉴权：demo API Key + 用户 JWT。

设计要点：

- dev 模式不带凭据时不校验，返回固定 principal，现有调用方与评测套件完全无感。
- demo 模式必须带有效 API Key 或用户 JWT，否则 401。
- demo 模式但没配 API Key —— 拒绝启动。绝不能出现"以为开了演示模式、
  其实没有任何保护"的状态，那比不配还危险。
- key 比较用 secrets.compare_digest，避免时序侧信道。
- JWT 只携带身份与 token_version；权限留给第 3 步 RBAC。
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.exceptions import InvalidAccessToken
from app.auth.jwt import decode_access_token
from app.auth.repository import UserRepository
from app.core.config import settings
from app.db.session import get_db_session


@dataclass(frozen=True)
class Principal:
    """一个已认证的调用方。"""

    name: str

    # 用户 JWT 才有 user_id；demo API Key 和 dev local 为 None。
    user_id: str | None = None

    # local | api_key | jwt
    auth_method: str = "local"

    # 第 3 步多租户使用，本阶段不落库。
    tenant_id: str | None = None


# dev 模式下所有人共享的身份
LOCAL_PRINCIPAL = Principal(
    name="local",
    auth_method="local",
)

bearer_scheme = HTTPBearer(auto_error=False)


class DemoConfigError(RuntimeError):
    """演示模式配置不合法。"""


def parse_api_keys(raw: str) -> dict[str, Principal]:
    """
    解析 "alice:key1,bob:key2" -> {key1: Principal(alice), ...}

    principal 名不允许包含 ':'，否则会话命名空间 f"{name}:{sid}"
    会出现歧义（"a:b:c" 无法判断前缀是 a 还是 a:b）。
    """

    mapping: dict[str, Principal] = {}

    for chunk in (raw or "").split(","):

        chunk = chunk.strip()

        if not chunk:
            continue

        name, separator, key = chunk.partition(":")

        name = name.strip()
        key = key.strip()

        if not separator or not name or not key:
            raise DemoConfigError(
                "DEMO_API_KEYS 格式错误，应为 "
                "'name:key,name:key'，"
                f"实际收到: {chunk!r}"
            )

        if ":" in name:
            raise DemoConfigError(
                f"principal 名不能包含 ':'：{name!r}"
            )

        if key in mapping:
            # 不打印 key 的任何片段，哪怕是前几位
            raise DemoConfigError(
                f"API key 重复（属于 {mapping[key].name} "
                f"与 {name}）。"
            )

        mapping[key] = Principal(
            name=name,
            auth_method="api_key",
        )

    return mapping


# settings 被 monkeypatch（测试）后自动失效的缓存
_KEY_MAP_CACHE: tuple[str, dict[str, Principal]] | None = None


def get_api_key_map() -> dict[str, Principal]:
    global _KEY_MAP_CACHE

    raw = settings.demo_api_keys

    if _KEY_MAP_CACHE is None or _KEY_MAP_CACHE[0] != raw:
        _KEY_MAP_CACHE = (raw, parse_api_keys(raw))

    return _KEY_MAP_CACHE[1]


def validate_demo_config() -> None:
    """
    启动闸门。演示模式必须配好 key，否则直接拒绝启动。
    """

    if not settings.is_demo:
        return

    if not get_api_key_map():
        raise DemoConfigError(
            "APP_MODE=demo 但 DEMO_API_KEYS 为空。"
            "演示模式不允许无鉴权启动。"
            "请在 .env 里配置 DEMO_API_KEYS=\"alice:key1,bob:key2\"，"
            "或改回 APP_MODE=dev。"
        )


def resolve_principal(api_key: str | None) -> Principal | None:
    """把请求带来的 key 解析成 principal，认不出来返回 None。"""

    if not api_key:
        return None

    for known_key, principal in get_api_key_map().items():

        # 恒时比较：不能用 == 或 dict 直接查，会泄露前缀匹配长度
        if secrets.compare_digest(api_key, known_key):
            return principal

    return None


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _looks_like_jwt(token: str) -> bool:
    return token.count(".") == 2


async def _principal_from_access_token(
    token: str,
    db: AsyncSession,
) -> Principal:
    try:
        payload = decode_access_token(token)
    except InvalidAccessToken as exc:
        raise _unauthorized(str(exc)) from exc

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise _unauthorized("Invalid access token.")

    try:
        user_id = uuid.UUID(subject)
        token_version = int(payload.get("ver"))
    except (TypeError, ValueError, AttributeError):
        raise _unauthorized("Invalid access token.") from None

    user = await UserRepository(db).get_by_id(user_id)

    if user is None:
        raise _unauthorized("Invalid access token.")

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Account is disabled.",
        )

    if token_version != user.token_version:
        raise _unauthorized("Access token has been revoked.")

    return Principal(
        name=f"user:{user.id}",
        user_id=str(user.id),
        auth_method="jwt",
    )


async def require_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    x_api_key: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> Principal:
    """
    FastAPI 依赖：解析并校验调用方身份。

    支持三种凭据，优先级如下：

      1. X-API-Key: <key>                 （仅 demo）
      2. Authorization: Bearer <JWT>      （用户登录）
      3. Authorization: Bearer <api-key>  （仅 demo，兼容旧用法）

    dev 模式没有凭据时仍返回 LOCAL_PRINCIPAL，保持原有零鉴权行为。
    demo 模式没有任何有效凭据时 401。
    """

    if x_api_key:

        if settings.is_demo:

            principal = resolve_principal(x_api_key)

            if principal is None:
                raise _unauthorized(
                    "Missing or invalid API key."
                )

            return principal

        # dev 模式忽略 X-API-Key，与改动前一致。

    if credentials is not None:

        token = credentials.credentials

        if _looks_like_jwt(token):
            return await _principal_from_access_token(
                token,
                db,
            )

        if settings.is_demo:

            principal = resolve_principal(token)

            if principal is None:
                raise _unauthorized(
                    "Missing or invalid API key."
                )

            return principal

        # dev 模式下非 JWT 的 Bearer 值仍然被忽略。

    if settings.is_demo:
        raise _unauthorized("Missing or invalid API key.")

    return LOCAL_PRINCIPAL
