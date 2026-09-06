import asyncio

from app.rag.service import (
    rag_service,
)


async def main():

    result = await rag_service.search(

        query=(
            "KnowledgeFlow "
            "新增了什么功能？"
        ),

        filters={
            "file_name":
                "product_update.txt"
        }
    )

    print(
        "\n===== FILTER ====="
    )

    print(
        result[
            "filters"
        ]
    )

    print(
        "\n===== RESULTS ====="
    )

    for item in result[
        "results"
    ]:

        print(
            "\nfile:",
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


if __name__ == "__main__":

    asyncio.run(
        main()
    )
