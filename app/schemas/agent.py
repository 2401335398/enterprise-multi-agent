from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.task import Task
"""
Supervisor 必须输出结构化结果，而不是自由文本。
{
  "task_type": "complex",
  "reasoning": "该问题同时需要外部调研和数据分析",
  "tasks": [
    {
      "id": "T1",
      "description": "调研行业趋势",
      "agent": "research",
      "depends_on": [],
      "status": "pending"
    },
    {
      "id": "T2",
      "description": "综合分析调研结果",
      "agent": "analysis",
      "depends_on": ["T1"],
      "status": "pending"
    }
  ]
}

"""

class SupervisorDecision(BaseModel):

    task_type: Literal[
        "simple",
        "research",
        "knowledge",
        "analysis",
        "complex"
    ]

    reasoning: str

    tasks: list[Task] = Field(default_factory=list)
