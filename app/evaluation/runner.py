from app.evaluation.dataset import (
    load_rag_eval_dataset,
)

from app.evaluation.retrieval import (
    evaluate_case,
)

from app.rag.retriever import (
    vector_retrieve,
)

from app.rag.hybrid import (
    hybrid_retrieve,
    hybrid_retrieve_without_rerank,
)


def run_retrieval_evaluation():

    dataset = (
        load_rag_eval_dataset()
    )

    all_results = []

    for case in dataset:

        # =========================
        # Vector Only
        # =========================

        vector_results = (
            vector_retrieve(
                query=
                    case.query,

                top_k=5,
            )
        )

        all_results.append(
            evaluate_case(
                case=case,

                results=
                    vector_results,

                retriever_name=
                    "vector",
            )
        )

        # =========================
        # Hybrid
        # =========================

        hybrid_results = (
            hybrid_retrieve_without_rerank(
                query=
                    case.query
            )
        )

        all_results.append(
            evaluate_case(
                case=case,

                results=
                    hybrid_results[
                        :5
                    ],

                retriever_name=
                    "hybrid",
            )
        )

        # =========================
        # Hybrid + Reranker
        # =========================

        rerank_results = (
            hybrid_retrieve(
                query=
                    case.query
            )
        )

        all_results.append(
            evaluate_case(
                case=case,

                results=
                    rerank_results[
                        :5
                    ],

                retriever_name=
                    "hybrid_rerank",
            )
        )

    return all_results
