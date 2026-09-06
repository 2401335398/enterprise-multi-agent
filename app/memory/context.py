from app.memory.manager import (
    memory_manager,
)


def build_memory_context(
    session_id: str,
    current_query: str,
) -> str:

    conversation = (
        memory_manager
        .get_recent_conversation(
            session_id,
            limit=6,
        )
    )

    semantic_memories = (
        memory_manager
        .search_semantic_memories(
            session_id=session_id,
            query=current_query,
            top_k=5,
        )
    )

    episodes = (
        memory_manager
        .get_episodes(
            session_id,
            limit=5,
        )
    )

    blocks = []

    if semantic_memories:

        lines = [
            "Relevant Semantic Memory:"
        ]

        for memory in (
            semantic_memories
        ):

            lines.append(
                f"- "
                f"{memory['content']}"
            )

        blocks.append(
            "\n".join(
                lines
            )
        )

    if conversation:

        lines = [
            "Recent Conversation:"
        ]

        for record in conversation:

            role = (
                record.metadata.get(
                    "role",
                    "unknown"
                )
            )

            lines.append(
                f"{role}: "
                f"{record.content}"
            )

        blocks.append(
            "\n".join(
                lines
            )
        )

    if episodes:

        lines = [
            "Recent Episodes:"
        ]

        for record in episodes:

            lines.append(
                f"- {record.content}"
            )

        blocks.append(
            "\n".join(
                lines
            )
        )

    return (
        "\n\n".join(
            blocks
        )
    )

