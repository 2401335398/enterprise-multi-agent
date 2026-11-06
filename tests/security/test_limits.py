"""
要求 5：请求限流 + 并发限制。

两个 limiter 都是进程内的 —— 演示固定单 worker，够用且不引新依赖。
测试直接打 limiter，再用 HTTP 验一遍接线（尤其是 finally 里的释放）。
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.security.limits import (
    ConcurrencyLimiter,
    RateLimiter,
    get_concurrency_limiter,
    get_rate_limiter,
    reset_limiters,
)

ALICE_KEY = "test-key-alice"


# ============================================================
# 1. RateLimiter 单元
# ============================================================

def test_rate_limiter_allows_up_to_limit(demo_mode):
    limiter = RateLimiter(limit_per_minute=3)

    for _ in range(3):
        limiter.check("alice")


def test_rate_limiter_raises_after_limit(demo_mode):
    limiter = RateLimiter(limit_per_minute=2)

    limiter.check("alice")
    limiter.check("alice")

    with pytest.raises(HTTPException) as exc_info:
        limiter.check("alice")

    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers


def test_rate_limiter_is_per_principal(demo_mode):
    """一个用户打满了，不能连累别人。"""

    limiter = RateLimiter(limit_per_minute=1)

    limiter.check("alice")

    with pytest.raises(HTTPException):
        limiter.check("alice")

    limiter.check("bob")   # 不受影响


def test_rate_limiter_disabled_when_limit_is_zero(demo_mode):
    limiter = RateLimiter(limit_per_minute=0)

    for _ in range(100):
        limiter.check("alice")


def test_rate_limiter_window_resets(demo_mode):
    import time

    limiter = RateLimiter(
        limit_per_minute=1, window_seconds=0.05
    )

    limiter.check("alice")

    with pytest.raises(HTTPException):
        limiter.check("alice")

    time.sleep(0.06)

    limiter.check("alice")   # 新窗口，恢复


# ============================================================
# 2. ConcurrencyLimiter 单元
# ============================================================

def test_concurrency_limiter_rejects_when_full(demo_mode):
    import asyncio

    async def scenario():
        limiter = ConcurrencyLimiter(max_concurrent=1)

        await limiter.acquire()

        with pytest.raises(HTTPException) as exc_info:
            await limiter.acquire()

        assert exc_info.value.status_code == 429

        await limiter.release()

        await limiter.acquire()   # 释放后又能进

    asyncio.run(scenario())


def test_concurrency_limiter_disabled_when_zero(demo_mode):
    import asyncio

    async def scenario():
        limiter = ConcurrencyLimiter(max_concurrent=0)

        for _ in range(50):
            await limiter.acquire()

    asyncio.run(scenario())


# ============================================================
# 3. dev 模式不限流（零回归）
# ============================================================

def test_dev_mode_never_rate_limits(dev_mode):
    limiter = get_rate_limiter()

    for _ in range(200):
        limiter.check("local")


# ============================================================
# 4. HTTP 接线
# ============================================================

def test_http_returns_429_when_rate_limited(
    demo_mode, asgi, stub_workflow, monkeypatch
):
    monkeypatch.setattr(
        settings, "demo_rate_limit_per_minute", 2
    )
    reset_limiters()

    headers = {"X-API-Key": ALICE_KEY}

    assert asgi.post_chat(
        {"message": "1"}, headers=headers
    ).status_code == 200
    assert asgi.post_chat(
        {"message": "2"}, headers=headers
    ).status_code == 200

    third = asgi.post_chat(
        {"message": "3"}, headers=headers
    )

    assert third.status_code == 429
    assert "Retry-After" in third.headers


def test_rate_limit_is_per_api_key(
    demo_mode, asgi, stub_workflow, monkeypatch
):
    monkeypatch.setattr(
        settings, "demo_rate_limit_per_minute", 1
    )
    reset_limiters()

    assert asgi.post_chat(
        {"message": "a"},
        headers={"X-API-Key": ALICE_KEY},
    ).status_code == 200

    # alice 已用尽，bob 不受影响
    assert asgi.post_chat(
        {"message": "b"},
        headers={"X-API-Key": "test-key-bob"},
    ).status_code == 200


def test_concurrency_slot_is_released_after_request(
    demo_mode, asgi, stub_workflow
):
    """
    如果在 finally 里漏了 release，这个计数器会一直涨，
    跑满 max_concurrent 次之后服务就永久 429 了 ——
    这是很容易漏、又很难在本地发现的一类 bug。
    """

    limiter = get_concurrency_limiter()

    assert limiter.active == 0

    for _ in range(5):
        response = asgi.post_chat(
            {"message": "hi"},
            headers={"X-API-Key": ALICE_KEY},
        )
        assert response.status_code == 200

    assert limiter.active == 0


def test_concurrency_slot_released_even_on_failure(
    demo_mode, asgi, monkeypatch
):
    """workflow 抛异常时也必须归还名额。"""

    from app.api import chat as chat_module

    async def boom(state, config=None):
        raise RuntimeError("workflow exploded")

    async def noop(**kwargs):
        return None

    async def empty_context(**kwargs):
        return ""

    async def no_recent_conversation(*args, **kwargs):
        return []

    monkeypatch.setattr(
        chat_module.agent_graph, "ainvoke", boom
    )
    monkeypatch.setattr(
        chat_module.memory_manager,
        "add_conversation",
        noop,
    )
    monkeypatch.setattr(
        chat_module, "build_memory_context", empty_context
    )
    monkeypatch.setattr(
        chat_module.memory_manager,
        "get_recent_conversation",
        no_recent_conversation,
    )
    monkeypatch.setattr(
        chat_module, "should_process_memory", lambda m: False
    )
    monkeypatch.setattr(
        chat_module, "get_langfuse_handler", lambda: None
    )

    limiter = get_concurrency_limiter()

    with pytest.raises(RuntimeError):
        asgi.post_chat(
            {"message": "hi"},
            headers={"X-API-Key": ALICE_KEY},
        )

    assert limiter.active == 0
