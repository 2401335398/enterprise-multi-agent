class LLMRuntimeMetrics:

    def __init__(self):

        self.total_calls = 0

        self.total_input_tokens = 0

        self.total_output_tokens = 0

    def record(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ):

        self.total_calls += 1

        self.total_input_tokens += (
            input_tokens
        )

        self.total_output_tokens += (
            output_tokens
        )


llm_metrics = (
    LLMRuntimeMetrics()
)
