import json
import sqlite3
from pathlib import Path

from app.memory.schema import (
    MemoryRecord,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

MEMORY_DB_PATH = (
    PROJECT_ROOT
    / "data"
    / "memory.db"
)


class SQLiteMemoryStore:

    def __init__(
        self,
        db_path: Path = MEMORY_DB_PATH
    ):

        db_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.db_path = db_path

        self._initialize()

    def _connect(
        self
    ):

        return sqlite3.connect(
            self.db_path
        )

    def _initialize(
        self
    ) -> None:

        with self._connect() as conn:

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    memory_type TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_memory_session
                ON memories(session_id)
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_memory_type
                ON memories(memory_type)
                """
            )

    def add(
        self,
        record: MemoryRecord
    ) -> None:

        with self._connect() as conn:

            conn.execute(
                """
                INSERT OR REPLACE INTO memories (
                    id,
                    memory_type,
                    session_id,
                    content,
                    metadata,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.memory_type,
                    record.session_id,
                    record.content,
                    json.dumps(
                        record.metadata,
                        ensure_ascii=False
                    ),
                    record.created_at.isoformat(),
                )
            )

    def get_session_memories(
        self,
        session_id: str,
        memory_type: str | None = None,
    ) -> list[MemoryRecord]:

        query = """
            SELECT
                id,
                memory_type,
                session_id,
                content,
                metadata,
                created_at
            FROM memories
            WHERE session_id = ?
        """

        params = [
            session_id
        ]

        if memory_type:

            query += """
                AND memory_type = ?
            """

            params.append(
                memory_type
            )

        query += """
            ORDER BY created_at ASC
        """

        with self._connect() as conn:

            rows = conn.execute(
                query,
                params
            ).fetchall()

        return [
            MemoryRecord(
                id=row[0],
                memory_type=row[1],
                session_id=row[2],
                content=row[3],
                metadata=json.loads(
                    row[4]
                ),
                created_at=row[5],
            )
            for row in rows
        ]

    def clear_session(
        self,
        session_id: str
    ) -> None:

        with self._connect() as conn:

            conn.execute(
                """
                DELETE FROM memories
                WHERE session_id = ?
                """,
                (
                    session_id,
                )
            )

    def update(
            self,
            memory_id: str,
            content: str,
            metadata: dict,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE memories
                SET content  = ?,
                    metadata = ?
                WHERE id = ?
                """,
                (
                    content,
                    json.dumps(
                        metadata,
                        ensure_ascii=False
                    ),
                    memory_id,
                )
            )

    def delete(
            self,
            memory_id: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                DELETE
                FROM memories
                WHERE id = ?
                """,
                (
                    memory_id,
                )
            )

    def get_by_id(
            self,
            memory_id: str,
    ) -> MemoryRecord | None:

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id,
                       memory_type,
                       session_id,
                       content,
                       metadata,
                       created_at
                FROM memories
                WHERE id = ?
                """,
                (
                    memory_id,
                )
            ).fetchone()

        if row is None:
            return None

        return MemoryRecord(
            id=row[0],
            memory_type=row[1],
            session_id=row[2],
            content=row[3],
            metadata=json.loads(
                row[4]
            ),
            created_at=row[5],
        )


memory_store = (
    SQLiteMemoryStore()
)
