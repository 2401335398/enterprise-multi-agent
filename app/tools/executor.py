import asyncio
import time

from app.schemas.policy import ToolPolicyAction
from app.schemas.tool import (
    ToolCall,
    ToolExecutionResult,
)
from app.tools.policy import tool_policy_engine
from app.tools.registry import get_tool
from app.observability.tracer import tracer


TOOL_TIMEOUT_SECONDS = 20


def _record_tool_trace(
    *,
    tool_call: ToolCall,
    workflow_id: str | None,
    task_id: str | None,
    agent_name: str | None,
    latency_ms: float,
    success: bool,
    policy_action: str,
    error: str | None = None,
) -> None:

    tracer.record(
        event_type="tool_call",
        workflow_id=workflow_id,
        task_id=task_id,
        agent=agent_name,
        tool=tool_call.tool,
        latency_ms=round(
            latency_ms,
            2
        ),
        success=success,
        metadata={
            "policy_action":
                policy_action,
            "error":
                error,
        },
    )


async def execute_tool_call(
    tool_call: ToolCall,
    *,
    workflow_id: str | None = None,
    task_id: str | None = None,
    agent_name: str | None = None,
) -> ToolExecutionResult:
    """
    Generic Tool Executor.

    - Registry lookup
    - Governance
    - argument passing
    - timeout
    - error handling
    - latency
    - structured tracing
    """

    policy = (
        tool_policy_engine.evaluate(
            tool_call.tool,
            agent_name=agent_name,
        )
    )

    if (
        policy.action
        == ToolPolicyAction.DENY
    ):
        error = (
            "Tool denied by policy: "
            f"{policy.reason}"
        )

        _record_tool_trace(
            tool_call=tool_call,
            workflow_id=workflow_id,
            task_id=task_id,
            agent_name=agent_name,
            latency_ms=0,
            success=False,
            policy_action=(
                policy.action.value
            ),
            error=error,
        )

        return ToolExecutionResult(
            tool=tool_call.tool,
            arguments=tool_call.arguments,
            success=False,
            error=error,
            latency_ms=0,
            policy_action=(
                policy.action.value
            ),
        )

    if (
        policy.action
        == ToolPolicyAction.REQUIRE_APPROVAL
    ):
        error = (
            "Tool requires human approval: "
            f"{policy.reason}"
        )

        _record_tool_trace(
            tool_call=tool_call,
            workflow_id=workflow_id,
            task_id=task_id,
            agent_name=agent_name,
            latency_ms=0,
            success=False,
            policy_action=(
                policy.action.value
            ),
            error=error,
        )

        return ToolExecutionResult(
            tool=tool_call.tool,
            arguments=tool_call.arguments,
            success=False,
            error=error,
            latency_ms=0,
            policy_action=(
                policy.action.value
            ),
        )

    started_at = (
        time.perf_counter()
    )

    try:
        tool = get_tool(
            tool_call.tool
        )

        result = await asyncio.wait_for(
            tool.run(
                **tool_call.arguments
            ),
            timeout=(
                TOOL_TIMEOUT_SECONDS
            ),
        )

        latency_ms = (
            time.perf_counter()
            - started_at
        ) * 1000

        _record_tool_trace(
            tool_call=tool_call,
            workflow_id=workflow_id,
            task_id=task_id,
            agent_name=agent_name,
            latency_ms=latency_ms,
            success=True,
            policy_action=(
                policy.action.value
            ),
        )

        return ToolExecutionResult(
            tool=tool_call.tool,
            arguments=tool_call.arguments,
            success=True,
            result=result,
            latency_ms=round(
                latency_ms,
                2
            ),
            policy_action=(
                policy.action.value
            ),
        )

    except asyncio.TimeoutError:
        latency_ms = (
            time.perf_counter()
            - started_at
        ) * 1000

        error = (
            f"Tool timeout after "
            f"{TOOL_TIMEOUT_SECONDS}s"
        )

        _record_tool_trace(
            tool_call=tool_call,
            workflow_id=workflow_id,
            task_id=task_id,
            agent_name=agent_name,
            latency_ms=latency_ms,
            success=False,
            policy_action=(
                policy.action.value
            ),
            error=error,
        )

        return ToolExecutionResult(
            tool=tool_call.tool,
            arguments=tool_call.arguments,
            success=False,
            error=error,
            latency_ms=round(
                latency_ms,
                2
            ),
            policy_action=(
                policy.action.value
            ),
        )

    except Exception as exc:
        latency_ms = (
            time.perf_counter()
            - started_at
        ) * 1000

        error = str(exc)

        _record_tool_trace(
            tool_call=tool_call,
            workflow_id=workflow_id,
            task_id=task_id,
            agent_name=agent_name,
            latency_ms=latency_ms,
            success=False,
            policy_action=(
                policy.action.value
            ),
            error=error,
        )

        return ToolExecutionResult(
            tool=tool_call.tool,
            arguments=tool_call.arguments,
            success=False,
            error=error,
            latency_ms=round(
                latency_ms,
                2
            ),
            policy_action=(
                policy.action.value
            ),
        )


async def execute_tool_calls(
    tool_calls: list[ToolCall],
    *,
    workflow_id: str | None = None,
    task_id: str | None = None,
    agent_name: str | None = None,
) -> list[ToolExecutionResult]:
    """
    Concurrently execute independent ToolCalls.

    All new keyword arguments are optional, so existing callers remain valid.
    """

    if not tool_calls:
        return []

    executions = [
        execute_tool_call(
            tool_call,
            workflow_id=workflow_id,
            task_id=task_id,
            agent_name=agent_name,
        )
        for tool_call
        in tool_calls
    ]

    return await asyncio.gather(
        *executions
    )
