# app/api/chat.py

from __future__ import annotations

import asyncio
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import settings

from app.graph.workflow import agent_graph

from app.security.auth import (
    Principal,
    require_principal,
)
from app.security.limits import (
    get_concurrency_limiter,
    get_rate_limiter,
)
from app.security.session import resolve_session_id
from app.security.budget import TokenBudgetExceeded

from app.memory.manager import memory_manager
from app.memory.context import build_memory_context
from app.memory.extractor import extract_semantic_memory
from app.memory.router import should_process_memory

from app.context_engineering import (
    build_context_decision,
    build_direct_workflow_result,
)

from app.observability.context import (
    WorkflowObservabilityContext,
    reset_observability_context,
    set_observability_context,
)
from app.observability.cost import estimate_cost
from app.observability.langfuse_integration import (
    get_langfuse_handler,
)
from app.observability.tracer import tracer


router = APIRouter()


# ============================================================
# Request / Response Schema
# ============================================================

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class RuntimeMetricsResponse(BaseModel):
    workflow_id: str

    latency_ms: float

    total_retries: int

    total_llm_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    total_tool_calls: int = 0

    memory_extractor_calls: int = 0
    memory_consolidator_calls: int = 0
    memory_fast_path_skips: int = 0

    estimated_cost_usd: float = 0.0


class ChatResponse(BaseModel):
    session_id: str

    answer: str

    task_type: str

    tasks: list[dict]

    trace: list[str]

    structured_trace: list[dict]

    errors: list[str]

    metrics: RuntimeMetricsResponse


# ============================================================
# Chat API
# ============================================================

@router.post(
    "/chat",
    response_model=ChatResponse,
)
async def chat(
    request: ChatRequest,
    principal: Principal = Depends(
        require_principal
    ),
):
    """
    演示模式外壳：鉴权 -> 限流 -> 并发闸 -> 请求级超时。

    真正的业务逻辑原封不动在 _chat_impl 里，
    所以规划 / DAG 调度 / RAG / Memory 一行都没改。
    """

    # ---- 服务端限流（按 principal，超限 429）----
    get_rate_limiter().check(
        principal.name
    )

    # ---- 全局并发闸（不排队，满了直接 429）----
    await (
        get_concurrency_limiter()
        .acquire()
    )

    try:

        if settings.is_demo:

            try:

                async with asyncio.timeout(
                    settings
                    .demo_request_timeout_seconds
                ):

                    return await _chat_impl(
                        request,
                        principal,
                    )

            except TimeoutError:

                raise HTTPException(
                    status_code=504,
                    detail=(
                        "Request timed out."
                    ),
                ) from None

            except TokenBudgetExceeded as exc:

                raise HTTPException(
                    status_code=429,
                    detail=str(exc),
                ) from None

        return await _chat_impl(
            request,
            principal,
        )

    finally:

        await (
            get_concurrency_limiter()
            .release()
        )


