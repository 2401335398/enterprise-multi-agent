from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.metrics import runtime_metrics
from app.security.budget import check_token_budget


class TrackedChatModel:

    def __init__(
        self,
        llm: ChatOpenAI
    ):
        self.llm = llm

    async def ainvoke(
        self,
        messages
    ):

        # 演示模式的单请求 token 预算闸门。
        # 全系统的 LLM 调用都走 llm 这个单例，所以这里是唯一咽喉。
        check_token_budget()

        response = await self.llm.ainvoke(
            messages
        )

        usage = getattr(
            response,
            "usage_metadata",
            None
        )

        input_tokens = 0
        output_tokens = 0

        if usage:

            input_tokens = (
                usage.get(
                    "input_tokens",
                    0
                )
            )

            output_tokens = (
                usage.get(
                    "output_tokens",
                    0
                )
            )

        await runtime_metrics.record_llm_call(
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )

        return response


def create_llm():

    base_llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=0
    )

    return TrackedChatModel(
        base_llm
    )


llm = create_llm()


# ============================================================
# 注意：以下 TrackedChatModel 是**死代码**。
#
# `llm = create_llm()` 在上面执行时绑定的是第一个定义，
# 所以全系统实际使用的是上面那个类；这里重新定义只是把模块里的
# 名字遮蔽掉，不会影响已经创建好的 llm 单例。
#
# 已实测确认：
#   llm.__class__ is TrackedChatModel  ->  False
#   hasattr(llm, "with_structured_output")  ->  False
#
# 全仓库没有任何地方调用 with_structured_output，所以这条路径从未被执行。
# 安全相关的钩子（token 预算）必须加在上面那个类里。
# 保留是因为删除会改变 TrackedChatModel 这个名字的含义，
# 超出本次改动范围。
# ============================================================

class TrackedChatModel:

    def __init__(self, llm):
        self.llm = llm

    def with_structured_output(
        self,
        schema
    ):

        return TrackedChatModel(
            self.llm.with_structured_output(
                schema
            )
        )

    async def ainvoke(
        self,
        messages
    ):

        response = await self.llm.ainvoke(
            messages
        )

        usage = getattr(
            response,
            "usage_metadata",
            None
        )

        input_tokens = 0
        output_tokens = 0

        if usage:

            input_tokens = usage.get(
                "input_tokens",
                0
            )

            output_tokens = usage.get(
                "output_tokens",
                0
            )

        await runtime_metrics.record_llm_call(
            input_tokens,
            output_tokens
        )

        return response


