from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowObservabilityContext:
    """
    每个 Workflow 独立的 Observability Context。

    使用 ContextVar 隔离并发请求，
    避免不同 FastAPI Request 的 Trace / Metrics 混在一起。
    """

    workflow_id: str

    # ========================================================
    # LLM Metrics
    # ========================================================

    llm_calls: int = 0

    input_tokens: int = 0

    output_tokens: int = 0

    # ========================================================
    # Tool Metrics
    # ========================================================

    tool_calls: int = 0

    # ========================================================
    # Memory Metrics
    # ========================================================

    memory_extractor_calls: int = 0

    memory_consolidator_calls: int = 0

    memory_fast_path_skips: int = 0

    # ========================================================
    # Structured Trace Events
    # ========================================================

    events: list[
        dict[str, Any]
    ] = field(
        default_factory=list
    )


_current_context: ContextVar[
    WorkflowObservabilityContext | None
] = ContextVar(
    "workflow_observability_context",
    default=None,
)


def set_observability_context(
    context: WorkflowObservabilityContext,
):
    """
    设置当前 Workflow 的 Observability Context。
    """

    return _current_context.set(
        context
    )


def get_observability_context(
) -> WorkflowObservabilityContext | None:
    """
    获取当前 Workflow 的 Observability Context。
    """

    return _current_context.get()


def reset_observability_context(
    token
) -> None:
    """
    Workflow 结束后恢复 ContextVar。
    """

    _current_context.reset(
        token
    )
