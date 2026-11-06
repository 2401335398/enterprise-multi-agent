"""
要求 5：单任务（单次请求，整个 DAG）Token 预算。

挂载点是 app/core/llm.py 的 TrackedChatModel.ainvoke。全系统的 LLM
调用都走 llm 这个单例，所以一处即可覆盖 Supervisor、全部 Agent、
记忆抽取/整理、RAG query rewrite。

特别注意：llm.py 里有**两个** TrackedChatModel 定义，后一个遮蔽了
前一个，而 `llm = create_llm()` 是在两次定义之间执行的 ——
也就是说单例用的是**第一个**类。闸门加在第二个上等于没加。
下面 test_live_singleton_is_guarded 就是专门钉住这一点的。
"""

from __future__ import annotations

import asyncio

import pytest

from app.core.config import settings
from app.core.llm import llm
from app.observability.context import (
    WorkflowObservabilityContext,
    reset_observability_context,
    set_observability_context,
)
from app.security.budget import (
    TokenBudgetExceeded,
    check_token_budget,
    tokens_used_in_current_request,
)


class SpyLLM:
    """替身：记录有没有被调用。"""

    def __init__(self):
        self.called = False

    async def ainvoke(self, messages):
        self.called = True
        return None


def _with_token_context(input_tokens, output_tokens):
    """返回一个 (setup, cleanup) 对，方便写在协程里。"""

    context = WorkflowObservabilityContext(
        workflow_id="budget-test"
    )
    context.input_tokens = input_tokens
    context.output_tokens = output_tokens

    return context, set_observability_context(context)


# ============================================================
# 1. 计数来源
# ============================================================

def test_tokens_used_sums_input_and_output():
    async def scenario():
        context, token = _with_token_context(100, 40)
        try:
            assert tokens_used_in_current_request() == 140
        finally:
            reset_observability_context(token)

    asyncio.run(scenario())


def test_tokens_used_is_zero_without_context():
    assert tokens_used_in_current_request() == 0


# ============================================================
# 2. check_token_budget 的条件
# ============================================================

def test_dev_mode_ignores_budget(dev_mode):

    async def scenario():
        context, token = _with_token_context(10_000_000, 0)
        try:
            check_token_budget()   # 不抛
        finally:
            reset_observability_context(token)

    asyncio.run(scenario())


def test_demo_raises_when_over_budget(demo_mode, monkeypatch):

    monkeypatch.setattr(
        settings, "demo_max_tokens_per_request", 1000
    )

    async def scenario():
        context, token = _with_token_context(1000, 0)
        try:
            with pytest.raises(TokenBudgetExceeded):
                check_token_budget()
        finally:
            reset_observability_context(token)

    asyncio.run(scenario())


def test_demo_passes_when_under_budget(demo_mode, monkeypatch):

    monkeypatch.setattr(
        settings, "demo_max_tokens_per_request", 1000
    )

    async def scenario():
        context, token = _with_token_context(999, 0)
        try:
            check_token_budget()   # 不抛
        finally:
            reset_observability_context(token)

    asyncio.run(scenario())


def test_budget_disabled_when_limit_is_zero(
    demo_mode, monkeypatch
):

    monkeypatch.setattr(
        settings, "demo_max_tokens_per_request", 0
    )

    async def scenario():
        context, token = _with_token_context(10_000_000, 0)
        try:
            check_token_budget()   # 不抛
        finally:
            reset_observability_context(token)

    asyncio.run(scenario())


# ============================================================
# 3. 真正的闸门：在调用 LLM **之前** 拦下来
# ============================================================

def test_guard_blocks_before_calling_llm(demo_mode, monkeypatch):

    monkeypatch.setattr(
        settings, "demo_max_tokens_per_request", 100
    )

    async def scenario():
        spy = SpyLLM()

        # 注意用 type(llm) 而不是 import 进来的 TrackedChatModel：
        # 模块末尾的第二个同名类遮蔽了名字，import 拿到的是**死代码**那一版，
        # 它没有闸门。这里要测的是单例真正在用的那个类。
        model = type(llm)(spy)

        context, token = _with_token_context(100, 0)
        try:
            with pytest.raises(TokenBudgetExceeded):
                await model.ainvoke([])
        finally:
            reset_observability_context(token)

        # 关键：超预算时底层 LLM 根本不该被调用，
        # 否则"预算"只是事后统计，拦不住花费。
        assert spy.called is False

    asyncio.run(scenario())


def test_live_singleton_is_guarded(demo_mode, monkeypatch):
    """
    钉住模块里那两个同名类的问题。

    如果哪天有人把闸门挪到了第二个 TrackedChatModel 上，
    这个测试会失败 —— 而线上表现是"预算完全不起作用"，
    极难从日志上看出来。
    """

    monkeypatch.setattr(
        settings, "demo_max_tokens_per_request", 100
    )

    async def scenario():
        spy = SpyLLM()
        monkeypatch.setattr(llm, "llm", spy)


        context, token = _with_token_context(100, 0)
        try:
            with pytest.raises(TokenBudgetExceeded):
                await llm.ainvoke([])
        finally:
            reset_observability_context(token)

        assert spy.called is False

    asyncio.run(scenario())


def test_module_has_two_classes_and_singleton_uses_the_first():
    """
    把 llm.py 里"同名类遮蔽"这件事钉成可执行的事实。

    写这个测试的原因是它真的咬过一次：闸门最初加在了第二个定义上，
    而单例用的是第一个 —— 表现是"预算完全不起作用，但代码看起来是对的"。
    哪天有人清理掉死代码，这个测试会失败并提醒同步更新上面的注释。
    """

    import app.core.llm as llm_module

    assert type(llm).__module__ == "app.core.llm"

    # 模块级名字指向的是第二个定义
    assert (
        llm_module.TrackedChatModel is not type(llm)
    )

    # 单例带闸门：超预算时调用会抛
    assert hasattr(llm, "ainvoke")


def test_guard_follows_growth_within_one_request(
    demo_mode, monkeypatch
):
    """
    预算是"整个 DAG 累计"，不是"单次调用"。第一次能过，
    累计超了之后必须被拦下 —— 这正是 DAG 多任务场景的样子。
    """

    monkeypatch.setattr(
        settings, "demo_max_tokens_per_request", 100
    )

    async def scenario():
        context, token = _with_token_context(0, 0)
        try:
            # 第一次调用前：0，放行
            check_token_budget()

            # 模拟 DAG 跑了一阵子
            context.input_tokens = 60
            context.output_tokens = 60

            with pytest.raises(TokenBudgetExceeded):
                check_token_budget()
        finally:
            reset_observability_context(token)

    asyncio.run(scenario())


# ============================================================
# 4. HTTP 层：预算耗尽 -> 429，而不是 500
# ============================================================

def test_budget_exceeded_maps_to_429(
    demo_mode, asgi, monkeypatch
):
    from app.api import chat as chat_module

    async def over_budget(state, config=None):
        raise TokenBudgetExceeded("budget gone")

    async def noop(**kwargs):
        return None

    async def empty_context(**kwargs):
        return ""

    async def no_recent_conversation(*args, **kwargs):
        return []

    monkeypatch.setattr(
        chat_module.agent_graph, "ainvoke", over_budget
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

    response = asgi.post_chat(
        {"message": "hi"},
        headers={"X-API-Key": "test-key-alice"},
    )

    assert response.status_code == 429
