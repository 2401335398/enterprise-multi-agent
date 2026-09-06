from abc import ABC, abstractmethod

from langchain_openai import ChatOpenAI

from app.graph.state import AgentState
"""
为什么要抽象这一层？
因为以后：
Research Agent
Knowledge Agent
Analysis Agent
Report Agent
都遵循：
async def run(state) -> dict
后面我们做 Agent Registry 会非常方便。
"""

class BaseAgent(ABC):

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def run(self, state: AgentState) -> dict:
        raise NotImplementedError
