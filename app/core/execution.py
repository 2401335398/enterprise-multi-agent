from dataclasses import dataclass


@dataclass
class ExecutionMetrics:

    llm_calls: int = 0

    input_tokens: int = 0

    output_tokens: int = 0

    retries: int = 0
