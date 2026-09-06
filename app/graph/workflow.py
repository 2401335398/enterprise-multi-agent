from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from app.agents.supervisor import (
    supervisor_node,
)

from app.agents.registry import (
    AGENT_REGISTRY,
)

from app.graph.scheduler import (
    scheduler_node,
)

from app.graph.state import AgentState


async def report_node(
    state: AgentState
):

    report_agent = (
        AGENT_REGISTRY["report"]
    )

    return await report_agent.run(
        state
    )


def build_graph():

    graph = StateGraph(
        AgentState
    )

    graph.add_node(
        "supervisor",
        supervisor_node
    )

    graph.add_node(
        "scheduler",
        scheduler_node
    )

    graph.add_node(
        "report",
        report_node
    )

    graph.add_edge(
        START,
        "supervisor"
    )

    graph.add_edge(
        "supervisor",
        "scheduler"
    )

    graph.add_edge(
        "scheduler",
        "report"
    )

    graph.add_edge(
        "report",
        END
    )

    return graph.compile()


agent_graph = build_graph()
