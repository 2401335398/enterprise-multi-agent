import asyncio

from app.rag.service import (
    rag_service,
)


async def main():

    result = (
        await rag_service.search(
            query=(
                "KnowledgeFlow 3.2 "
                "增加了什么功能？"
            )
        )
    )

    print(
        "\n===== ORIGINAL ====="
    )

    print(
        result[
            "original_query"
        ]
    )

    print(
        "\n===== REWRITTEN ====="
    )

    print(
        result[
            "rewritten_query"
        ]
    )

    print(
        "\n===== RESULTS ====="
    )

    for index, item in enumerate(
        result["results"],
        start=1
    ):

        print(
            f"\nResult {index}"
        )

        print(
            "file:",
            item[
                "metadata"
            ].get(
                "file_name"
            )
        )

        print(
            "rerank:",
            item.get(
                "rerank_score"
            )
        )

        print(
            "text:",
            item["text"]
        )

    print(
        "\n===== CONTEXT ====="
    )

    print(
        result[
            "context"
        ]
    )


if __name__ == "__main__":

    asyncio.run(
        main()
    )
