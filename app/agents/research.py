from app.agents.base import BaseAgent
from app.graph.state import AgentState

from app.observability.llm_runtime import (
    tracked_llm_invoke,
)

from app.skills.registry import (
    get_skill,
)

from app.skills.router import (
    select_skill,
)


class ResearchAgent(BaseAgent):

    @property
    def name(self) -> str:
        return "research"

    async def run(
        self,
        state: AgentState
    ) -> dict:

        task = state[
            "current_task"
        ]

        # =====================
        # Dynamic Skill Routing
        # =====================

        skill_name = select_skill(
            agent_name=self.name,
            state=state
        )

        skill = get_skill(
            skill_name
        )

        skill_result = (
            await skill.run(
                state
            )
        )

        prompt = f"""
用户总体目标：

{state["user_query"]}


当前任务：

{task["description"]}


系统选择的 Skill：

{skill_name}


Skill 执行结果：

{skill_result}


请基于 Skill 和 Tool 返回的结果，
完成当前 Research Task。

要求：

1. 只处理当前任务。
2. 不要虚构工具没有提供的信息。
3. 如果当前工具仍为 Mock 实现，需要明确说明。
"""

        response = await tracked_llm_invoke(
            [
                {
                    "role": "system",
                    "content": (
                        "你是企业级 "
                        "Research Agent。"
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            workflow_id=state.get("workflow_id"),
            task_id=task.get("id"),
            agent_name=self.name,
            component="research_answer",
        )

        return {
            "result":
                response.content,

            "skill":
                skill_name,

            "tool_calls":
                skill_result.get(
                    "tool_calls",
                    []
                ),

            "tool_results":
                skill_result.get(
                    "tool_results",
                    []
                )
        }


