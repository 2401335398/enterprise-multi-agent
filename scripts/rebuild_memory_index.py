"""Rebuild the Chroma semantic-memory index from PostgreSQL."""

from __future__ import annotations

import argparse
import asyncio

from app.db.session import dispose_database_engine
from app.memory.postgres_repository import memory_repository
from app.memory.vector_store import semantic_memory_store


async def rebuild_semantic_index(batch_size: int = 100) -> int:
    await asyncio.to_thread(semantic_memory_store.clear)

    indexed = 0
    while True:
        records = await memory_repository.list_semantic_memories(
            offset=indexed,
            limit=batch_size,
        )
        if not records:
            break

        for record in records:
            await asyncio.to_thread(
                semantic_memory_store.add,
                memory_id=record.id,
                session_id=record.session_id,
                content=record.content,
                metadata=record.metadata,
            )
            indexed += 1

    return indexed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild semantic-memory vectors from PostgreSQL."
    )
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    if args.batch_size <= 0:
        parser.error("--batch-size must be greater than zero")

    async def run() -> None:
        try:
            indexed = await rebuild_semantic_index(args.batch_size)
            print(f"Rebuilt {indexed} semantic memory vectors.")
        finally:
            await dispose_database_engine()

    asyncio.run(run())


if __name__ == "__main__":
    main()