async def _chat_impl(
    request: ChatRequest,
    principal: Principal,
):
    print("\n========== CHAT REQUEST RECEIVED ==========")
    print("message:", request.message)
    print("session_id:", request.session_id)
    print("===========================================\n")

    # ========================================================
    # 1. Workflow / Session Identity
    # ========================================================

    workflow_id = str(
        uuid.uuid4()
    )

    # 演示模式下把 session 收敛到 principal 的命名空间里，
    # 跨用户读会话在结构上就不可能（dev 模式与原逻辑逐字一致）。
    session_id = resolve_session_id(
        principal,
        request.session_id,
    )

    workflow_started_at = (
        time.perf_counter()
    )

    # ========================================================
    # 2. Local Observability Context
    # ========================================================

    obs_context = (
        WorkflowObservabilityContext(
            workflow_id=workflow_id
        )
    )

    obs_token = (
        set_observability_context(
            obs_context
        )
    )

    try:

        # ====================================================
        # 3. Workflow Start Trace
        # ====================================================

        tracer.record(
            event_type="workflow_started",
            workflow_id=workflow_id,
            success=True,
            metadata={
                "session_id":
                    session_id,
            },
        )

        # ====================================================
        # 4. Historical Memory Retrieval
        # ====================================================

        memory_context = (
            await build_memory_context(
                session_id=session_id,
                current_query=(
                    request.message
                ),
            )
        )

        # Context policy reads the conversation before the current message is
        # stored, so "what did I just ask" resolves to the previous turn.
        context_decision = await build_context_decision(
            session_id=session_id,
            current_query=request.message,
            memory_context=memory_context,
        )

        tracer.record(
            event_type="context_selected",
            workflow_id=workflow_id,
            success=True,
            metadata={
                "intent": context_decision.intent,
                "reason": context_decision.reason,
                "direct_answer": context_decision.uses_direct_answer,
                "agent_context_chars": len(context_decision.agent_context),
            },
        )

        # ====================================================
        # 5. Store Current User Message
        # ====================================================

        await memory_manager.add_conversation(
            session_id=session_id,
            role="user",
            content=request.message,
        )

        # ====================================================
        # 6. Semantic Memory Fast Path
        # ====================================================

        semantic_memory = None
        consolidation_result = None

        should_process = (
            should_process_memory(
                request.message
            )
        )

        if should_process:

            # ------------------------------------------------
            # Memory Extractor
            # ------------------------------------------------

            obs_context.memory_extractor_calls += 1

            semantic_memory = (
                await extract_semantic_memory(
                    request.message
                )
            )

            # ------------------------------------------------
            # Memory Consolidation
            # ------------------------------------------------

            if semantic_memory:

                consolidation_result = (
                    await memory_manager
                    .consolidate_semantic_memory(
                        session_id=session_id,
                        candidate_memory=(
                            semantic_memory
                        ),
                    )
                )

                # --------------------------------------------
                # If consolidation itself did not take the
                # deterministic fast path, count the LLM call.
                # --------------------------------------------

                if not consolidation_result.get(
                    "fast_path",
                    False,
                ):

                    obs_context.memory_consolidator_calls += 1

                tracer.record(
                    event_type="memory_semantic",
                    workflow_id=workflow_id,
                    success=True,
                    metadata={
                        "candidate":
                            semantic_memory,
                        "decision":
                            consolidation_result,
                    },
                )

                print(
                    "\n"
                    "===== MEMORY PIPELINE ====="
                )
                print(
                    "candidate:",
                    semantic_memory
                )
                print(
                    "decision:",
                    consolidation_result
                )
                print(
                    "===========================\n"
                )

        else:

            # ------------------------------------------------
            # Deterministic Memory Fast Path
            # ------------------------------------------------

            obs_context.memory_fast_path_skips += 1

            tracer.record(
                event_type="memory_fast_path",
                workflow_id=workflow_id,
                success=True,
                metadata={
                    "skipped":
                        True,
                },
            )

            print(
                "[MEMORY] Fast path skipped "
                "semantic processing."
            )

        # ====================================================
        # 7. Build Initial LangGraph State
        # ====================================================

        initial_state = {

            "workflow_id":
                workflow_id,

            "workflow_started_at":
                workflow_started_at,

            "workflow_completed_at":
                None,

            "workflow_latency_ms":
                None,

            "session_id":
                session_id,

            "memory_context":
                memory_context,

            "context_intent":
                context_decision.intent,

            "agent_context":
                context_decision.agent_context,

            "total_retries":
                0,

            "total_llm_calls":
                0,

            "total_input_tokens":
                0,

            "total_output_tokens":
                0,

            "user_query":
                request.message,

            "task_type":
                "",

            "supervisor_reasoning":
                "",

            "tasks":
                [],

            "task_results":
                {},

            "current_task":
                None,

            "dependency_results":
                {},

            "final_answer":
                None,

            "status":
                "running",

            "messages":
                [],

            "errors":
                [],
        }

        # ====================================================
        # 8. Optional Langfuse Callback
        # ====================================================

        langfuse_handler = (
            None
            if context_decision.uses_direct_answer
            else get_langfuse_handler()
        )

        print(
            "[LANGFUSE]",
            "enabled"
            if langfuse_handler is not None
            else "disabled"
        )

        # ----------------------------------------------------
        # LangGraph config
        #
        # workflow_id is kept as normal LangGraph metadata.
        #
        # session_id / tags / workflow metadata are propagated
        # to Langfuse separately below.
        # ----------------------------------------------------

        graph_config = {

            "run_name":
                "enterprise-multi-agent",

            "metadata": {
                "workflow_id":
                    workflow_id,
            },
        }



        # ====================================================
        # 9. Execute Workflow
        # ====================================================

        # ====================================================
        # 9. Execute Workflow
        # ====================================================

        if context_decision.uses_direct_answer:

            result = build_direct_workflow_result(
                context_decision
            )

            tracer.record(
                event_type="context_direct_answer",
                workflow_id=workflow_id,
                agent="context",
                success=True,
                metadata={
                    "intent": context_decision.intent,
                },
            )

        elif langfuse_handler is not None:

            from langfuse import (
                propagate_attributes,
            )

            from app.observability.langfuse_integration import (
                get_langfuse_client,
            )

            langfuse_client = (
                get_langfuse_client()
            )

            print(
                "[LANGFUSE] starting root trace:",
                workflow_id,
            )

            with (
                    langfuse_client
                            .start_as_current_observation(
                        as_type="span",
                        name="enterprise-multi-agent",
                        input={
                            "message":
                                request.message,
                        },
                        metadata={
                            "workflow_id":
                                workflow_id,
                        },
                    )
            ) as root_span:

                with propagate_attributes(

                        session_id=session_id,

                        trace_name=(
                                "enterprise-multi-agent"
                        ),

                        tags=[
                            "enterprise-multi-agent",
                            "langgraph",
                            "regression-test",
                        ],

                        metadata={
                            "workflow_id":
                                workflow_id,

                            "application":
                                "enterprise-multi-agent",
                        },

                        environment="development",

                ):
                    result = (
                        await agent_graph.ainvoke(
                            initial_state,
                            config=graph_config,
                        )
                    )

                # --------------------------------------------
                # Update root trace output
                # --------------------------------------------

                root_span.update(
                    output={
                        "status":
                            result.get(
                                "status"
                            ),

                        "task_type":
                            result.get(
                                "task_type"
                            ),

                        "final_answer":
                            result.get(
                                "final_answer"
                            ),
                    }
                )

            # --------------------------------------------
            # TEMPORARY during integration testing.
            #
            # Force Langfuse to export immediately so we
            # don't have to wait for background batching.
            # Later this can be removed.
            # --------------------------------------------

            print(
                "[LANGFUSE] flushing trace..."
            )

            langfuse_client.flush()

            print(
                "[LANGFUSE] trace flushed."
            )

        else:

            result = (
                await agent_graph.ainvoke(
                    initial_state,
                    config=graph_config,
                )
            )

        # ====================================================
        # 10. Workflow Latency
        # ====================================================

        workflow_latency_ms = (
            time.perf_counter()
            - workflow_started_at
        ) * 1000

        final_answer = (
            result.get(
                "final_answer"
            )
            or ""
        )

        # ====================================================
        # 11. Save Assistant Conversation Memory
        # ====================================================

        await memory_manager.add_conversation(
            session_id=session_id,
            role="assistant",
            content=final_answer,
        )

        # ====================================================
        # 12. Save Episodic Memory
        # ====================================================

        episode_content = (
            f"User asked: "
            f"{request.message}\n"
            f"Workflow type: "
            f"{result.get('task_type', '')}\n"
            f"Final answer summary: "
            f"{final_answer[:500]}"
        )

        await memory_manager.add_episode(
            session_id=session_id,
            content=episode_content,
            metadata={
                "workflow_id":
                    workflow_id,

                "task_type":
                    result.get(
                        "task_type",
                        "",
                    ),
            },
        )

        # ====================================================
        # 13. Workflow Completed Trace
        # ====================================================

        tracer.record(
            event_type="workflow_completed",
            workflow_id=workflow_id,
            latency_ms=round(
                workflow_latency_ms,
                2,
            ),
            success=(
                result.get(
                    "status"
                )
                != "failed"
            ),
            metadata={
                "status":
                    result.get(
                        "status"
                    ),

                "task_type":
                    result.get(
                        "task_type"
                    ),
            },
        )

        # ====================================================
        # 14. Export Local Structured Trace
        # ====================================================

        structured_trace = (
            tracer.export()
        )

        # ====================================================
        # 15. Estimate Cost
        # ====================================================

        estimated_cost = (
            estimate_cost(
                input_tokens=(
                    obs_context.input_tokens
                ),
                output_tokens=(
                    obs_context.output_tokens
                ),
            )
        )

        # ====================================================
        # 16. Build API Response
        # ====================================================

        response = ChatResponse(

            session_id=session_id,

            answer=final_answer,

            task_type=result.get(
                "task_type",
                "",
            ),

            tasks=result.get(
                "tasks",
                [],
            ),

            trace=result.get(
                "messages",
                [],
            ),

            structured_trace=(
                structured_trace
            ),

            errors=result.get(
                "errors",
                [],
            ),

            metrics=RuntimeMetricsResponse(

                workflow_id=workflow_id,

                latency_ms=round(
                    workflow_latency_ms,
                    2,
                ),

                total_retries=result.get(
                    "total_retries",
                    0,
                ),

                total_llm_calls=(
                    obs_context.llm_calls
                ),

                total_input_tokens=(
                    obs_context.input_tokens
                ),

                total_output_tokens=(
                    obs_context.output_tokens
                ),

                total_tool_calls=(
                    obs_context.tool_calls
                ),

                memory_extractor_calls=(
                    obs_context
                    .memory_extractor_calls
                ),

                memory_consolidator_calls=(
                    obs_context
                    .memory_consolidator_calls
                ),

                memory_fast_path_skips=(
                    obs_context
                    .memory_fast_path_skips
                ),

                estimated_cost_usd=round(
                    estimated_cost,
                    8,
                ),
            ),
        )

        return response

    # ========================================================
    # 17. Workflow Failure
    # ========================================================

    except Exception as exc:

        tracer.record(
            event_type="workflow_failed",
            workflow_id=workflow_id,
            success=False,
            metadata={
                "error":
                    str(exc),
            },
        )

        raise

    # ========================================================
    # 18. Cleanup ContextVar
    # ========================================================

    finally:

        reset_observability_context(
            obs_token
        )
