import json
import re
import time

from app.graph.state import AgentState
from app.schemas.agent import SupervisorDecision
from app.observability.llm_runtime import tracked_llm_invoke
from app.observability.tracer import tracer


SUPERVISOR_PROMPT = """
你是企业级 Multi-Agent 系统中的 Supervisor。

你不直接回答用户问题。

你的职责是：

1. 判断任务类型
2. 将复杂目标拆分成子任务
3. 为每个任务选择最合适的 Agent
4. 为任务建立依赖关系，形成 DAG


可用 Agent：

research:
- 市场研究
- 竞争对手研究
- 行业趋势
- 外部公开信息

knowledge:
- 企业内部文档
- 内部知识库
- 产品资料
- 历史报告

analysis:
- 数据分析
- 综合分析
- 多来源结果对比
- 原因分析
- 策略判断


任务类型只能是：

simple
research
knowledge
analysis
complex


规则：

1. 不要为了 Multi-Agent 强行拆分任务。
2. 没有依赖关系的任务应该允许并行。
3. 存在依赖关系时必须写入 depends_on。
4. 不要生成 report 任务。
5. Task ID 使用 T1、T2、T3...
6. status 固定为 pending。
7. 必须只输出一个 JSON 对象。
8. 不要输出 Markdown。
9. 不要输出 ```json。
10. 不要在 JSON 前后添加任何解释。


Memory 使用规则：

11. Historical Memory 仅用于帮助理解：
    - 用户当前请求中的指代关系
    - 前文讨论对象
    - 已经明确的上下文
    - 与当前任务直接相关的历史信息

12. 当前用户请求的优先级始终高于 Historical Memory。

13. 如果当前请求与 Historical Memory 冲突，
    必须以当前请求为准。

14. 不要因为 Historical Memory 中出现某个主题，
    就强行把当前任务解释成那个主题。

15. Historical Memory 只能作为辅助上下文，
    不能替代当前用户请求。


严格使用以下格式：

{
  "task_type": "complex",
  "reasoning": "任务需要多个专业 Agent 协作",
  "tasks": [
    {
      "id": "T1",
      "description": "调研外部市场情况",
      "agent": "research",
      "depends_on": [],
      "status": "pending",
      "retry_count": 0,
      "result": null,
      "error": null
    }
  ]
}
"""


def extract_json(text: str) -> dict:
    """
    尽可能从 LLM 输出中提取 JSON。
    """

    if not text:
        raise ValueError(
            "Supervisor returned empty content."
        )

    text = text.strip()

    if text.startswith("```"):
        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
        )

        text = re.sub(
            r"\s*```$",
            "",
            text,
        )

        text = text.strip()

    try:
        return json.loads(text)

    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError(
            "No JSON object found in "
            f"Supervisor output: {text!r}"
        )

    return json.loads(
        text[start:end + 1]
    )


async def supervisor_node(
    state: AgentState
) -> dict:

    node_started_at = time.perf_counter()

    user_query = state["user_query"]

    memory_context = (
        state.get(
            "memory_context",
            ""
        )
        or ""
    )

    if memory_context:
        user_content = f"""
Historical Memory:

{memory_context}


Current User Request:

{user_query}


请结合 Historical Memory 理解当前请求中的上下文和指代关系。

但是：
当前用户请求的优先级高于 Historical Memory。
如果两者发生冲突，以当前用户请求为准。
"""

    else:
        user_content = f"""
Current User Request:

{user_query}
"""

    response = await tracked_llm_invoke(
        [
            {
                "role": "system",
                "content": SUPERVISOR_PROMPT,
            },
            {
                "role": "user",
                "content": user_content,
            },
        ],
        workflow_id=state.get(
            "workflow_id"
        ),
        agent_name="supervisor",
        component="supervisor_planning",
    )

    print(
        "\n"
        "========== SUPERVISOR RAW RESPONSE =========="
    )
    print(repr(response.content))
    print(
        "============================================="
        "\n"
    )

    data = extract_json(
        response.content
    )

    decision = (
        SupervisorDecision
        .model_validate(data)
    )

    latency_ms = (
        time.perf_counter()
        - node_started_at
    ) * 1000

    tracer.record(
        event_type="supervisor_completed",
        workflow_id=state.get(
            "workflow_id"
        ),
        agent="supervisor",
        latency_ms=round(
            latency_ms,
            2
        ),
        success=True,
        metadata={
            "task_type":
                decision.task_type,
            "task_count":
                len(decision.tasks),
        },
    )

    return {
        "task_type":
            decision.task_type,

        "supervisor_reasoning":
            decision.reasoning,

        "tasks": [
            task.model_dump()
            for task
            in decision.tasks
        ],

        "messages": [
            f"Supervisor classified task as "
            f"{decision.task_type}"
        ],
    }
