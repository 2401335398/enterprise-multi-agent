from app.rag.service import (
    rag_service,
)

from app.tools.base import (
    BaseTool,
)


class DocumentSearchTool(
    BaseTool
):

    @property
    def name(
        self
    ) -> str:

        return "document_search"

    @property
    def description(
        self
    ) -> str:

        return (
            "通过企业级 RAG 检索"
            "内部知识库，并返回带来源"
            "的上下文证据。"
        )

    async def run(
        self,
        query: str,
        filters: dict | None = None,
    ) -> dict:

        return await rag_service.search(
            query=query,
            filters=filters,
        )
