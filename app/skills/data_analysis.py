from app.graph.state import AgentState
from app.skills.base import BaseSkill


class DataAnalysisSkill(
    BaseSkill
):

    @property
    def name(self) -> str:
        return "data_analysis"

    @property
    def description(self) -> str:
        return (
            "用于业务分析、数据分析和"
            "多来源信息综合。"
        )

    async def run(
        self,
        state: AgentState
    ) -> dict:

        task = state[
            "current_task"
        ]

        dependency_results = (
            state.get(
                "dependency_results",
                {}
            )
        )

        return {
            "skill":
                self.name,

            "analysis_context": {
                "task":
                    task[
                        "description"
                    ],

                "dependency_results":
                    dependency_results
            }
        }
