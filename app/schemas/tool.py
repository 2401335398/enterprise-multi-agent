from typing import Any

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    tool: str

    arguments: dict[str, Any] = Field(
        default_factory=dict
    )


class ToolExecutionResult(BaseModel):
    tool: str

    arguments: dict[str, Any]

    success: bool

    result: Any | None = None

    error: str | None = None

    latency_ms: float | None = None

    policy_action: str | None = None
