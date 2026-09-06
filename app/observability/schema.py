from typing import Any

from pydantic import BaseModel, Field


class TraceEvent(BaseModel):

    event_type: str

    workflow_id: str

    task_id: str | None = None

    agent: str | None = None

    skill: str | None = None

    tool: str | None = None

    latency_ms: float | None = None

    success: bool = True

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )
