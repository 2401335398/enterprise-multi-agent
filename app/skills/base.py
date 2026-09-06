from abc import ABC, abstractmethod

from app.graph.state import AgentState


class BaseSkill(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def description(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def run(
        self,
        state: AgentState
    ) -> dict:
        raise NotImplementedError
