# app/observability/llm_runtime.py

from __future__ import annotations

import time
from typing import Any

from app.core.llm import llm

from app.observability.context import (
    get_observability_context,
)

from app.observability.tracer import (
    tracer,
)

from app.observability.langfuse_integration import (
    get_langfuse_client,
)


# ============================================================
# Token Usage Extraction
# ============================================================

def _extract_usage(
    response: Any,
) -> tuple[int, int]:
    """
    Extract input/output token usage from common
    LangChain-compatible model response formats.

    Priority:
    1. response.usage_metadata
    2. response.response_metadata["token_usage"]
    3. response.response_metadata["usage"]

    Returns:
        (input_tokens, output_tokens)
    """

    input_tokens = 0
    output_tokens = 0

    # --------------------------------------------------------
    # LangChain standard usage_metadata
    # --------------------------------------------------------

    usage = getattr(
        response,
        "usage_metadata",
        None,
    )

    if isinstance(
        usage,
        dict,
    ):

        input_tokens = int(
            usage.get(
                "input_tokens",
                0,
            )
            or 0
        )

        output_tokens = int(
            usage.get(
                "output_tokens",
                0,
            )
            or 0
        )

        return (
            input_tokens,
            output_tokens,
        )

    # --------------------------------------------------------
    # Provider-specific response metadata
    # --------------------------------------------------------

    response_metadata = getattr(
        response,
        "response_metadata",
        None,
    )

    if isinstance(
        response_metadata,
        dict,
    ):

        token_usage = (
            response_metadata.get(
                "token_usage"
            )
            or response_metadata.get(
                "usage"
            )
            or {}
        )

        if isinstance(
            token_usage,
            dict,
        ):

            input_tokens = int(
                token_usage.get(
                    "prompt_tokens",
                    token_usage.get(
                        "input_tokens",
                        0,
                    ),
                )
                or 0
            )

            output_tokens = int(
                token_usage.get(
                    "completion_tokens",
                    token_usage.get(
                        "output_tokens",
                        0,
                    ),
                )
                or 0
            )

    return (
        input_tokens,
        output_tokens,
    )


# ============================================================
# Response Serialization Helpers
# ============================================================

def _serialize_messages(
    messages: Any,
) -> Any:
    """
    Convert LangChain messages or arbitrary prompt input
    into a Langfuse-friendly structure.

    This function deliberately avoids strict dependency
    on a specific LangChain message class.
    """

    if messages is None:
        return None

    if isinstance(
        messages,
        str,
    ):
        return messages

    if isinstance(
        messages,
        (
            int,
            float,
            bool,
        ),
    ):
        return messages

    if isinstance(
        messages,
        dict,
    ):
        return {
            str(key):
                _serialize_messages(
                    value
                )
            for key, value
            in messages.items()
        }

    if isinstance(
        messages,
        (
            list,
            tuple,
        ),
    ):
        return [
            _serialize_messages(
                item
            )
            for item in messages
        ]

    # --------------------------------------------------------
    # Common LangChain BaseMessage shape
    # --------------------------------------------------------

    content = getattr(
        messages,
        "content",
        None,
    )

    if content is not None:

        message_type = getattr(
            messages,
            "type",
            None,
        )

        role = getattr(
            messages,
            "role",
            None,
        )

        serialized = {
            "content":
                content,
        }

        if message_type:
            serialized[
                "type"
            ] = message_type

        if role:
            serialized[
                "role"
            ] = role

        name = getattr(
            messages,
            "name",
            None,
        )

        if name:
            serialized[
                "name"
            ] = name

        return serialized

    # --------------------------------------------------------
    # Last-resort safe representation
    # --------------------------------------------------------

    try:
        return str(
            messages
        )

    except Exception:
        return (
            "<unserializable>"
        )


def _serialize_response(
    response: Any,
) -> Any:
    """
    Convert an LLM response into a representation
    suitable for Langfuse output.
    """

    if response is None:
        return None

    content = getattr(
        response,
        "content",
        None,
    )

    if content is not None:
        return content

    try:
        return str(
            response
        )

    except Exception:
        return (
            "<unserializable-response>"
        )


