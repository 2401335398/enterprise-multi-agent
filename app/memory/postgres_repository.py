import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.memory import MemoryRecordModel
from app.db.session import async_session_factory
from app.memory.schema import MemoryRecord, MemoryType


class PostgresMemoryRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] = async_session_factory,
    ) -> None:
        self._session_factory = session_factory

    async def add(self, record: MemoryRecord) -> MemoryRecord:
        model = self._to_model(record)
        async with self._session_factory() as session:
            async with session.begin():
                session.add(model)
        return self._to_record(model)

    async def get_session_memories(
        self,
        session_id: str,
        memory_type: MemoryType | None = None,
        limit: int | None = None,
    ) -> list[MemoryRecord]:
        statement = select(MemoryRecordModel).where(
            MemoryRecordModel.session_id == session_id
        )
        if memory_type is not None:
            statement = statement.where(
                MemoryRecordModel.memory_type == memory_type
            )

        if limit is None:
            statement = statement.order_by(
                MemoryRecordModel.created_at.asc(),
                MemoryRecordModel.id.asc(),
            )
        else:
            statement = statement.order_by(
                MemoryRecordModel.created_at.desc(),
                MemoryRecordModel.id.desc(),
            ).limit(limit)

        async with self._session_factory() as session:
            async with session.begin():
                models = (await session.scalars(statement)).all()

        records = self._to_records(models)
        return list(reversed(records)) if limit is not None else records

    async def get_by_id(self, memory_id: str) -> MemoryRecord | None:
        parsed_id = self._parse_id(memory_id)
        if parsed_id is None:
            return None

        async with self._session_factory() as session:
            async with session.begin():
                model = await session.get(MemoryRecordModel, parsed_id)
        return self._to_record(model) if model is not None else None

    async def get_by_ids(
        self,
        memory_ids: list[str],
        *,
        session_id: str,
        memory_type: MemoryType,
    ) -> list[MemoryRecord]:
        parsed_ids = [
            parsed_id
            for memory_id in memory_ids
            if (parsed_id := self._parse_id(memory_id)) is not None
        ]
        if not parsed_ids:
            return []

        statement = select(MemoryRecordModel).where(
            MemoryRecordModel.id.in_(parsed_ids),
            MemoryRecordModel.session_id == session_id,
            MemoryRecordModel.memory_type == memory_type,
        )
        async with self._session_factory() as session:
            async with session.begin():
                models = (await session.scalars(statement)).all()
        return self._to_records(models)

    async def update(
        self,
        memory_id: str,
        content: str,
        metadata: dict,
    ) -> MemoryRecord | None:
        parsed_id = self._parse_id(memory_id)
        if parsed_id is None:
            return None

        async with self._session_factory() as session:
            async with session.begin():
                model = await session.get(
                    MemoryRecordModel,
                    parsed_id,
                    with_for_update=True,
                )
                if model is None:
                    return None
                model.content = content
                model.metadata_json = dict(metadata)
                await session.flush()
        return self._to_record(model)

    async def delete(self, memory_id: str) -> bool:
        parsed_id = self._parse_id(memory_id)
        if parsed_id is None:
            return False

        statement = delete(MemoryRecordModel).where(
            MemoryRecordModel.id == parsed_id
        )
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(statement)
        return bool(result.rowcount)

    async def clear_session(self, session_id: str) -> int:
        statement = delete(MemoryRecordModel).where(
            MemoryRecordModel.session_id == session_id
        )
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(statement)
        return int(result.rowcount or 0)

    async def list_semantic_memories(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        statement = (
            select(MemoryRecordModel)
            .where(MemoryRecordModel.memory_type == "semantic")
            .order_by(
                MemoryRecordModel.created_at.asc(),
                MemoryRecordModel.id.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
        async with self._session_factory() as session:
            async with session.begin():
                models = (await session.scalars(statement)).all()
        return self._to_records(models)

    @staticmethod
    def _parse_id(memory_id: str) -> uuid.UUID | None:
        try:
            return uuid.UUID(memory_id)
        except (TypeError, ValueError, AttributeError):
            return None

    @staticmethod
    def _to_model(record: MemoryRecord) -> MemoryRecordModel:
        return MemoryRecordModel(
            id=uuid.UUID(record.id),
            memory_type=record.memory_type,
            session_id=record.session_id,
            content=record.content,
            metadata_json=dict(record.metadata),
            created_at=record.created_at,
        )

    @staticmethod
    def _to_record(model: MemoryRecordModel) -> MemoryRecord:
        return MemoryRecord(
            id=str(model.id),
            memory_type=model.memory_type,
            session_id=model.session_id,
            content=model.content,
            metadata=dict(model.metadata_json),
            created_at=model.created_at,
        )

    @classmethod
    def _to_records(
        cls,
        models: Sequence[MemoryRecordModel],
    ) -> list[MemoryRecord]:
        return [cls._to_record(model) for model in models]


memory_repository = PostgresMemoryRepository()
