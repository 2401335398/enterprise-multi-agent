from app.rag.context_builder import (
    build_context,
)

from app.rag.hybrid import (
    hybrid_retrieve,
)

from app.rag.query_rewriter import (
    rewrite_query,
)


class RAGService:

    async def search(
        self,
        query: str,
        filters: dict | None = None,
        conversation_context: str | None = None,
    ) -> dict:

        # =========================
        # 1. Query Rewrite
        # =========================

        rewritten_query = (
            await rewrite_query(
                query=query,

                conversation_context=(
                    conversation_context
                )
            )
        )

        # =========================
        # 2. Hybrid Retrieval
        # =========================

        results = (
            hybrid_retrieve(
                query=rewritten_query,
                filters=filters,
            )
        )

        # =========================
        # 3. Context Builder
        # =========================

        context = (
            build_context(
                results
            )
        )

        return {
            "original_query":
                query,

            "rewritten_query":
                rewritten_query,

            "filters":
                filters or {},

            "results":
                results,

            "context":
                context,
        }


rag_service = (
    RAGService()
)