# ============================================================
# Model Name Helper
# ============================================================

def _get_model_name() -> str:
    """
    Try to extract the configured model name from
    the LangChain model instance.

    Falls back to the class name when no explicit
    model identifier is exposed.
    """

    candidates = [
        "model_name",
        "model",
        "model_id",
    ]

    for attr_name in candidates:

        value = getattr(
            llm,
            attr_name,
            None,
        )

        if isinstance(
            value,
            str,
        ) and value:

            return value

    return (
        llm.__class__.__name__
    )


# ============================================================
# Local Observability Success Record
# ============================================================

def _record_success(
    *,
    workflow_id: str | None,
    task_id: str | None,
    agent_name: str | None,
    component: str | None,
    latency_ms: float,
    input_tokens: int,
    output_tokens: int,
) -> None:

    context = (
        get_observability_context()
    )

    if context is not None:

        context.llm_calls += 1

        context.input_tokens += (
            input_tokens
        )

        context.output_tokens += (
            output_tokens
        )

    tracer.record(
        event_type="llm_call",
        workflow_id=workflow_id,
        task_id=task_id,
        agent=agent_name,
        latency_ms=round(
            latency_ms,
            2,
        ),
        success=True,
        metadata={
            "component":
                component,

            "input_tokens":
                input_tokens,

            "output_tokens":
                output_tokens,
        },
    )


# ============================================================
# Local Observability Failure Record
# ============================================================

def _record_failure(
    *,
    workflow_id: str | None,
    task_id: str | None,
    agent_name: str | None,
    component: str | None,
    latency_ms: float,
    exc: Exception,
) -> None:

    context = (
        get_observability_context()
    )

    if context is not None:

        context.llm_calls += 1

    tracer.record(
        event_type="llm_call",
        workflow_id=workflow_id,
        task_id=task_id,
        agent=agent_name,
        latency_ms=round(
            latency_ms,
            2,
        ),
        success=False,
        metadata={
            "component":
                component,

            "error":
                str(
                    exc
                ),
        },
    )


# ============================================================
# Centralized LLM Runtime
# ============================================================

