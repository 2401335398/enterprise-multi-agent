from __future__ import annotations

import time
from typing import Any

from app.core.llm import llm
from app.observability.context import get_observability_context
from app.observability.tracer import tracer


def _extract_usage(
    response: Any,
) -> tuple[int, int]:
    """
    LangChain providers commonly expose usage in usage_metadata.
    Fallback to response_metadata.token_usage when needed.
    """

    input_tokens = 0
    output_tokens = 0

    usage = getattr(
        response,
        "usage_metadata",
        None,
    )

    if isinstance(usage, dict):
        input_tokens = int(
            usage.get("input_tokens", 0) or 0
        )
        output_tokens = int(
            usage.get("output_tokens", 0) or 0
        )

        return input_tokens, output_tokens

    response_metadata = getattr(
        response,
        "response_metadata",
        None,
    )

    if isinstance(response_metadata, dict):
        token_usage = (
            response_metadata.get("token_usage")
            or response_metadata.get("usage")
            or {}
        )

        if isinstance(token_usage, dict):
            input_tokens = int(
                token_usage.get(
                    "prompt_tokens",
                    token_usage.get("input_tokens", 0)
                )
                or 0
            )

            output_tokens = int(
                token_usage.get(
                    "completion_tokens",
                    token_usage.get("output_tokens", 0)
                )
                or 0
            )

    return input_tokens, output_tokens


async def tracked_llm_invoke(
    messages,
    *,
    workflow_id: str | None = None,
    task_id: str | None = None,
    agent_name: str | None = None,
    component: str | None = None,
):
    """
    Centralized LLM invocation for local observability.

    IMPORTANT:
    Only calls routed through this function are included in the local
    total_llm_calls / token counters.
    """

    started_at = time.perf_counter()

    try:
        response = await llm.ainvoke(messages)

        latency_ms = (
            time.perf_counter() - started_at
        ) * 1000

        input_tokens, output_tokens = (
            _extract_usage(response)
        )

        context = get_observability_context()

        if context is not None:
            context.llm_calls += 1
            context.input_tokens += input_tokens
            context.output_tokens += output_tokens

        tracer.record(
            event_type="llm_call",
            workflow_id=workflow_id,
            task_id=task_id,
            agent=agent_name,
            latency_ms=round(latency_ms, 2),
            success=True,
            metadata={
                "component": component,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        )

        return response

    except Exception as exc:
        latency_ms = (
            time.perf_counter() - started_at
        ) * 1000

        context = get_observability_context()

        if context is not None:
            context.llm_calls += 1

        tracer.record(
            event_type="llm_call",
            workflow_id=workflow_id,
            task_id=task_id,
            agent=agent_name,
            latency_ms=round(latency_ms, 2),
            success=False,
            metadata={
                "component": component,
                "error": str(exc),
            },
        )

        raise
