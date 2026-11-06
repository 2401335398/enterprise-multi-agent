from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.memory.postgres_repository import PostgresMemoryRepository
from app.memory.schema import MemoryRecord


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration tests",
)


def _record(session_id: str, content: str) -> MemoryRecord:
    return MemoryRecord(
        id=str(uuid.uuid4()),
        memory_type="conversation",
        session_id=session_id,
        content=content,
        metadata={"role": "user"},
        created_at=datetime.now(timezone.utc),
    )


def test_postgres_repository_crud_concurrency_and_restart_persistence():
    session_id = f"test-{uuid.uuid4()}"
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
        check=True,
    )

    async def scenario():
        engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        repository = PostgresMemoryRepository(factory)

        try:
            records = [_record(session_id, f"item-{index}") for index in range(20)]
            await asyncio.gather(*(repository.add(record) for record in records))

            stored = await repository.get_session_memories(session_id)
            assert len(stored) == 20

            updated = await repository.update(
                records[0].id,
                "updated",
                {"role": "user", "updated": True},
            )
            assert updated is not None
            assert updated.content == "updated"
            assert await repository.delete(records[1].id) is True
        finally:
            await engine.dispose()

        # A new engine simulates a process restart; data must still be present.
        restarted_engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
        restarted_factory = async_sessionmaker(
            restarted_engine, expire_on_commit=False
        )
        restarted_repository = PostgresMemoryRepository(restarted_factory)
        try:
            persisted = await restarted_repository.get_session_memories(session_id)
            assert len(persisted) == 19
            assert any(record.content == "updated" for record in persisted)
            assert await restarted_repository.clear_session(session_id) == 19
        finally:
            await restarted_engine.dispose()

    asyncio.run(scenario())
