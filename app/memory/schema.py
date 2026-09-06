from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


MemoryType = Literal[
    "conversation",
    "episodic",
    "semantic",
]


class MemoryRecord(BaseModel):
    """
    统一 Memory Record。

    memory_type 用于区分：

    conversation
        当前会话中的原始用户/Assistant消息

    episodic
        历史 Workflow / Task 经历

    semantic
        从历史交互中抽取出的稳定事实、偏好和约束
    """

    id: str

    memory_type: MemoryType

    session_id: str

    content: str

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )

    created_at: datetime


class ConversationTurn(BaseModel):
    """
    可选的 Conversation Turn Schema。

    目前主要用于类型表达，
    MemoryStore 实际统一存 MemoryRecord。
    """

    role: Literal[
        "user",
        "assistant",
        "system",
    ]

    content: str

    created_at: datetime
