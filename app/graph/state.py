from operator import add
from typing import Annotated, TypedDict


class AgentState(TypedDict):

    user_query: str

    task_type: str

    supervisor_reasoning: str

    tasks: list[dict]

    task_results: dict[str, str]

    current_task: dict | None

    dependency_results: dict[str, str]

    final_answer: str | None

    status: str

    messages: Annotated[
        list[str],
        add
    ]

    errors: Annotated[
        list[str],
        add
    ]

    # 新增
    workflow_id: str

    workflow_started_at: float

    workflow_completed_at: float | None

    workflow_latency_ms: float | None

    total_retries: int

    total_llm_calls: int

    total_input_tokens: int

    total_output_tokens: int

    session_id: str
    memory_context: str


