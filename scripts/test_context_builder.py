from app.rag.context_builder import (
    build_context,
)


results = [
    {
        "text":
            (
                "KnowledgeFlow 3.2 "
                "新增 Manufacturing Copilot。"
            ),

        "metadata": {
            "file_name":
                "product_update.txt",

            "chunk_id":
                "product_update:c0",
        },
    },

    {
        "text":
            (
                "2026 年公司的战略重点是"
                "扩大 KnowledgeFlow "
                "在制造业客户中的市场覆盖。"
            ),

        "metadata": {
            "file_name":
                "company_profile.txt",

            "chunk_id":
                "company_profile:c0",
        },
    },
]


context = build_context(
    results
)


print(
    context
)
