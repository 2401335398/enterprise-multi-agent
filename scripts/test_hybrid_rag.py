from app.rag.hybrid import (
    hybrid_retrieve,
)


queries = [
    "KnowledgeFlow 3.2 "
    "新增了什么功能？"
]


for query in queries:

    print(
        "\n=============================="
    )

    print(
        "QUERY:",
        query
    )

    print(
        "=============================="
    )

    results = (
        hybrid_retrieve(
            query=query,
            top_k=5
        )
    )

    for index, item in enumerate(
        results,
        start=1
    ):

        print(
            f"\nRank {index}"
        )

        print(
            "RRF:",
            item[
                "rrf_score"
            ]
        )

        print(
            "source:",
            item[
                "metadata"
            ].get(
                "file_name"
            )
        )

        print(
            "text:",
            item["text"]
        )
