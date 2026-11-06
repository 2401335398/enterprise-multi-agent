import asyncio
import logging
import uuid
from datetime import datetime, timezone

from app.memory.postgres_repository import memory_repository
from app.memory.repository import MemoryRepository
from app.memory.schema import MemoryRecord, MemoryType
from app.memory.vector_store import semantic_memory_store


MEMORY_SIMILARITY_THRESHOLD = 0.72
logger = logging.getLogger(__name__)


class SemanticIndexSyncError(RuntimeError):
    def __init__(self, memory_id: str) -> None:
        super().__init__(
            f"Memory {memory_id} was committed to PostgreSQL but could not be "
            "synchronized to Chroma. Run the semantic index rebuild command."
        )
        self.memory_id = memory_id


class MemoryManager:
    def __init__(
        self,
        repository: MemoryRepository = memory_repository,
        vector_store=semantic_memory_store,
    ) -> None:
        self._repository = repository
        self._vector_store = vector_store

    async def add_conversation(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        await self._repository.add(
            self._new_record(
                memory_type="conversation",
                session_id=session_id,
                content=content,
                metadata={"role": role},
            )
        )

    async def add_episode(
        self,
        session_id: str,
        content: str,
        metadata: dict | None = None,
    ) -> None:
        await self._repository.add(
            self._new_record(
                memory_type="episodic",
                session_id=session_id,
                content=content,
                metadata=metadata or {},
            )
        )

    async def get_recent_conversation(
        self,
        session_id: str,
        limit: int = 6,
    ) -> list[MemoryRecord]:
        return await self._repository.get_session_memories(
            session_id,
            memory_type="conversation",
            limit=limit,
        )

    async def get_episodes(
        self,
        session_id: str,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        return await self._repository.get_session_memories(
            session_id,
            memory_type="episodic",
            limit=limit,
        )

    async def add_semantic_memory(
        self,
        session_id: str,
        content: str,
        metadata: dict | None = None,
    ) -> None:
        record = self._new_record(
            memory_type="semantic",
            session_id=session_id,
            content=content,
            metadata=metadata or {},
        )

        # The database transaction finishes before embedding or Chroma I/O.
        await self._repository.add(record)
        try:
            await asyncio.to_thread(
                self._vector_store.add,
                memory_id=record.id,
                session_id=session_id,
                content=content,
                metadata=record.metadata,
            )
        except Exception as exc:
            logger.exception(
                "Semantic memory committed but Chroma synchronization failed",
                extra={"memory_id": record.id, "session_id": session_id},
            )
            raise SemanticIndexSyncError(record.id) from exc

    async def search_semantic_memories(
        self,
        session_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        vector_matches = await asyncio.to_thread(
            self._vector_store.search,
            session_id=session_id,
            query=query,
            top_k=top_k,
        )
        match_ids = [match["id"] for match in vector_matches]
        records = await self._repository.get_by_ids(
            match_ids,
            session_id=session_id,
            memory_type="semantic",
        )
        records_by_id = {record.id: record for record in records}

        authoritative_matches = []
        for match in vector_matches:
            record = records_by_id.get(match["id"])
            if record is None:
                continue
            authoritative_matches.append(
                {
                    "id": record.id,
                    "content": record.content,
                    "metadata": record.metadata,
                    "score": match.get("score", 0.0),
                }
            )
        return authoritative_matches

    async def consolidate_semantic_memory(
        self,
        session_id: str,
        candidate_memory: str,
    ) -> dict:
        from app.memory.consolidator import consolidate_memory

        existing_memories = await self.search_semantic_memories(
            session_id=session_id,
            query=candidate_memory,
            top_k=5,
        )

        if not existing_memories:
            await self.add_semantic_memory(
                session_id=session_id,
                content=candidate_memory,
                metadata={"source": "memory_fast_path"},
            )
            return {
                "action": "ADD",
                "target_memory_id": None,
                "memory": candidate_memory,
                "reason": "No existing semantic memory found.",
                "fast_path": True,
            }

        best_score = max(
            memory.get("score", 0.0) for memory in existing_memories
        )
        if best_score < MEMORY_SIMILARITY_THRESHOLD:
            await self.add_semantic_memory(
                session_id=session_id,
                content=candidate_memory,
                metadata={"source": "memory_fast_path"},
            )
            return {
                "action": "ADD",
                "target_memory_id": None,
                "memory": candidate_memory,
                "reason": "No sufficiently similar memory found.",
                "best_similarity": best_score,
                "fast_path": True,
            }

        # No database session is open while the consolidator calls the LLM.
        decision = await consolidate_memory(
            candidate_memory=candidate_memory,
            existing_memories=existing_memories,
        )
        decision["best_similarity"] = best_score
        decision["fast_path"] = False

        action = decision.get("action")
        target_memory_id = decision.get("target_memory_id")
        final_memory = decision.get("memory")

        if action == "ADD" and final_memory:
            await self.add_semantic_memory(
                session_id=session_id,
                content=final_memory,
                metadata={"source": "memory_consolidation"},
            )
        elif action == "UPDATE" and target_memory_id and final_memory:
            await self._update_semantic_memory(
                session_id=session_id,
                memory_id=target_memory_id,
                content=final_memory,
            )
        elif action == "DELETE" and target_memory_id:
            await self._delete_semantic_memory(target_memory_id)

        return decision

    async def _update_semantic_memory(
        self,
        *,
        session_id: str,
        memory_id: str,
        content: str,
    ) -> None:
        old_record = await self._repository.get_by_id(memory_id)
        if old_record is None:
            return

        metadata = {**old_record.metadata, "updated": True}
        updated = await self._repository.update(
            memory_id=memory_id,
            content=content,
            metadata=metadata,
        )
        if updated is None:
            return

        try:
            await asyncio.to_thread(
                self._vector_store.add,
                memory_id=memory_id,
                session_id=session_id,
                content=content,
                metadata=metadata,
            )
        except Exception as exc:
            logger.exception(
                "Semantic memory updated but Chroma synchronization failed",
                extra={"memory_id": memory_id, "session_id": session_id},
            )
            raise SemanticIndexSyncError(memory_id) from exc

    async def _delete_semantic_memory(self, memory_id: str) -> None:
        deleted = await self._repository.delete(memory_id)
        if not deleted:
            return
        try:
            await asyncio.to_thread(self._vector_store.delete, memory_id)
        except Exception:
            # Searches are reconciled with PostgreSQL, so a stale vector is hidden.
            logger.exception(
                "Semantic memory deleted but stale Chroma vector remains",
                extra={"memory_id": memory_id},
            )

    @staticmethod
    def _new_record(
        *,
        memory_type: MemoryType,
        session_id: str,
        content: str,
        metadata: dict,
    ) -> MemoryRecord:
        return MemoryRecord(
            id=str(uuid.uuid4()),
            memory_type=memory_type,
            session_id=session_id,
            content=content,
            metadata=metadata,
            created_at=datetime.now(timezone.utc),
        )


memory_manager = MemoryManager()
