import json
import re

from app.observability.llm_runtime import (
    tracked_llm_invoke,
)


MEMORY_CONSOLIDATION_PROMPT = """
你是企业级 Multi-Agent 系统中的 Memory Consolidator。

你的任务是判断一条新的 Candidate Memory
应该如何与已有 Semantic Memory 合并。

允许的 action：

ADD
表示这是新的、有价值的信息，应该新增。

UPDATE
表示 Candidate Memory 修正、覆盖或更新了一条已有 Memory。

SKIP
表示 Candidate Memory 与已有 Memory 基本重复，
没有必要再次保存。

DELETE
表示用户明确取消、撤销或废弃了一条已有 Memory。


判断原则：

1. 新信息比旧信息优先。

2. 语义重复时使用 SKIP。

3. 如果新信息改变了旧约束或旧事实，
使用 UPDATE。

4. 只有用户明确表示取消某项信息时，
才使用 DELETE。

5. 如果没有相关已有 Memory，
使用 ADD。

6. 不要凭空创造用户没有表达的信息。

7. 只输出 JSON，不要 Markdown。


输出格式：

{
  "action": "ADD",
  "target_memory_id": null,
  "memory": "最终应该保存的记忆",
  "reason": "没有发现重复或冲突的已有记忆"
}

UPDATE 示例：

{
  "action": "UPDATE",
  "target_memory_id": "memory-id",
  "memory": "更新后的最终记忆",
  "reason": "新信息修改了已有项目约束"
}

SKIP 示例：

{
  "action": "SKIP",
  "target_memory_id": "memory-id",
  "memory": null,
  "reason": "与已有记忆语义重复"
}

DELETE 示例：

{
  "action": "DELETE",
  "target_memory_id": "memory-id",
  "memory": null,
  "reason": "用户明确取消了已有约束"
}
"""


def _extract_json(
    text: str
) -> dict:

    if not text:
        raise ValueError(
            "Memory Consolidator returned empty output."
        )

    text = text.strip()

    if text.startswith("```"):

        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text
        )

        text = re.sub(
            r"\s*```$",
            "",
            text
        )

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:

        raise ValueError(
            "No JSON object found in "
            "Memory Consolidator output."
        )

    return json.loads(
        text[start:end + 1]
    )


async def consolidate_memory(
    candidate_memory: str,
    existing_memories: list[dict],
) -> dict:

    if not existing_memories:

        return {
            "action":
                "ADD",

            "target_memory_id":
                None,

            "memory":
                candidate_memory,

            "reason":
                "No related semantic memory exists.",
        }

    existing_text = "\n".join(
        [
            (
                f"ID: {memory['id']}\n"
                f"Memory: {memory['content']}\n"
                f"Similarity: "
                f"{memory.get('score', 0):.4f}"
            )
            for memory
            in existing_memories
        ]
    )

    user_content = f"""
Candidate Memory:

{candidate_memory}


Existing Related Memories:

{existing_text}
"""

    response = await tracked_llm_invoke(
        [
            {
                "role":
                    "system",

                "content":
                    MEMORY_CONSOLIDATION_PROMPT,
            },
            {
                "role":
                    "user",

                "content":
                    user_content,
            }
        ]
    )

    try:

        data = _extract_json(
            response.content
        )

    except Exception as exc:

        # Consolidation 失败时宁可不污染 Memory。
        return {
            "action":
                "SKIP",

            "target_memory_id":
                None,

            "memory":
                None,

            "reason":
                f"Consolidation failed: {exc}",
        }

    action = str(
        data.get(
            "action",
            "SKIP"
        )
    ).upper()

    if action not in {
        "ADD",
        "UPDATE",
        "SKIP",
        "DELETE",
    }:

        action = "SKIP"

    data["action"] = action

    return data
