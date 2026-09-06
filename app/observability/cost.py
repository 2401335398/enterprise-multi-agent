import os


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
) -> float:
    """
    根据环境变量配置的模型价格估算成本。

    价格单位：
    USD / 1M tokens

    环境变量：

    LLM_INPUT_COST_PER_1M_USD
    LLM_OUTPUT_COST_PER_1M_USD
    """

    input_rate = float(
        os.getenv(
            "LLM_INPUT_COST_PER_1M_USD",
            "0"
        )
    )

    output_rate = float(
        os.getenv(
            "LLM_OUTPUT_COST_PER_1M_USD",
            "0"
        )
    )

    input_cost = (
        input_tokens
        / 1_000_000
        * input_rate
    )

    output_cost = (
        output_tokens
        / 1_000_000
        * output_rate
    )

    return (
        input_cost
        + output_cost
    )
