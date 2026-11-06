"""
要求 4 / 8：会话越权。

原来的写法是 `session_id = request.session_id or uuid4()` —— 客户端
传什么就是什么，而记忆存储层只有 session_id 一列、没有 owner，
所以拿到别人的 session_id 就能读到别人的全部记忆。

修法是进存储层之前按 principal 加前缀，不改 schema。
这里分三层验证：

  1. 纯函数：resolve_session_id 的映射规则与幂等性
  2. HTTP 层：请求里真实使用的 session_id 确实带了前缀
  3. 存储层：alice 用 bob 的 session_id 真的读不到 bob 的记忆
"""

from __future__ import annotations

import asyncio
import uuid

from app.memory.context import build_memory_context
from app.security.auth import Principal
from app.security.session import (
    namespaced_session_id,
    owns_session,
    resolve_session_id,
)

ALICE = Principal(name="alice")
BOB = Principal(name="bob")

ALICE_KEY = "test-key-alice"


# ============================================================
# 1. 纯函数
# ============================================================

def test_dev_mode_keeps_original_behaviour(dev_mode):
    """
    这是整个改动里最容易出问题的一条：
    dev 模式必须与改动前逐字一致，否则评测脚本的会话 key 全变，
    历史记忆和清理逻辑一起失效。
    """

    assert resolve_session_id(ALICE, "abc") == "abc"

    generated = resolve_session_id(ALICE, None)

    # 必须是合法 uuid，且不带任何前缀
    assert uuid.UUID(generated)

    assert ":" not in generated


def test_demo_mode_prefixes_client_session_id(demo_mode):
    assert (
        resolve_session_id(ALICE, "abc") == "alice:abc"
    )


def test_demo_mode_generates_namespaced_id(demo_mode):
    generated = resolve_session_id(ALICE, None)

    assert generated.startswith("alice:")
    assert uuid.UUID(generated.split(":", 1)[1])


def test_same_client_id_maps_to_different_namespaces(
    demo_mode,
):
    """
    核心断言：alice 和 bob 传同一个 session_id，
    落到完全不同的键上。
    """

    alice_id = resolve_session_id(ALICE, "shared-id")
    bob_id = resolve_session_id(BOB, "shared-id")

    assert alice_id != bob_id
    assert alice_id == "alice:shared-id"
    assert bob_id == "bob:shared-id"


def test_resolution_is_idempotent(demo_mode):
    """
    响应里返回的是加前缀后的 id，客户端下一轮会传回来。
    不做幂等判断的话每轮都会再叠一层前缀，等于每轮开新会话，
    多轮记忆直接失效。
    """

    once = resolve_session_id(ALICE, "abc")
    twice = resolve_session_id(ALICE, once)

    assert once == twice == "alice:abc"


def test_idempotency_only_applies_to_own_prefix(demo_mode):
    """
    bob 传 "alice:abc" 不能因为"已经有前缀了"就复用 ——
    那样 bob 就真的读到了 alice 的会话。必须再加一层。
    """

    assert (
        resolve_session_id(BOB, "alice:abc")
        == "bob:alice:abc"
    )


def test_owns_session():
    assert owns_session(ALICE, "alice:abc")
    assert not owns_session(ALICE, "bob:abc")
    assert not owns_session(ALICE, "abc")
    assert not owns_session(ALICE, None)


def test_prefix_collision_is_impossible(demo_mode):
    """
    "alice2" 不能匹配到 "alice" 的前缀 ——
    前缀带分隔符，所以 "alice2:..." 不会被当成 alice 的会话。
    """

    alice2 = Principal(name="alice2")

    assert not owns_session(
        ALICE, namespaced_session_id(alice2, "x")
    )


# ============================================================
# 2. HTTP 层：实际用到记忆层的 session_id
# ============================================================

