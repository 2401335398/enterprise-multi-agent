from app.graph.state import AgentState
from app.schemas.tool import ToolCall


def build_tool_calls(
    skill_name: str,
    state: AgentState
) -> list[ToolCall]:
    """
    根据 Skill + Task 构建结构化 ToolCall。

    当前是 deterministic planning。

    后续可以增加：
    LLM Tool Planner fallback。
    """

    task = state[
        "current_task"
    ]

    description = (
        task["description"]
        .lower()
    )

    # =========================
    # web_research
    # =========================

    if skill_name == "web_research":

        return [
            ToolCall(
                tool="search",
                arguments={
                    "query":
                        task[
                            "description"
                        ]
                }
            )
        ]

    # =========================
    # competitor_research
    # =========================

    if skill_name == (
        "competitor_research"
    ):

        calls = [
            ToolCall(
                tool="search",

                arguments={
                    "query":
                        task[
                            "description"
                        ]
                }
            )
        ]

        browser_keywords = [
            "官网",
            "网页",
            "产品页面",
            "发布说明",
            "release",
            "website",
            "official",
        ]

        if any(
            keyword in description
            for keyword
            in browser_keywords
        ):

            calls.append(
                ToolCall(
                    tool="browser",

                    arguments={
                        "url":
                            (
                                "https://example.com/"
                                "mock-competitor"
                            )
                    }
                )
            )

        return calls

    # =========================
    # document_search
    # =========================

    if skill_name == (
        "document_search"
    ):

        return [
            ToolCall(
                tool=(
                    "document_search"
                ),

                arguments={
                    "query":
                        task[
                            "description"
                        ]
                }
            )
        ]

    # =========================
    # data_analysis
    # =========================

    if skill_name == (
        "data_analysis"
    ):

        return []

    # =========================
    # synthesis_analysis
    # =========================

    if skill_name == (
        "synthesis_analysis"
    ):

        return []

    raise ValueError(
        f"No tool routing rule "
        f"for skill: {skill_name}"
    )
