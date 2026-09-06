from dataclasses import dataclass, field
from asyncio import Lock


@dataclass
class RuntimeMetrics:

    llm_calls: int = 0

    input_tokens: int = 0

    output_tokens: int = 0

    retries: int = 0

    lock: Lock = field(
        default_factory=Lock
    )

    async def record_llm_call(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0
    ):
        async with self.lock:

            self.llm_calls += 1

            self.input_tokens += (
                input_tokens
            )

            self.output_tokens += (
                output_tokens
            )

    async def record_retry(self):
        async with self.lock:
            self.retries += 1


runtime_metrics = RuntimeMetrics()
