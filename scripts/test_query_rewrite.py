import asyncio

from app.rag.query_rewriter import (
    rewrite_query,
)


async def main():

    query = (
        "那个面向制造业的版本"
        "最近加了什么？"
    )

    context = (
        "上一轮讨论的是 "
        "KnowledgeFlow 3.2。"
    )

    rewritten = (
        await rewrite_query(
            query=query,
            conversation_context=context,
        )
    )

    print(
        "\n===== QUERY REWRITE ====="
    )

    print(
        "Original:"
    )

    print(
        query
    )

    print(
        "\nContext:"
    )

    print(
        context
    )

    print(
        "\nRewritten:"
    )

    print(
        rewritten
    )


if __name__ == "__main__":

    asyncio.run(
        main()
    )
