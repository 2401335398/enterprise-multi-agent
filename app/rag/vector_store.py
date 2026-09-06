import chromadb

from app.rag.config import (
    CHROMA_DIR,
    COLLECTION_NAME,
)


class VectorStore:

    def __init__(
        self
    ):

        CHROMA_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        self.client = (
            chromadb.PersistentClient(
                path=str(
                    CHROMA_DIR
                )
            )
        )

        self.collection = (
            self.client
            .get_or_create_collection(
                name=(
                    COLLECTION_NAME
                ),

                metadata={
                    "hnsw:space":
                        "cosine"
                },
            )
        )

    def add(
        self,
        ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ):

        self.collection.upsert(
            ids=ids,

            documents=texts,

            embeddings=embeddings,

            metadatas=metadatas,
        )

    def query(
            self,
            embedding: list[float],
            top_k: int,
            where: dict | None = None,
    ):
        kwargs = {
            "query_embeddings": [
                embedding
            ],

            "n_results":
                top_k,

            "include": [
                "documents",
                "metadatas",
                "distances",
            ],
        }

        if where:
            kwargs["where"] = where

        return self.collection.query(
            **kwargs
        )


vector_store = (
    VectorStore()
)
