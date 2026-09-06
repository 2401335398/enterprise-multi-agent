from sentence_transformers import (
    CrossEncoder,
)

from app.rag.config import (
    RERANKER_MODEL,
)


class Reranker:

    def __init__(
        self
    ):

        self.model = (
            CrossEncoder(
                RERANKER_MODEL
            )
        )

    def rerank(
        self,
        query: str,
        documents: list[dict],
        top_k: int = 5,
    ) -> list[dict]:

        if not documents:
            return []

        pairs = [
            [
                query,
                document["text"]
            ]

            for document
            in documents
        ]

        scores = (
            self.model.predict(
                pairs
            )
        )

        ranked = []

        for document, score in zip(
            documents,
            scores
        ):

            item = dict(
                document
            )

            item[
                "rerank_score"
            ] = float(
                score
            )

            ranked.append(
                item
            )

        ranked.sort(
            key=lambda item:
                item[
                    "rerank_score"
                ],
            reverse=True
        )

        return ranked[
            :top_k
        ]


reranker = Reranker()
