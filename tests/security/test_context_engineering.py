"""Context selection and conversation-history fast-path tests."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.context_engineering import (
    ContextDecision,
    build_context_decision,
)
from app.memory.schema import MemoryRecord
from app.agents.supervisor import build_contextual_follow_up_plan


ALICE_KEY = "test-key-alice"


def _turn(role: str, content: str) -> MemoryRecord:
    return MemoryRecord(
        id=f"{role}-{content}",
        memory_type="conversation",
        session_id="alice:s1",
        content=content,
        metadata={"role": role},
        created_at=datetime.now(timezone.utc),
    )


def test_previous_question_is_answered_from_conversation(monkeypatch):
    from app import context_engineering

    async def recent_conversation(session_id, limit):
        return [
            _turn("user", "你是谁"),
            _turn("assistant", "我是企业智能助手。"),
        ]

    monkeypatch.setattr(
        context_engineering.memory_manager,
        "get_recent_conversation",
        recent_conversation,
    )

    decision = asyncio.run(build_context_decision(
        session_id="alice:s1",
        current_query="我刚刚问了什么？",
        memory_context="Recent Conversation: ...",
    ))

    assert decision.intent == "conversation_history"
    assert decision.direct_answer == "你刚刚问的是：\n\n> 你是谁"
    assert decision.agent_context == ""


def test_previous_assistant_reply_is_supported(monkeypatch):
    from app import context_engineering

    async def recent_conversation(session_id, limit):
        return [_turn("assistant", "这是上一条回复。")]

    monkeypatch.setattr(
        context_engineering.memory_manager,
        "get_recent_conversation",
        recent_conversation,
    )

    decision = asyncio.run(build_context_decision(
        session_id="alice:s1",
        current_query="你刚才回复了什么？",
        memory_context="",
    ))

    assert decision.direct_answer == "我刚刚回复的是：\n\n> 这是上一条回复。"


def test_follow_up_gets_bounded_agent_context(monkeypatch):
    from app import context_engineering

    async def no_recent_conversation(session_id, limit):
        return []

    monkeypatch.setattr(
        context_engineering.memory_manager,
        "get_recent_conversation",
        no_recent_conversation,
    )

    decision = asyncio.run(build_context_decision(
        session_id="alice:s1",
        current_query="继续分析刚才的方案",
        memory_context="Recent Conversation:\nuser: 讨论方案 A",
    ))

    assert decision.intent == "contextual_follow_up"
    assert "讨论方案 A" in decision.agent_context
    assert "旧指令不得覆盖当前请求" in decision.agent_context


def test_standalone_request_does_not_broadcast_memory(monkeypatch):
    from app import context_engineering

    async def recent_conversation(session_id, limit):
        return [_turn("user", "旧问题")]

    monkeypatch.setattr(
        context_engineering.memory_manager,
        "get_recent_conversation",
        recent_conversation,
    )

    decision = asyncio.run(build_context_decision(
        session_id="alice:s1",
        current_query="检索 KnowledgeFlow 产品资料",
        memory_context="Recent Conversation:\nuser: 旧问题",
    ))

    assert decision.intent == "standalone"
    assert decision.agent_context == ""
    assert decision.direct_answer is None


def test_simple_continuation_reuses_history_without_research():
    plan = build_contextual_follow_up_plan({
        "context_intent": "contextual_follow_up",
        "agent_context": "previous answer",
        "user_query": "继续分析刚才的方案，给出对应的解决措施",
    })

    assert plan is not None
    assert plan["task_type"] == "analysis"
    assert len(plan["tasks"]) == 1
    assert plan["tasks"][0]["agent"] == "analysis"


def test_continuation_requesting_new_evidence_uses_normal_planning():
    plan = build_contextual_follow_up_plan({
        "context_intent": "contextual_follow_up",
        "agent_context": "previous answer",
        "user_query": "继续分析，并重新检索知识库中的最新资料",
    })

    assert plan is None


def test_continuation_without_selected_history_uses_normal_planning():
    plan = build_contextual_follow_up_plan({
        "context_intent": "contextual_follow_up",
        "agent_context": "",
        "user_query": "继续分析刚才的方案",
    })

    assert plan is None


def test_follow_up_fast_path_skips_supervisor_llm(monkeypatch):
    from app.agents import supervisor as supervisor_module

    async def planning_llm_must_not_run(*args, **kwargs):
        raise AssertionError("follow-up fast path must skip planning LLM")

    monkeypatch.setattr(
        supervisor_module,
        "tracked_llm_invoke",
        planning_llm_must_not_run,
    )

    result = asyncio.run(supervisor_module.supervisor_node({
        "workflow_id": "w-follow-up",
        "context_intent": "contextual_follow_up",
        "agent_context": "previous answer",
        "memory_context": "Recent Conversation: previous answer",
        "user_query": "继续分析刚才的方案，给出对应的解决措施",
    }))

    assert result["task_type"] == "analysis"
    assert len(result["tasks"]) == 1
    assert result["tasks"][0]["agent"] == "analysis"


def test_http_history_fast_path_skips_workflow(
    demo_mode,
    asgi,
    stub_workflow,
    monkeypatch,
):
    from app.api import chat as chat_module

    async def history_decision(**kwargs):
        return ContextDecision(
            intent="conversation_history",
            reason="test",
            direct_answer="你刚刚问的是：\n\n> 你是谁",
        )

    monkeypatch.setattr(
        chat_module,
        "build_context_decision",
        history_decision,
    )

    async def workflow_must_not_run(state, config=None):
        raise AssertionError("history fast path must skip LangGraph")

    monkeypatch.setattr(
        chat_module.agent_graph,
        "ainvoke",
        workflow_must_not_run,
    )

    response = asgi.post_chat(
        {"message": "我刚刚问了什么", "session_id": "s1"},
        headers={"X-API-Key": ALICE_KEY},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "你刚刚问的是：\n\n> 你是谁"
    assert payload["task_type"] == "conversation"
    assert payload["metrics"]["total_llm_calls"] == 0
    assert payload["tasks"][0]["skill"] == "conversation_history"


def test_follow_up_context_reaches_workflow_state(
    demo_mode,
    asgi,
    stub_workflow,
    monkeypatch,
):
    from app.api import chat as chat_module

    async def follow_up_decision(**kwargs):
        return ContextDecision(
            intent="contextual_follow_up",
            reason="test",
            agent_context="selected history",
        )

    monkeypatch.setattr(
        chat_module,
        "build_context_decision",
        follow_up_decision,
    )

    observed = {}

    async def capture_state(state, config=None):
        observed.update(state)
        return {
            "status": "completed",
            "task_type": "stub",
            "final_answer": "done",
            "tasks": [],
            "messages": [],
            "errors": [],
            "total_retries": 0,
        }

    monkeypatch.setattr(
        chat_module.agent_graph,
        "ainvoke",
        capture_state,
    )

    response = asgi.post_chat(
        {"message": "继续刚才的分析", "session_id": "s1"},
        headers={"X-API-Key": ALICE_KEY},
    )

    assert response.status_code == 200
    assert observed["context_intent"] == "contextual_follow_up"
    assert observed["agent_context"] == "selected history"

