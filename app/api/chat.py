# app/api/chat.py

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from app.graph.workflow import agent_graph

from app.memory.manager import memory_manager
from app.memory.context import build_memory_context
from app.memory.extractor import extract_semantic_memory
from app.memory.router import should_process_memory

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

    session_id = (
        request.session_id
        or str(
            uuid.uuid4()
        )
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
            build_memory_context(
                session_id=session_id,
                current_query=(
                    request.message
                ),
            )
        )

        # ====================================================
        # 5. Store Current User Message
        # ====================================================

        memory_manager.add_conversation(
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
            get_langfuse_handler()
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

        if langfuse_handler is not None:

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

        memory_manager.add_conversation(
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

        memory_manager.add_episode(
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
