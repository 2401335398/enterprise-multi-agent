"""
单次请求的 Token 预算。

挂载点：app/core/llm.py 的 TrackedChatModel.ainvoke —— 已验证全系统的
LLM 调用（Supervisor + 全部 Agent + memory extractor/consolidator +
RAG query rewriter）都经过这个单例，所以一处即可覆盖整个 DAG。

计数来源：app/observability/context.py 的 WorkflowObservabilityContext，
它是每个 workflow 一个的共享可变对象，asyncio.gather 的并发子任务
写进去的 token 数都能被这里读到。

精度说明：本检查发生在**每次 LLM 调用之前**，因此最多超支
"一次 LLM 调用"的量（实测约 2–4k token）。要做到绝对精确只能
在流式回包里中断，复杂度不值得。
"""

from __future__ import annotations

from app.core.config import settings
from app.observability.context import (
    get_observability_context,
)


class TokenBudgetExceeded(RuntimeError):
    """本次请求的 token 预算已用尽。"""


def tokens_used_in_current_request() -> int:
    """当前 workflow 已消耗的 token 总数（输入 + 输出）。"""

    context = get_observability_context()

    if context is None:
        return 0

    return (
        context.input_tokens
        + context.output_tokens
    )


def check_token_budget() -> None:
    """
    超预算就抛。非演示模式、或未配置上限（<=0）时不做任何事。
    """

    if not settings.is_demo:
        return

    limit = settings.demo_max_tokens_per_request

    if limit <= 0:
        return

    used = tokens_used_in_current_request()

    if used >= limit:

        raise TokenBudgetExceeded(
            "Token budget exceeded for this request: "
            f"used {used}, limit {limit}. "
            "本次请求已中断。"
        )
