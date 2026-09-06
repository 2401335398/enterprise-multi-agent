import jieba

from rank_bm25 import (
    BM25Okapi,
)

from app.rag.chunker import (
    chunk_documents,
)

from app.rag.loader import (
    load_directory,
)

from app.rag.config import (
    KNOWLEDGE_BASE_DIR,
)


def tokenize(
    text: str
) -> list[str]:

    return [
        token.strip()
        for token in jieba.cut(
            text.lower()
        )
        if token.strip()
    ]


class BM25Retriever:

    def __init__(
        self
    ):

        self.chunks: list[dict] = []

        self.bm25: (
            BM25Okapi | None
        ) = None

        self._build()

    def _build(
        self
    ):

        documents = (
            load_directory(
                KNOWLEDGE_BASE_DIR
            )
        )

        self.chunks = (
            chunk_documents(
                documents
            )
        )

        corpus = [
            tokenize(
                chunk["text"]
            )
            for chunk
            in self.chunks
        ]

        if corpus:

            self.bm25 = (
                BM25Okapi(
                    corpus
                )
            )

    def search(
            self,
            query: str,
            top_k: int = 10,
            filters: dict | None = None,
    ) -> list[dict]:

        if (
            self.bm25 is None
            or not self.chunks
        ):

            return []

        query_tokens = (
            tokenize(
                query
            )
        )

        scores = (
            self.bm25.get_scores(
                query_tokens
            )
        )

        ranked = sorted(
            enumerate(
                scores
            ),
            key=lambda item:
                item[1],
            reverse=True
        )

        results = []

        for index, score in ranked[
            :top_k
        ]:

            chunk = (
                self.chunks[index]
            )

            results.append(
                {
                    "id":
                        chunk["id"],

                    "text":
                        chunk["text"],

                    "metadata":
                        chunk[
                            "metadata"
                        ],

                    "bm25_score":
                        float(score),
                }
            )

        return results

    def metadata_matches(
            metadata: dict,
            filters: dict
    ) -> bool:

        for key, value in (
                filters.items()
        ):

            if metadata.get(
                    key
            ) != value:
                return False

        return True


bm25_retriever = (
    BM25Retriever()
)
