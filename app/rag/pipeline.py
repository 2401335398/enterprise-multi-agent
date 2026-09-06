from app.rag.config import (
    FINAL_TOP_K,
    RERANK_CANDIDATES,
)

from app.rag.hybrid import (
    hybrid_retrieve,
)

from app.rag.reranker import (
    reranker,
)


def retrieve(
    query: str
) -> list[dict]:

    candidates = (
        hybrid_retrieve(
            query=query,

            top_k=(
                RERANK_CANDIDATES
            ),

            candidate_k=(
                RERANK_CANDIDATES
            ),
        )
    )

    results = (
        reranker.rerank(
            query=query,
            documents=candidates,
            top_k=FINAL_TOP_K,
        )
    )

    return results
