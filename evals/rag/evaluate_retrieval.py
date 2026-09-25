import json
from pathlib import Path

from app.rag.bm25 import bm25_retriever
from app.rag.hybrid import (
    hybrid_retrieve,
    hybrid_retrieve_without_rerank,
)
from app.rag.retriever import vector_retrieve
STRATEGIES = {
    "Dense": lambda query: vector_retrieve(
        query,
        top_k=TOP_K,
    ),
    "BM25": lambda query: bm25_retriever.search(
        query,
        top_k=TOP_K,
    ),
    "Hybrid RRF": lambda query: hybrid_retrieve_without_rerank(
        query,
        top_k=TOP_K,
    ),
    "Hybrid + Reranker": lambda query: hybrid_retrieve(
        query,
        top_k=TOP_K,
    ),
}



DATASET_PATH = (
    Path(__file__).parent
    / "datasets"
    / "retrieval_cases.json"
)

TOP_K = 5


def load_cases() -> list[dict]:
    with DATASET_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def is_relevant(
    result: dict,
    case: dict,
) -> bool:
    metadata = result.get("metadata", {})

    file_name = metadata.get("file_name")
    page = metadata.get("page")

    return (
        file_name == case["expected_document"]
        and page in case["relevant_pages"]
    )


def evaluate_case(
    case: dict,
    retrieve_fn,
) -> dict:
    results = retrieve_fn(
        case["question"]
    )

    first_relevant_rank = None

    for rank, result in enumerate(
        results,
        start=1,
    ):
        if is_relevant(result, case):
            first_relevant_rank = rank
            break

    return {
        "id": case["id"],
        "first_relevant_rank": first_relevant_rank,
        "hit@1": first_relevant_rank == 1,
        "hit@3": (
            first_relevant_rank is not None
            and first_relevant_rank <= 3
        ),
        "hit@5": (
            first_relevant_rank is not None
            and first_relevant_rank <= 5
        ),
        "mrr": (
            1 / first_relevant_rank
            if first_relevant_rank
            else 0.0
        ),
    }



def main():
    cases = load_cases()

    positive_cases = [
        case
        for case in cases
        if case["question_type"] != "negative"
    ]

    print(
        f"Positive retrieval cases: "
        f"{len(positive_cases)}"
    )

    print(
        "Negative/no-answer cases:",
        len(cases) - len(positive_cases),
    )

    all_summaries = []

    for strategy_name, retrieve_fn in (
        STRATEGIES.items()
    ):
        print(
            f"\n=== {strategy_name} ==="
        )

        results = []

        for case in positive_cases:
            result = evaluate_case(
                case,
                retrieve_fn,
            )

            results.append(result)

            rank = result[
                "first_relevant_rank"
            ]

            print(
                f"{result['id']}: "
                f"rank={rank} | "
                f"H@1={int(result['hit@1'])} "
                f"H@3={int(result['hit@3'])} "
                f"H@5={int(result['hit@5'])} "
                f"MRR={result['mrr']:.3f}"
            )

        count = len(results)

        summary = {
            "strategy": strategy_name,
            "hit@1": sum(
                result["hit@1"]
                for result in results
            ) / count,
            "hit@3": sum(
                result["hit@3"]
                for result in results
            ) / count,
            "hit@5": sum(
                result["hit@5"]
                for result in results
            ) / count,
            "mrr": sum(
                result["mrr"]
                for result in results
            ) / count,
        }

        all_summaries.append(summary)

    print(
        "\n=== Retrieval Evaluation Summary ==="
    )

    print(
        f"{'Strategy':<22}"
        f"{'Hit@1':>8}"
        f"{'Hit@3':>8}"
        f"{'Hit@5':>8}"
        f"{'MRR':>8}"
    )

    for summary in all_summaries:
        print(
            f"{summary['strategy']:<22}"
            f"{summary['hit@1']:>8.3f}"
            f"{summary['hit@3']:>8.3f}"
            f"{summary['hit@5']:>8.3f}"
            f"{summary['mrr']:>8.3f}"
        )


if __name__ == "__main__":
    main()




