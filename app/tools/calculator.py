from app.tools.base import BaseTool


class CalculatorTool(BaseTool):

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "执行简单数值计算。"

    async def run(
        self,
        expression: str
    ) -> dict:

        try:

            result = eval(
                expression,
                {"__builtins__": {}},
                {}
            )

            return {
                "expression":
                    expression,

                "result":
                    result
            }

        except Exception as exc:

            return {
                "expression":
                    expression,

                "error":
                    str(exc)
            }
