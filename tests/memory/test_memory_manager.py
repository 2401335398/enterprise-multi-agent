from __future__ import annotations

import asyncio

import pytest

from app.memory.manager import MemoryManager, SemanticIndexSyncError


class FakeRepository:
    def __init__(self):
        self.records = {}

    async def add(self, record):
        self.records[record.id] = record
        return record

    async def get_session_memories(
        self, session_id, memory_type=None, limit=None
    ):
        records = [
            record
            for record in self.records.values()
            if record.session_id == session_id
            and (memory_type is None or record.memory_type == memory_type)
        ]
        records.sort(key=lambda record: record.created_at)
        return records[-limit:] if limit is not None else records

    async def get_by_id(self, memory_id):
        return self.records.get(memory_id)

    async def get_by_ids(
        self, memory_ids, *, session_id, memory_type
    ):
        return [
            self.records[memory_id]
            for memory_id in memory_ids
            if memory_id in self.records
            and self.records[memory_id].session_id == session_id
            and self.records[memory_id].memory_type == memory_type
        ]

    async def update(self, memory_id, content, metadata):
        record = self.records.get(memory_id)
        if record is None:
            return None
        updated = record.model_copy(
            update={"content": content, "metadata": metadata}
        )
        self.records[memory_id] = updated
        return updated

    async def delete(self, memory_id):
        return self.records.pop(memory_id, None) is not None

    async def clear_session(self, session_id):
        ids = [
            record.id
            for record in self.records.values()
            if record.session_id == session_id
        ]
        for memory_id in ids:
            del self.records[memory_id]
        return len(ids)

    async def list_semantic_memories(self, *, offset=0, limit=100):
        records = [
            record
            for record in self.records.values()
            if record.memory_type == "semantic"
        ]
        return records[offset : offset + limit]


class FakeVectorStore:
    def __init__(self):
        self.records = {}
        self.fail_add = False

    def add(self, memory_id, session_id, content, metadata):
        if self.fail_add:
            raise RuntimeError("index unavailable")
        self.records[memory_id] = {
            "id": memory_id,
            "session_id": session_id,
            "content": content,
            "metadata": metadata,
            "score": 0.9,
        }

    def search(self, session_id, query, top_k=5):
        return [
            record
            for record in self.records.values()
            if record["session_id"] == session_id
        ][:top_k]

    def delete(self, memory_id):
        self.records.pop(memory_id, None)


def test_conversation_and_episode_behavior_is_preserved():
    repository = FakeRepository()
    manager = MemoryManager(repository, FakeVectorStore())

    async def scenario():
        await manager.add_conversation("s1", "user", "first")
        await manager.add_conversation("s1", "assistant", "second")
        await manager.add_episode("s1", "episode", {"workflow_id": "w1"})

        conversation = await manager.get_recent_conversation("s1", limit=1)
        episodes = await manager.get_episodes("s1")

        assert [record.content for record in conversation] == ["second"]
        assert episodes[0].metadata == {"workflow_id": "w1"}

    asyncio.run(scenario())


def test_postgres_remains_authoritative_when_chroma_write_fails():
    repository = FakeRepository()
    vector_store = FakeVectorStore()
    vector_store.fail_add = True
    manager = MemoryManager(repository, vector_store)

    async def scenario():
        with pytest.raises(SemanticIndexSyncError):
            await manager.add_semantic_memory("s1", "durable fact")

        records = await repository.get_session_memories(
            "s1", memory_type="semantic"
        )
        assert [record.content for record in records] == ["durable fact"]

    asyncio.run(scenario())


def test_stale_chroma_results_are_filtered_by_postgres():
    repository = FakeRepository()
    vector_store = FakeVectorStore()
    manager = MemoryManager(repository, vector_store)

    vector_store.records["00000000-0000-0000-0000-000000000001"] = {
        "id": "00000000-0000-0000-0000-000000000001",
        "session_id": "s1",
        "content": "stale",
        "metadata": {},
        "score": 1.0,
    }

    results = asyncio.run(manager.search_semantic_memories("s1", "query"))
    assert results == []


def test_concurrent_conversation_writes_do_not_share_session_state():
    repository = FakeRepository()
    manager = MemoryManager(repository, FakeVectorStore())

    async def scenario():
        await asyncio.gather(
            *(
                manager.add_conversation("s1", "user", f"message-{index}")
                for index in range(25)
            )
        )
        records = await manager.get_recent_conversation("s1", limit=25)
        assert len(records) == 25
        assert len({record.id for record in records}) == 25

    asyncio.run(scenario())
