from app.agents.base import BaseAgent
from app.graph.state import AgentState

from app.observability.llm_runtime import (
    tracked_llm_invoke,
)


REPORT_AGENT_PROMPT = """
你是企业级 Multi-Agent 系统中的 Report Agent。

你的职责不是重新执行分析，
而是根据已经完成的 Specialist Agent 结果，
生成最终面向用户的回答。

必须遵守：

1. 优先回答用户原始问题。
2. 不重复进行 Specialist Agent 已完成的深度推理。
3. 不得伪造任何数据、事实或来源。
4. 如果某个 Agent 明确指出证据不足，
   必须保留这一限制。
5. 如果不同 Agent 结论存在冲突，
   应明确指出，而不是自行掩盖。
6. 如果结果中存在 [Source N] 引用，
   应尽量保留引用。
7. 不输出内部 Task JSON、
   ToolCall、Tool Result、RRF score、
   rerank score、latency 等系统内部信息。
8. 输出应简洁、结构清晰，
   避免机械重复已有报告内容。
"""


class ReportAgent(BaseAgent):

    @property
    def name(self) -> str:
        return "report"

    async def run(
        self,
        state: AgentState
    ) -> dict:

        # ====================================================
        # 1. 基础数据
        # ====================================================

        user_query = (
            state.get(
                "user_query",
                ""
            )
        )

        tasks = (
            state.get(
                "tasks",
                []
            )
        )

        task_results = (
            state.get(
                "task_results",
                {}
            )
        )

        # ====================================================
        # 2. 构造精简 Task Summary
        #
        # 非常重要：
        #
        # 不再把整个 tasks JSON 放进 Prompt。
        #
        # 只保留：
        #
        # - task id
        # - agent
        # - skill
        # - description
        # - result
        #
        # 不传：
        #
        # tool_results
        # tool_calls
        # RAG chunks
        # scores
        # runtime metadata
        # ====================================================

        compact_results = []

        synthesis_result = None

        for task in tasks:

            task_id = (
                task.get(
                    "id"
                )
            )

            result = (
                task_results.get(
                    task_id,
                    ""
                )
            )

            if not result:
                continue

            agent_name = (
                task.get(
                    "agent",
                    ""
                )
            )

            skill_name = (
                task.get(
                    "skill"
                )
            )

            description = (
                task.get(
                    "description",
                    ""
                )
            )

            compact_results.append(
                {
                    "task_id":
                        task_id,

                    "agent":
                        agent_name,

                    "skill":
                        skill_name,

                    "description":
                        description,

                    "result":
                        result,
                }
            )

            # ================================================
            # 如果已经有 synthesis_analysis，
            # 说明 Analysis Agent 已经做过综合分析。
            #
            # Report 不应该再次从零分析。
            # ================================================

            if (
                agent_name == "analysis"
                and
                skill_name == "synthesis_analysis"
            ):
                synthesis_result = result

        # ====================================================
        # 3. Fast Report Path
        #
        # 已经存在综合分析结果：
        #
        # Analysis
        #     ↓
        # synthesis_analysis
        #     ↓
        # Report 只做最终整理
        #
        # 避免重复 reasoning。
        # ====================================================

        if synthesis_result:

            prompt = f"""
用户原始问题：

{user_query}


以下是 Analysis Agent 已完成的综合分析结果：

================ ANALYSIS RESULT ================

{synthesis_result}

============== END ANALYSIS RESULT ==============


请将以上分析整理成最终回答。

要求：

1. 不要重新进行一轮完整分析。
2. 保留重要结论、风险和建议。
3. 删除明显重复内容。
4. 保留必要的证据限制和不确定性说明。
5. 如果存在 [Source N] 引用，尽量保留。
6. 直接回答用户问题。
7. 不展示内部 Agent、Task、Skill 等系统实现信息。
"""

            component = (
                "report_fast_path"
            )

        # ====================================================
        # 4. Normal Report Path
        #
        # 没有 synthesis_analysis 时，
        # Report 才负责综合多个 Agent。
        # ====================================================

        else:

            parts = []

            for item in compact_results:

                parts.append(
                    (
                        f"Task: "
                        f"{item['task_id']}\n"
                        f"Agent: "
                        f"{item['agent']}\n"
                        f"Skill: "
                        f"{item['skill']}\n"
                        f"目标: "
                        f"{item['description']}\n"
                        f"结果:\n"
                        f"{item['result']}"
                    )
                )

            compact_context = (
                "\n\n"
                "----------------------------------------"
                "\n\n"
            ).join(
                parts
            )

            prompt = f"""
用户原始问题：

{user_query}


以下是各 Specialist Agent 的最终业务结果：

================ AGENT RESULTS ================

{compact_context}

============== END AGENT RESULTS ==============


请综合这些结果生成最终回答。

要求：

1. 围绕用户原始问题组织答案。
2. 去除多个 Agent 之间的重复内容。
3. 不得添加 Agent 结果中没有依据的数据。
4. 对证据不足的部分明确说明。
5. 如果不同结果存在冲突，应明确指出。
6. 如果结果中包含 [Source N]，尽量保留。
7. 不展示内部 Agent、Task、Skill、Tool 等系统细节。
"""

            component = (
                "report_generation"
            )

        # ====================================================
        # 5. LLM
        # ====================================================

        response = await tracked_llm_invoke(
            [
                {
                    "role":
                        "system",

                    "content":
                        REPORT_AGENT_PROMPT,
                },
                {
                    "role":
                        "user",

                    "content":
                        prompt,
                }
            ],

            workflow_id=state.get(
                "workflow_id"
            ),

            agent_name=self.name,

            component=component,
        )

        # ====================================================
        # 6. Return
        # ====================================================

        return {
            "final_answer":
                response.content,

            "status":
                "completed",

            "messages": [
                (
                    "Report Agent completed "
                    f"using {component}"
                )
            ]
        }
