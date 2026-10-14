"""
会话命名空间化 —— 修掉会话越权。

原来的写法（app/api/chat.py）：

    session_id = request.session_id or str(uuid.uuid4())

客户端传什么就用什么。Memory 存储层只有 session_id 一列、没有 owner，
所以只要猜到（或拿到）别人的 session_id，就能读到那个会话的全部记忆。

这里的做法是不改数据库 schema，而是在**进入存储层之前**把 session_id
按 principal 加前缀：

    alice 传 "abc"        -> "alice:abc"
    bob   传 "alice:abc"  -> "bob:alice:abc"

于是跨用户读取在结构上不可能 —— 无论客户端传什么，
落到的命名空间一定属于调用者自己。

dev 模式只有 single principal，不需要隔离，因此**完全保持原行为**，
不加任何前缀。这样既有的评测脚本、清理逻辑、历史记忆都不受影响。
"""

from __future__ import annotations

import uuid

from app.core.config import settings
from app.security.auth import Principal

SESSION_SEPARATOR = ":"


def _prefix(principal: Principal) -> str:
    return f"{principal.name}{SESSION_SEPARATOR}"


def namespaced_session_id(
    principal: Principal,
    client_session_id: str | None,
) -> str:
    """
    把客户端提供的 session_id 映射到该 principal 独占的命名空间。

    幂等：已经带本 principal 前缀的值原样返回。

    这一条是必需的，不是优化 —— 响应里返回的是加前缀后的 id，
    客户端下一轮会把它传回来；若不做幂等判断，每轮都会再加一层前缀，
    等于每轮都开一个新会话，多轮记忆功能直接失效。
    """

    prefix = _prefix(principal)

    if client_session_id:

        if client_session_id.startswith(prefix):
            return client_session_id

        return f"{prefix}{client_session_id}"

    return f"{prefix}{uuid.uuid4()}"


def resolve_session_id(
    principal: Principal,
    client_session_id: str | None,
) -> str:
    """请求入口统一走这个函数。"""

    if not settings.is_demo:
        # dev：与改动前逐字一致
        return client_session_id or str(uuid.uuid4())

    return namespaced_session_id(principal, client_session_id)


def owns_session(
    principal: Principal,
    session_id: str | None,
) -> bool:
    """该 session_id 是否属于这个 principal。用于防御性断言与审计。"""

    if not session_id:
        return False

    return session_id.startswith(_prefix(principal))
