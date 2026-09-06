from pprint import pprint

from app.evaluation.metrics import (
    summarize_results,
)

from app.evaluation.runner import (
    run_retrieval_evaluation,
)


results = (
    run_retrieval_evaluation()
)


summary = (
    summarize_results(
        results
    )
)


print(
    "\n===== RAG EVALUATION =====\n"
)


pprint(
    summary
)


print(
    "\n===== FAILED CASES ====="
)


for result in results:

    if not result.hit_at_5:

        print(
            "\nRetriever:",
            result.retriever
        )

        print(
            "Case:",
            result.case_id
        )

        print(
            "Query:",
            result.query
        )

        print(
            "Retrieved:",
            result.retrieved_sources
        )
