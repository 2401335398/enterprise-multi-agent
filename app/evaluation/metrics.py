from collections import defaultdict

from app.evaluation.schema import (
    RetrievalEvalResult,
)


def summarize_results(
    results: list[
        RetrievalEvalResult
    ]
) -> dict:

    grouped = defaultdict(
        list
    )

    for result in results:

        grouped[
            result.retriever
        ].append(
            result
        )

    summary = {}

    for retriever, items in (
        grouped.items()
    ):

        count = len(
            items
        )

        if count == 0:
            continue

        summary[
            retriever
        ] = {

            "queries":
                count,

            "hit@1":
                sum(
                    item.hit_at_1
                    for item in items
                )
                / count,

            "hit@3":
                sum(
                    item.hit_at_3
                    for item in items
                )
                / count,

            "hit@5":
                sum(
                    item.hit_at_5
                    for item in items
                )
                / count,

            "mrr":
                sum(
                    item.reciprocal_rank
                    for item in items
                )
                / count,
        }

    return summary
