import json
import re

from app.observability.llm_runtime import (
    tracked_llm_invoke,
)

MEMORY_EXTRACTION_PROMPT = """
你是企业级 Agent 系统中的 Memory Extractor。

判断当前用户消息中是否包含未来可能持续有用的信息。

适合保存为 Semantic Memory 的内容包括：

- 用户明确的长期偏好
- 项目固定约束
- 后续任务应持续遵守的规则
- 已明确确认的重要项目事实
- 长期目标
- 反复需要使用的背景

不应该保存：

- 普通问候
- 临时问题
- 一次性报错
- “继续”“好的”等无信息消息
- 未确认的推测

只输出 JSON：

{
  "should_store": true,
  "memory": "精炼后的稳定事实"
}

或者：

{
  "should_store": false,
  "memory": null
}
"""


def _extract_json(
    text: str
) -> dict:

    text = text.strip()

    if text.startswith(
        "```"
    ):

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

    start = text.find(
        "{"
    )

    end = text.rfind(
        "}"
    )

    if (
        start == -1
        or end == -1
    ):

        return {
            "should_store":
                False,

            "memory":
                None
        }

    return json.loads(
        text[
            start:
            end + 1
        ]
    )


async def extract_semantic_memory(
    user_message: str
) -> str | None:

    response = (
        await tracked_llm_invoke(
            [
                {
                    "role":
                        "system",

                    "content":
                        MEMORY_EXTRACTION_PROMPT,
                },
                {
                    "role":
                        "user",

                    "content":
                        user_message,
                }
            ],
            agent_name="memory",
            component="memory_extraction",
        )
    )

    try:

        data = _extract_json(
            response.content
        )

    except Exception:

        return None

    if not data.get(
        "should_store"
    ):
        return None

    memory = data.get(
        "memory"
    )

    if not memory:
        return None

    return str(
        memory
    ).strip()
