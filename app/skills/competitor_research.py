from app.graph.state import AgentState
from app.skills.base import BaseSkill

from app.tools.executor import (
    execute_tool_calls,
)

from app.tools.router import (
    build_tool_calls,
)


class CompetitorResearchSkill(
    BaseSkill
):

    @property
    def name(self) -> str:
        return (
            "competitor_research"
        )

    @property
    def description(self) -> str:
        return (
            "用于竞品、竞争对手、"
            "产品变化和竞争格局研究。"
        )

    async def run(
        self,
        state: AgentState
    ) -> dict:

        tool_calls = (
            build_tool_calls(
                skill_name=self.name,
                state=state
            )
        )

        tool_execution_results = (
            await execute_tool_calls(
                tool_calls
            )
        )

        return {
            "skill":
                self.name,

            "tool_calls": [
                call.model_dump()
                for call
                in tool_calls
            ],

            "tool_results": [
                result.model_dump()
                for result
                in tool_execution_results
            ]
        }
