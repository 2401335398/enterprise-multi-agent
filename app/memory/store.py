from collections import defaultdict

from app.memory.schema import (
    MemoryRecord,
)


class MemoryStore:

    def __init__(self):

        self.records: dict[
            str,
            list[MemoryRecord]
        ] = defaultdict(list)

    def add(
        self,
        record: MemoryRecord
    ) -> None:

        self.records[
            record.session_id
        ].append(
            record
        )

    def get_session_memories(
        self,
        session_id: str,
        memory_type: str | None = None,
    ) -> list[MemoryRecord]:

        records = self.records.get(
            session_id,
            []
        )

        if memory_type is None:
            return records

        return [
            record
            for record in records
            if record.memory_type
            == memory_type
        ]

    def clear_session(
        self,
        session_id: str
    ) -> None:

        self.records.pop(
            session_id,
            None
        )


memory_store = MemoryStore()
