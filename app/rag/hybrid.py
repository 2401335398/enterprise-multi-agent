from collections import defaultdict

from app.rag.bm25 import (
    bm25_retriever,
)

from app.rag.retriever import (
    vector_retrieve,
)

from app.rag.reranker import (
    reranker,
)


RRF_K = 60


def hybrid_retrieve_without_rerank(
    query: str,
    top_k: int = 10,
    candidate_k: int = 10,
    filters: dict | None = None,
) -> list[dict]:
    """
    Hybrid Retrieval without Reranker.

    Pipeline:

    Query
      ├── Vector Retrieval
      └── BM25 Retrieval
             ↓
          RRF Fusion
             ↓
           Top-K

    主要用于：
    1. RAG Evaluation
    2. Ablation Study
    3. 对比 Reranker 的实际贡献
    """

    # =========================================
    # 1. Dense / Vector Retrieval
    # =========================================

    vector_results = vector_retrieve(
        query=query,
        top_k=candidate_k,
        filters=filters,
    )

    # =========================================
    # 2. Sparse / BM25 Retrieval
    # =========================================

    bm25_results = bm25_retriever.search(
        query=query,
        top_k=candidate_k,
        filters=filters,
    )

    # =========================================
    # 3. RRF Score
    # =========================================

    scores = defaultdict(
        float
    )

    documents = {}

    retriever_hits = defaultdict(
        list
    )

    # =========================================
    # Vector Ranking
    # =========================================

    for rank, item in enumerate(
        vector_results,
        start=1
    ):

        chunk_id = item.get(
            "id"
        )

        if not chunk_id:
            continue

        scores[
            chunk_id
        ] += (
            1.0
            / (
                RRF_K
                + rank
            )
        )

        documents[
            chunk_id
        ] = item

        retriever_hits[
            chunk_id
        ].append(
            "vector"
        )

    # =========================================
    # BM25 Ranking
    # =========================================

    for rank, item in enumerate(
        bm25_results,
        start=1
    ):

        chunk_id = item.get(
            "id"
        )

        if not chunk_id:
            continue

        scores[
            chunk_id
        ] += (
            1.0
            / (
                RRF_K
                + rank
            )
        )

        if chunk_id not in documents:

            documents[
                chunk_id
            ] = item

        retriever_hits[
            chunk_id
        ].append(
            "bm25"
        )

    # =========================================
    # 4. 根据 RRF 分数排序
    # =========================================

    ranked_ids = sorted(
        scores.keys(),
        key=lambda chunk_id:
            scores[chunk_id],
        reverse=True
    )

    results = []

    for chunk_id in ranked_ids[
        :top_k
    ]:

        item = dict(
            documents[
                chunk_id
            ]
        )

        item[
            "rrf_score"
        ] = scores[
            chunk_id
        ]

        item[
            "retriever_hits"
        ] = retriever_hits[
            chunk_id
        ]

        results.append(
            item
        )

    return results


def hybrid_retrieve(
    query: str,
    top_k: int = 5,
    candidate_k: int = 10,
    filters: dict | None = None,
) -> list[dict]:
    """
    Full Hybrid Retrieval.

    Pipeline:

    Query
      ├── Vector Retrieval
      └── BM25 Retrieval
             ↓
          RRF Fusion
             ↓
        Candidate Top-K
             ↓
          Reranker
             ↓
          Final Top-K
    """

    # =========================================
    # 1. Hybrid Candidate Retrieval
    # =========================================

    candidates = (
        hybrid_retrieve_without_rerank(
            query=query,
            top_k=candidate_k,
            candidate_k=candidate_k,
            filters=filters,
        )
    )

    if not candidates:
        return []

    # =========================================
    # 2. Cross-Encoder Rerank
    # =========================================

    reranked_results = (
        reranker.rerank(
            query=query,
            documents=candidates,
            top_k=top_k,
        )
    )

    return reranked_results
