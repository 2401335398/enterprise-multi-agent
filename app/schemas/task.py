from typing import Literal

from pydantic import BaseModel, Field


AgentName = Literal[
    "research",
    "knowledge",
    "analysis"
]


class Task(BaseModel):

    id: str

    description: str

    agent: AgentName

    depends_on: list[str] = Field(
        default_factory=list
    )

    status: Literal[
        "pending",
        "running",
        "completed",
        "failed",
        "timeout"
    ] = "pending"


    skill: str | None = None

    # tools: list[str] = Field(
    #     default_factory=list
    # )

    tool_calls: list[dict] = Field(
        default_factory=list
    )

    tool_results: list[dict] = Field(
        default_factory=list
    )

    retry_count: int = 0

    result: str | None = None

    error: str | None = None

    started_at: float | None = None

    completed_at: float | None = None

    latency_ms: float | None = None


