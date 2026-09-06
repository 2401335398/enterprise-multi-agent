from app.observability.llm_runtime import (
    tracked_llm_invoke,
)


QUERY_REWRITE_PROMPT = """
你是企业知识库 RAG 系统中的 Query Rewriter。

你的任务是将用户问题改写成适合知识检索的查询。

要求：

1. 保留用户原始意图。
2. 补全明显的指代。
3. 删除无意义的口语表达。
4. 保留产品名、版本号、时间、部门名等关键实体。
5. 不要回答问题。
6. 不要添加用户没有提供或上下文无法确认的事实。
7. 输出一个简洁的检索查询即可。
"""


async def rewrite_query(
    query: str,
    conversation_context: str | None = None
) -> str:

    context = (
        conversation_context
        or "无额外上下文"
    )

    prompt = f"""
用户问题：

{query}

可用上下文：

{context}
"""

    response = await tracked_llm_invoke(
        [
            {
                "role": "system",
                "content":
                    QUERY_REWRITE_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            }
        ]
    )

    rewritten = (
        response.content
        .strip()
    )

    if not rewritten:
        return query

    return rewritten
