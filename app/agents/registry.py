from app.core.llm import llm

from app.agents.research import ResearchAgent
from app.agents.knowledge import KnowledgeAgent
from app.agents.analysis import AnalysisAgent
from app.agents.report import ReportAgent


research_agent = ResearchAgent(llm)
knowledge_agent = KnowledgeAgent(llm)
analysis_agent = AnalysisAgent(llm)
report_agent = ReportAgent(llm)


AGENT_REGISTRY = {
    "research": research_agent,
    "knowledge": knowledge_agent,
    "analysis": analysis_agent,
    "report": report_agent,
}
