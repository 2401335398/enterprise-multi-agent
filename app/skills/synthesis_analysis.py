from app.graph.state import AgentState
from app.skills.base import BaseSkill


class SynthesisAnalysisSkill(BaseSkill):

    @property
    def name(self) -> str:
        return "synthesis_analysis"

    @property
    def description(self) -> str:
        return (
            "用于综合多个前置任务结果，"
            "进行跨来源比较、归纳和策略分析。"
        )

    async def run(
        self,
        state: AgentState
    ) -> dict:

        task = state["current_task"]

        dependency_results = state.get(
            "dependency_results",
            {}
        )

        return {
            "skill":
                self.name,

            "analysis_type":
                "synthesis",

            "task":
                task["description"],

            "dependency_results":
                dependency_results
        }