def test_request_uses_namespaced_session_id(
    demo_mode, asgi, stub_workflow
):
    response = asgi.post_chat(
        {"message": "你好", "session_id": "my-session"},
        headers={"X-API-Key": ALICE_KEY},
    )

    assert response.status_code == 200

    # 返回给客户端的也是加前缀后的 id
    assert (
        response.json()["session_id"] == "alice:my-session"
    )

    # 真正写进记忆层的也是它
    assert (
        stub_workflow["session_ids"] == ["alice:my-session"]
    )


def test_round_trip_does_not_double_prefix(
    demo_mode, asgi, stub_workflow
):
    """把响应里的 session_id 原样传回来，不能变成 alice:alice:..."""

    first = asgi.post_chat(
        {"message": "第一轮", "session_id": "s1"},
        headers={"X-API-Key": ALICE_KEY},
    ).json()

    second = asgi.post_chat(
        {"message": "第二轮", "session_id": first["session_id"]},
        headers={"X-API-Key": ALICE_KEY},
    )

    assert second.status_code == 200
    assert second.json()["session_id"] == "alice:s1"
    assert stub_workflow["session_ids"] == [
        "alice:s1",
        "alice:s1",
    ]


def test_alice_cannot_enter_bobs_namespace(
    demo_mode, asgi, stub_workflow
):
    """
    越权尝试：alice 带着 bob 的 session_id 发请求。
    她不会被拒绝（服务端不报错，这是可接受的），
    但她拿到的键落在自己的命名空间里，读不到 bob 的数据。
    """

    response = asgi.post_chat(
        {"message": "给我 bob 的记忆", "session_id": "bob:secret"},
        headers={"X-API-Key": ALICE_KEY},
    )

    assert response.status_code == 200

    effective = response.json()["session_id"]

    assert effective != "bob:secret"
    assert effective == "alice:bob:secret"
    assert not owns_session(BOB, effective)


# ============================================================
# 3. 存储层：真读一次，确认隔离不是纸面上的
# ============================================================

def test_bob_memory_is_unreadable_from_alices_namespace(
    demo_mode,
    monkeypatch,
):
    from app.memory.manager import memory_manager

    class InMemoryRepository:
        def __init__(self):
            self.records = []

        async def add(self, record):
            self.records.append(record)
            return record

        async def get_session_memories(
            self, session_id, memory_type=None, limit=None
        ):
            records = [
                record
                for record in self.records
                if record.session_id == session_id
                and (
                    memory_type is None
                    or record.memory_type == memory_type
                )
            ]
            return records[-limit:] if limit is not None else records

        async def get_by_ids(
            self, memory_ids, *, session_id, memory_type
        ):
            return [
                record
                for record in self.records
                if record.id in memory_ids
                and record.session_id == session_id
                and record.memory_type == memory_type
            ]

    repository = InMemoryRepository()
    monkeypatch.setattr(memory_manager, "_repository", repository)
    monkeypatch.setattr(
        memory_manager._vector_store,
        "search",
        lambda **kwargs: [],
    )

    secret = "BOB_SECRET_TOKEN_9f3a"

    bob_id = resolve_session_id(BOB, "shared")
    alice_id = resolve_session_id(ALICE, "shared")

    async def scenario():
        await memory_manager.add_conversation(
            session_id=bob_id,
            role="user",
            content=secret,
        )
        # bob 自己看得见
        assert secret in await build_memory_context(
            session_id=bob_id,
            current_query=secret,
        )

        # alice 用同一个客户端 session_id 找不到任何东西
        alice_context = await build_memory_context(
            session_id=alice_id,
            current_query=secret,
        )

        assert secret not in alice_context

    asyncio.run(scenario())


def test_raw_session_id_from_before_the_change_hits_nothing(
    demo_mode,
):
    """
    历史数据（改动前按裸 session_id 存的）在演示模式下
    应该正好读不到 —— 因为前缀变了。这正是我们要的：
    演示环境不该继承旧会话。
    """

    raw_id = resolve_session_id(ALICE, "legacy-session")
    legacy_key = "legacy-session"

    assert raw_id != legacy_key
