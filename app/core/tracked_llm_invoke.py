import time

from app.core.llm import llm

from app.observability.tracer import (
    tracer,
)

from app.core.llm_runtime import (
    llm_metrics,
)


async def tracked_llm_invoke(
    messages,
    *,
    workflow_id: str,
    task_id: str | None = None,
    agent_name: str | None = None,
):
    started = time.perf_counter()

    response = await llm.ainvoke(
        messages
    )

    latency_ms = (
        time.perf_counter()
        - started
    ) * 1000

    input_tokens = 0
    output_tokens = 0

    usage = getattr(
        response,
        "usage_metadata",
        None
    )

    if usage:

        input_tokens = (
            usage.get(
                "input_tokens",
                0
            )
        )

        output_tokens = (
            usage.get(
                "output_tokens",
                0
            )
        )

    llm_metrics.record(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    tracer.record(
        event_type="llm_call",

        workflow_id=workflow_id,

        task_id=task_id,

        agent=agent_name,

        latency_ms=round(
            latency_ms,
            2
        ),

        metadata={
            "input_tokens":
                input_tokens,

            "output_tokens":
                output_tokens,
        }
    )

    return response
