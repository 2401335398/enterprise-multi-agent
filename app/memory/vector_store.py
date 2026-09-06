import chromadb
from pathlib import Path

from app.rag.embeddings import (
    embedding_model,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

MEMORY_CHROMA_DIR = (
    PROJECT_ROOT
    / "data"
    / "memory_chroma"
)


class SemanticMemoryStore:

    def __init__(
        self
    ):

        MEMORY_CHROMA_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        self.client = (
            chromadb.PersistentClient(
                path=str(
                    MEMORY_CHROMA_DIR
                )
            )
        )

        self.collection = (
            self.client
            .get_or_create_collection(
                name="semantic_memory",
                metadata={
                    "hnsw:space":
                        "cosine"
                }
            )
        )

    def add(
        self,
        memory_id: str,
        session_id: str,
        content: str,
        metadata: dict,
    ) -> None:

        embedding = (
            embedding_model
            .embed_query(
                content
            )
        )

        vector_metadata = dict(
            metadata
        )

        vector_metadata[
            "session_id"
        ] = session_id

        self.collection.upsert(
            ids=[
                memory_id
            ],

            documents=[
                content
            ],

            embeddings=[
                embedding
            ],

            metadatas=[
                vector_metadata
            ],
        )

    def search(
        self,
        session_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:

        embedding = (
            embedding_model
            .embed_query(
                query
            )
        )

        result = (
            self.collection.query(
                query_embeddings=[
                    embedding
                ],
                n_results=top_k,
                where={
                    "session_id":
                        session_id
                },
                include=[
                    "documents",
                    "metadatas",
                    "distances",
                ]
            )
        )

        ids = (
            result.get(
                "ids",
                [[]]
            )[0]
        )

        documents = (
            result.get(
                "documents",
                [[]]
            )[0]
        )

        metadatas = (
            result.get(
                "metadatas",
                [[]]
            )[0]
        )

        distances = (
            result.get(
                "distances",
                [[]]
            )[0]
        )

        memories = []

        for (
                memory_id,
                document,
                metadata,
                distance
        ) in zip(
            ids,
            documents,
            metadatas,
            distances
        ):
            memories.append(
                {
                    "id":
                        memory_id,

                    "content":
                        document,

                    "metadata":
                        metadata,

                    "score":
                        1 - distance,
                }
            )

        return memories

    def delete(
            self,
            memory_id: str,
    ) -> None:
        self.collection.delete(
            ids=[
                memory_id
            ]
        )


semantic_memory_store = (
    SemanticMemoryStore()
)
