from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.metrics import runtime_metrics


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