async def tracked_llm_invoke(
    messages,
    *,
    workflow_id: str | None = None,
    task_id: str | None = None,
    agent_name: str | None = None,
    component: str | None = None,
):
    """
    Centralized LLM invocation runtime.

    Responsibilities:

    1. Execute the configured LangChain LLM.
    2. Measure latency.
    3. Extract token usage.
    4. Update local WorkflowObservabilityContext.
    5. Record local structured trace events.
    6. Create a Langfuse Generation observation when
       Langfuse is configured.
    7. Preserve graceful fallback when Langfuse is disabled.

    Important:
    Only LLM calls routed through this function are included
    in the local total_llm_calls / token counters.
    """

    started_at = (
        time.perf_counter()
    )

    # --------------------------------------------------------
    # Langfuse configuration
    # --------------------------------------------------------

    langfuse = (
        get_langfuse_client()
    )

    generation_name = (
        component
        or agent_name
        or "llm_call"
    )

    model_name = (
        _get_model_name()
    )

    langfuse_input = (
        _serialize_messages(
            messages
        )
    )

    metadata = {
        "workflow_id":
            workflow_id,

        "task_id":
            task_id,

        "agent":
            agent_name,

        "component":
            component,
    }

    # Remove None values so Langfuse UI stays cleaner.
    metadata = {
        key: value
        for key, value
        in metadata.items()
        if value is not None
    }

    # ========================================================
    # Langfuse-enabled path
    # ========================================================

    if langfuse is not None:

        try:

            # ------------------------------------------------
            # start_as_current_observation makes this
            # generation active in the current OpenTelemetry
            # context. If chat.py already established a
            # Langfuse/LangGraph trace, this generation will
            # become its child automatically.
            # ------------------------------------------------

            with (
                langfuse
                .start_as_current_observation(
                    as_type="generation",
                    name=generation_name,
                    model=model_name,
                    input=langfuse_input,
                    metadata=metadata,
                )
            ) as generation:

                try:

                    # ----------------------------------------
                    # Actual LLM invocation
                    #
                    # IMPORTANT:
                    # We intentionally do NOT pass another
                    # Langfuse CallbackHandler here.
                    #
                    # Otherwise the same LLM request may be
                    # recorded twice:
                    #
                    # 1. this manual Generation
                    # 2. LangChain CallbackHandler Generation
                    #
                    # This function itself owns the LLM-level
                    # Langfuse observation.
                    # ----------------------------------------

                    response = (
                        await llm.ainvoke(
                            messages
                        )
                    )

                    latency_ms = (
                        time.perf_counter()
                        - started_at
                    ) * 1000

                    (
                        input_tokens,
                        output_tokens,
                    ) = _extract_usage(
                        response
                    )

                    # ----------------------------------------
                    # Local observability
                    # ----------------------------------------

                    _record_success(
                        workflow_id=(
                            workflow_id
                        ),
                        task_id=task_id,
                        agent_name=(
                            agent_name
                        ),
                        component=(
                            component
                        ),
                        latency_ms=(
                            latency_ms
                        ),
                        input_tokens=(
                            input_tokens
                        ),
                        output_tokens=(
                            output_tokens
                        ),
                    )

                    # ----------------------------------------
                    # Langfuse Generation completion
                    # ----------------------------------------

                    generation.update(
                        output=(
                            _serialize_response(
                                response
                            )
                        ),
                        usage_details={
                            "input_tokens":
                                input_tokens,

                            "output_tokens":
                                output_tokens,
                        },
                        metadata={
                            **metadata,

                            "latency_ms":
                                round(
                                    latency_ms,
                                    2,
                                ),

                            "success":
                                True,
                        },
                    )

                    return response

                except Exception as exc:

                    latency_ms = (
                        time.perf_counter()
                        - started_at
                    ) * 1000

                    _record_failure(
                        workflow_id=(
                            workflow_id
                        ),
                        task_id=task_id,
                        agent_name=(
                            agent_name
                        ),
                        component=(
                            component
                        ),
                        latency_ms=(
                            latency_ms
                        ),
                        exc=exc,
                    )

                    # ----------------------------------------
                    # Mark Langfuse Generation as failed.
                    # ----------------------------------------

                    generation.update(
                        level="ERROR",
                        status_message=str(
                            exc
                        ),
                        metadata={
                            **metadata,

                            "latency_ms":
                                round(
                                    latency_ms,
                                    2,
                                ),

                            "success":
                                False,

                            "error":
                                str(
                                    exc
                                ),
                        },
                    )

                    raise

        # ----------------------------------------------------
        # Langfuse itself must never break the application.
        #
        # If creating/updating the Langfuse observation fails
        # before the actual model call starts, fall back to
        # normal local execution.
        #
        # IMPORTANT:
        # We only enter this block for Langfuse instrumentation
        # failures outside the inner LLM execution path.
        # ----------------------------------------------------

        except Exception as langfuse_exc:

            print(
                "[LANGFUSE] generation "
                "instrumentation failed:",
                langfuse_exc,
            )

    # ========================================================
    # Langfuse-disabled / instrumentation-fallback path
    # ========================================================

    try:

        response = (
            await llm.ainvoke(
                messages
            )
        )

        latency_ms = (
            time.perf_counter()
            - started_at
        ) * 1000

        (
            input_tokens,
            output_tokens,
        ) = _extract_usage(
            response
        )

        _record_success(
            workflow_id=(
                workflow_id
            ),
            task_id=task_id,
            agent_name=(
                agent_name
            ),
            component=(
                component
            ),
            latency_ms=(
                latency_ms
            ),
            input_tokens=(
                input_tokens
            ),
            output_tokens=(
                output_tokens
            ),
        )

        return response

    except Exception as exc:

        latency_ms = (
            time.perf_counter()
            - started_at
        ) * 1000

        _record_failure(
            workflow_id=(
                workflow_id
            ),
            task_id=task_id,
            agent_name=(
                agent_name
            ),
            component=(
                component
            ),
            latency_ms=(
                latency_ms
            ),
            exc=exc,
        )

        raise
