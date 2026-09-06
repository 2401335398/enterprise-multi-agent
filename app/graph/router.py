from app.graph.state import AgentState


def route_after_supervisor(state: AgentState) -> str:

    task_type = state["task_type"]

    if task_type == "research":
        return "research"

    if task_type == "knowledge":
        return "knowledge"

    if task_type == "analysis":
        return "analysis"

    if task_type == "complex":
        return "research"

    return "report"
