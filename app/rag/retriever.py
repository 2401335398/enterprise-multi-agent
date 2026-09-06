from app.rag.config import (
    TOP_K,
)

from app.rag.embeddings import (
    embedding_model,
)

from app.rag.vector_store import (
    vector_store,
)


def vector_retrieve(
    query: str,
    top_k: int = TOP_K,
    filters: dict | None = None,
) -> list[dict]:

    query_embedding = (
        embedding_model
        .embed_query(
            query
        )
    )

    raw = vector_store.query(
        embedding=query_embedding,
        top_k=top_k,
        where=filters,
    )

    documents = (
        raw.get(
            "documents",
            [[]]
        )[0]
    )

    metadatas = (
        raw.get(
            "metadatas",
            [[]]
        )[0]
    )

    distances = (
        raw.get(
            "distances",
            [[]]
        )[0]
    )

    results = []

    for (
        document,
        metadata,
        distance
    ) in zip(
        documents,
        metadatas,
        distances
    ):
        results.append(
            {
                "id":
                    metadata.get(
                        "chunk_id"
                    ),

                "text":
                    document,

                "metadata":
                    metadata,

                "vector_score":
                    1 - distance,
            }
        )

    return results
