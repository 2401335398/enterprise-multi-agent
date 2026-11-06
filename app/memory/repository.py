from typing import Protocol

from app.memory.schema import MemoryRecord, MemoryType


class MemoryRepository(Protocol):
    async def add(self, record: MemoryRecord) -> MemoryRecord: ...

    async def get_session_memories(
        self,
        session_id: str,
        memory_type: MemoryType | None = None,
        limit: int | None = None,
    ) -> list[MemoryRecord]: ...

    async def get_by_id(self, memory_id: str) -> MemoryRecord | None: ...

    async def get_by_ids(
        self,
        memory_ids: list[str],
        *,
        session_id: str,
        memory_type: MemoryType,
    ) -> list[MemoryRecord]: ...

    async def update(
        self,
        memory_id: str,
        content: str,
        metadata: dict,
    ) -> MemoryRecord | None: ...

    async def delete(self, memory_id: str) -> bool: ...

    async def clear_session(self, session_id: str) -> int: ...

    async def list_semantic_memories(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[MemoryRecord]: ...
