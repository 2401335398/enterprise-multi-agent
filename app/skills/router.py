from app.graph.state import AgentState


def select_skill(
    agent_name: str,
    state: AgentState
) -> str:
    """
    根据 Agent 类型、Task Description
    和依赖关系选择 Skill。

    当前版本使用 deterministic routing。
    后续可以增加 LLM fallback。
    """

    task = state["current_task"]

    description = (
        task["description"]
        .lower()
    )

    dependencies = task.get(
        "depends_on",
        []
    )

    # =========================
    # Research Agent
    # =========================

    if agent_name == "research":

        competitor_keywords = [
            "竞争对手",
            "竞品",
            "竞争情况",
            "竞争格局",
            "竞争分析",
            "competitor",
            "competitive",
        ]

        if any(
            keyword in description
            for keyword
            in competitor_keywords
        ):
            return (
                "competitor_research"
            )

        return "web_research"

    # =========================
    # Knowledge Agent
    # =========================

    if agent_name == "knowledge":

        return "document_search"

    # =========================
    # Analysis Agent
    # =========================

    if agent_name == "analysis":

        # 有多个依赖任务时，
        # 通常属于综合分析
        if len(dependencies) >= 2:

            return (
                "synthesis_analysis"
            )

        synthesis_keywords = [
            "综合",
            "整合",
            "结合",
            "汇总",
            "比较",
            "策略",
            "建议",
            "synthesis",
        ]

        if any(
            keyword in description
            for keyword
            in synthesis_keywords
        ):
            return (
                "synthesis_analysis"
            )

        return "data_analysis"

    raise ValueError(
        f"No skill routing rule "
        f"for agent: {agent_name}"
    )
