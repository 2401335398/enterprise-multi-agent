import uuid

from datetime import (
    datetime,
    timezone,
)

from app.memory.schema import (
    MemoryRecord,
)

from app.memory.sqlite_store import (
    memory_store,
)

from app.memory.vector_store import (
    semantic_memory_store,
)

MEMORY_SIMILARITY_THRESHOLD = 0.72


class MemoryManager:

    def add_conversation(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> None:

        record = MemoryRecord(
            id=str(
                uuid.uuid4()
            ),

            memory_type=(
                "conversation"
            ),

            session_id=session_id,

            content=content,

            metadata={
                "role":
                    role
            },

            created_at=(
                datetime.now(
                    timezone.utc
                )
            ),
        )

        memory_store.add(
            record
        )

    def add_episode(
        self,
        session_id: str,
        content: str,
        metadata: dict | None = None,
    ) -> None:

        record = MemoryRecord(
            id=str(
                uuid.uuid4()
            ),

            memory_type=(
                "episodic"
            ),

            session_id=session_id,

            content=content,

            metadata=(
                metadata
                or {}
            ),

            created_at=(
                datetime.now(
                    timezone.utc
                )
            ),
        )

        memory_store.add(
            record
        )

    def get_recent_conversation(
        self,
        session_id: str,
        limit: int = 6,
    ) -> list[MemoryRecord]:

        records = (
            memory_store
            .get_session_memories(
                session_id,
                memory_type=(
                    "conversation"
                )
            )
        )

        return records[
            -limit:
        ]

    def get_episodes(
        self,
        session_id: str,
        limit: int = 10,
    ) -> list[MemoryRecord]:

        records = (
            memory_store
            .get_session_memories(
                session_id,
                memory_type=(
                    "episodic"
                )
            )
        )

        return records[
            -limit:
        ]

    def add_semantic_memory(
        self,
        session_id: str,
        content: str,
        metadata: dict | None = None,
    ) -> None:

        record = MemoryRecord(
            id=str(
                uuid.uuid4()
            ),

            memory_type="semantic",

            session_id=session_id,

            content=content,

            metadata=(
                metadata
                or {}
            ),

            created_at=(
                datetime.now(
                    timezone.utc
                )
            ),
        )

        memory_store.add(
            record
        )

        semantic_memory_store.add(
            memory_id=record.id,
            session_id=session_id,
            content=content,
            metadata=record.metadata,
        )

    def search_semantic_memories(
        self,
        session_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:

        return (
            semantic_memory_store.search(
                session_id=session_id,
                query=query,
                top_k=top_k,
            )
        )

    async def consolidate_semantic_memory(
            self,
            session_id: str,
            candidate_memory: str,
    ) -> dict:

        from app.memory.consolidator import (
            consolidate_memory,
        )

        # =========================================
        # 1. Search Related Semantic Memories
        # =========================================

        existing_memories = (
            semantic_memory_store.search(
                session_id=session_id,
                query=candidate_memory,
                top_k=5,
            )
        )

        # =========================================
        # 2. Similarity Gate
        # =========================================

        if not existing_memories:
            self.add_semantic_memory(
                session_id=session_id,
                content=candidate_memory,
                metadata={
                    "source":
                        "memory_fast_path"
                },
            )

            return {
                "action":
                    "ADD",

                "target_memory_id":
                    None,

                "memory":
                    candidate_memory,

                "reason":
                    "No existing semantic memory found.",

                "fast_path":
                    True,
            }

        best_score = max(
            memory.get(
                "score",
                0.0
            )
            for memory
            in existing_memories
        )

        if (
                best_score
                < MEMORY_SIMILARITY_THRESHOLD
        ):
            self.add_semantic_memory(
                session_id=session_id,
                content=candidate_memory,
                metadata={
                    "source":
                        "memory_fast_path"
                },
            )

            return {
                "action":
                    "ADD",

                "target_memory_id":
                    None,

                "memory":
                    candidate_memory,

                "reason":
                    (
                        "No sufficiently similar "
                        "memory found."
                    ),

                "best_similarity":
                    best_score,

                "fast_path":
                    True,
            }

        # =========================================
        # 3. High Similarity
        #    才调用 LLM Consolidator
        # =========================================

        decision = await consolidate_memory(
            candidate_memory=(
                candidate_memory
            ),
            existing_memories=(
                existing_memories
            ),
        )

        decision[
            "best_similarity"
        ] = best_score

        decision[
            "fast_path"
        ] = False

        action = decision.get(
            "action"
        )

        target_memory_id = (
            decision.get(
                "target_memory_id"
            )
        )

        final_memory = (
            decision.get(
                "memory"
            )
        )

        # =========================================
        # ADD
        # =========================================

        if action == "ADD":

            if final_memory:
                self.add_semantic_memory(
                    session_id=session_id,
                    content=final_memory,
                    metadata={
                        "source":
                            "memory_consolidation"
                    },
                )

        # =========================================
        # UPDATE
        # =========================================

        elif (
                action == "UPDATE"
                and target_memory_id
                and final_memory
        ):

            old_record = (
                memory_store.get_by_id(
                    target_memory_id
                )
            )

            if old_record:
                metadata = dict(
                    old_record.metadata
                )

                metadata[
                    "updated"
                ] = True

                memory_store.update(
                    memory_id=
                    target_memory_id,

                    content=
                    final_memory,

                    metadata=
                    metadata,
                )

                semantic_memory_store.add(
                    memory_id=
                    target_memory_id,

                    session_id=
                    session_id,

                    content=
                    final_memory,

                    metadata=
                    metadata,
                )

        # =========================================
        # DELETE
        # =========================================

        elif (
                action == "DELETE"
                and target_memory_id
        ):

            memory_store.delete(
                target_memory_id
            )

            semantic_memory_store.delete(
                target_memory_id
            )

        return decision


memory_manager = (
    MemoryManager()
)
