from app.rag.retriever import (
    retrieve,
)


query = (
    "公司的主要产品是什么？"
)


results = retrieve(
    query
)


print(
    "\n===== RAG RESULTS ====="
)


for index, result in enumerate(
    results,
    start=1
):

    print(
        f"\nResult {index}"
    )

    print(
        "score:",
        result["score"]
    )

    print(
        "source:",
        result[
            "metadata"
        ].get(
            "file_name"
        )
    )

    print(
        "text:",
        result["text"]
    )
