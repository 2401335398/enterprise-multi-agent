from __future__ import annotations

from typing import Any

from app.observability.context import (
    get_observability_context,
)

from app.observability.schema import (
    TraceEvent,
)


class Tracer:
    """
    Workflow-level Structured Tracer。

    Trace Event 不保存在全局 list 中，
    而是写入当前 WorkflowObservabilityContext。

    这样可以保证：

    Request A
        → Context A
        → Events A

    Request B
        → Context B
        → Events B

    即使 FastAPI 并发执行，
    Trace 也不会互相污染。
    """

    def record(
        self,
        *,
        event_type: str,
        workflow_id: str | None = None,
        task_id: str | None = None,
        agent: str | None = None,
        skill: str | None = None,
        tool: str | None = None,
        latency_ms: float | None = None,
        success: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> None:

        # ====================================================
        # 1. 获取当前 Workflow Context
        # ====================================================

        context = (
            get_observability_context()
        )

        # ====================================================
        # 2. Resolve Workflow ID
        #
        # 优先使用显式传入的 workflow_id。
        #
        # 如果调用方没有传，例如：
        #
        # Memory Extractor
        # Query Rewrite
        #
        # 就自动从 ContextVar 获取。
        # ====================================================

        resolved_workflow_id = (
            workflow_id
            or (
                context.workflow_id
                if context
                else "unknown"
            )
        )

        # ====================================================
        # 3. Build Structured Event
        # ====================================================

        event = TraceEvent(

            event_type=
                event_type,

            workflow_id=
                resolved_workflow_id,

            task_id=
                task_id,

            agent=
                agent,

            skill=
                skill,

            tool=
                tool,

            latency_ms=
                latency_ms,

            success=
                success,

            metadata=(
                metadata
                or {}
            ),
        )

        # ====================================================
        # 4. 当前没有 Workflow Context
        #
        # 例如某些 standalone script。
        #
        # 此时不抛异常，
        # 直接忽略 Trace。
        # ====================================================

        if context is None:
            return

        # ====================================================
        # 5. 保存 Structured Event
        # ====================================================

        context.events.append(
            event.model_dump()
        )

        # ====================================================
        # 6. Tool Metrics
        #
        # 每出现一个 tool_call Event，
        # 自动增加 Tool Call 数。
        # ====================================================

        if event_type == "tool_call":

            context.tool_calls += 1

    def export(
        self
    ) -> list[dict]:
        """
        导出当前 Workflow 的全部 Structured Trace。
        """

        context = (
            get_observability_context()
        )

        if context is None:
            return []

        return list(
            context.events
        )


tracer = Tracer()
