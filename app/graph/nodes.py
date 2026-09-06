from app.agents.registry import AGENT_REGISTRY

from app.graph.state import AgentState


async def research_node(state: AgentState):
    return await AGENT_REGISTRY["research"].run(state)


async def knowledge_node(state: AgentState):
    return await AGENT_REGISTRY["knowledge"].run(state)


async def analysis_node(state: AgentState):
    return await AGENT_REGISTRY["analysis"].run(state)


async def report_node(state: AgentState):
    return await AGENT_REGISTRY["report"].run(state)
