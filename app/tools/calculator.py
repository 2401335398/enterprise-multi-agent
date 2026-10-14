"""
数值计算工具。

原先用 eval(expr, {"__builtins__": {}}, {})。屏蔽 builtins 并不能拦住
逃逸 —— 例如 `().__class__.__base__.__subclasses__()` 全程不需要
builtins 就能拿到任意类，是公认的 eval 沙箱逃逸路径。

现在改成 AST 白名单：只解析字面量数字与四则运算，其余一律拒绝。
对合法算术的行为与原来完全一致（返回值、错误信息结构都不变）。
"""

import ast
import operator

from app.tools.base import BaseTool


# 允许的二元运算符
_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# 允许的一元运算符
_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


class _ExpressionRejected(ValueError):
    """表达式包含不被允许的语法。"""


def _evaluate_node(node: ast.AST) -> float | int:

    # ---- 数字字面量 ----
    if isinstance(node, ast.Constant):

        if isinstance(node.value, bool) or not isinstance(
            node.value, (int, float)
        ):
            raise _ExpressionRejected(
                f"只允许数字字面量，收到 {type(node.value).__name__}"
            )

        return node.value

    # ---- 二元运算：a + b ----
    if isinstance(node, ast.BinOp):

        handler = _BINARY_OPERATORS.get(type(node.op))

        if handler is None:
            raise _ExpressionRejected(
                f"不允许的运算符: {type(node.op).__name__}"
            )

        left = _evaluate_node(node.left)
        right = _evaluate_node(node.right)

        # 幂运算限制规模，避免 9**9**9 这类把进程算死
        if isinstance(node.op, ast.Pow):
            if abs(right) > 64 or abs(left) > 1e9:
                raise _ExpressionRejected("幂运算指数过大")

        return handler(left, right)

    # ---- 一元运算：-a ----
    if isinstance(node, ast.UnaryOp):

        handler = _UNARY_OPERATORS.get(type(node.op))

        if handler is None:
            raise _ExpressionRejected(
                f"不允许的一元运算符: {type(node.op).__name__}"
            )

        return handler(_evaluate_node(node.operand))

    raise _ExpressionRejected(
        f"表达式中不允许出现 {type(node).__name__}"
    )


def safe_eval_expression(expression: str) -> float | int:
    """
    只求值纯算术表达式。任何函数调用、属性访问、下标、变量名
    都会抛 _ExpressionRejected。
    """

    if not expression or not expression.strip():
        raise _ExpressionRejected("表达式为空")

    try:
        tree = ast.parse(expression, mode="eval")

    except SyntaxError as exc:
        raise _ExpressionRejected(f"语法错误: {exc.msg}") from exc

    return _evaluate_node(tree.body)


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

            result = safe_eval_expression(
                expression
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
