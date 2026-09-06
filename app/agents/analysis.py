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



class AnalysisAgent(BaseAgent):

    @property
    def name(self) -> str:
        return "analysis"

    async def run(
        self,
        state: AgentState
    ) -> dict:

        task = state[
            "current_task"
        ]

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


当前分析任务：

{task["description"]}


系统选择的 Skill：

{skill_name}


Skill 提供的分析上下文：

{skill_result}


请完成当前分析任务。

要求：

1. 如果存在前置任务结果，必须使用。
2. 不要创造不存在的数据。
3. 如果证据不足，要明确说明。
"""

        response = await tracked_llm_invoke(
            [
                {
                    "role":
                        "system",

                    "content":
                        (
                            "你是企业级 "
                            "Analysis Agent。"
                        )
                },
                {
                    "role":
                        "user",

                    "content":
                        prompt
                }
            ],
            workflow_id=state.get("workflow_id"),
            task_id=task.get("id"),
            agent_name=self.name,
            component="analysis_reasoning",
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

