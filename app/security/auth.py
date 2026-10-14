"""
演示模式鉴权。

设计要点：

- dev 模式不做任何校验，返回固定 principal，现有调用方与评测套件完全无感。
- demo 模式必须带有效 key，否则 401。
- demo 模式但没配 key —— 拒绝启动。绝不能出现"以为开了演示模式、
  其实没有任何保护"的状态，那比不配还危险。
- key 比较用 secrets.compare_digest，避免时序侧信道。
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from fastapi import Header, HTTPException

from app.core.config import settings


@dataclass(frozen=True)
class Principal:
    """一个已认证的调用方。"""

    name: str


# dev 模式下所有人共享的身份
LOCAL_PRINCIPAL = Principal(name="local")


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

        mapping[key] = Principal(name=name)

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


async def require_principal(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> Principal:
    """
    FastAPI 依赖：解析并校验调用方身份。

    demo 模式支持两种传法：
      X-API-Key: <key>
      Authorization: Bearer <key>

    后者便于接 Cloudflare Access 的 Service Token 等场景。
    """

    if not settings.is_demo:
        return LOCAL_PRINCIPAL

    api_key = x_api_key

    if not api_key and authorization:

        scheme, _, token = authorization.partition(" ")

        if scheme.strip().lower() == "bearer":
            api_key = token.strip() or None

    principal = resolve_principal(api_key)

    if principal is None:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return principal
