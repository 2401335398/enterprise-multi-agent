"""
要求 3 / 8：演示模式下禁用文件写入、命令执行等高风险工具，
且在**实际执行入口**强制校验。

执行入口是 app/tools/executor.py::execute_tool_call，全系统唯一的
工具执行咽喉。这里的关键断言不是"返回值是失败的"，
而是"工具实现根本没被调用" —— 只看 success=False 是不够的，
DENY 之后仍然调用工具、只是把结果丢掉，同样会产生副作用。
"""

from __future__ import annotations

import asyncio

import pytest

from app.schemas.tool import ToolCall
from app.tools import executor as executor_module
from app.tools.executor import execute_tool_call


def run_async(coro):
    return asyncio.run(coro)


# 命中演示模式硬拒绝表的名字。故意包含两类：
#   - 写操作（原策略是 REQUIRE_APPROVAL）
#   - 读操作（原策略是 ALLOW）
#       —— 用来证明拒绝表**优先级高于 TOOL_POLICIES**，
#          而不是"恰好这些工具本来就被拒"
DEMO_DENIED_TOOL_NAMES = [
    "mcp.filesystem.write_file",
    "mcp.filesystem.move_file",
    "mcp.filesystem.read_text_file",
    "mcp.filesystem.delete_everything",
    "mcp.filesystem.read_multiple_files",
]

# 不在拒绝表里、靠"未登记即默认 DENY"兜住的名字。
# 证明即使将来新增了 MCP server，新工具也不会被自动放行。
# 这类名字的拒绝理由不会是"demo"（走的是默认拒绝那条分支）。
DEMO_UNKNOWN_TOOL_NAMES = [
    "shell.exec",
    "system.command_runner",
    "mcp.bash.run",
]


@pytest.fixture
def spy_get_tool(monkeypatch):
    """
    任何一次 registry 查找都记下来。
    DENY 是在查找之前返回的，所以这里必须保持为空。
    """

    looked_up: list[str] = []

    def fake_get_tool(name):
        looked_up.append(name)
        raise AssertionError(
            f"工具 {name} 在演示模式下不应该被查表/执行"
        )

    monkeypatch.setattr(
        executor_module, "get_tool", fake_get_tool
    )

    return looked_up


# ============================================================
# 1. 演示模式：拒绝且不执行
# ============================================================

@pytest.mark.parametrize(
    "tool_name", DEMO_DENIED_TOOL_NAMES
)
def test_demo_denies_dangerous_tool_without_executing(
    demo_mode, spy_get_tool, tool_name
):
    result = run_async(
        execute_tool_call(
            ToolCall(
                tool=tool_name,
                arguments={"path": "/etc/passwd"},
            ),
            agent_name="research_agent",
        )
    )

    assert result.success is False
    assert result.policy_action == "deny"
    assert "demo" in (result.error or "").lower()

    # 决定性断言：工具实现根本没被碰过
    assert spy_get_tool == []


@pytest.mark.parametrize(
    "tool_name", DEMO_UNKNOWN_TOOL_NAMES
)
def test_unknown_dangerous_tool_is_denied_by_default(
    demo_mode, spy_get_tool, tool_name
):
    """
    拒绝表没覆盖到的名字，靠"未登记即默认 DENY"兜底。
    两层任何一层失效，都会被这条或上一条测出来。
    """

    result = run_async(
        execute_tool_call(
            ToolCall(tool=tool_name, arguments={}),
            agent_name="research_agent",
        )
    )

    assert result.success is False
    assert result.policy_action == "deny"
    assert spy_get_tool == []


def test_demo_denies_calculator(demo_mode, spy_get_tool):
    """
    calculator 在 dev 模式下是 ALLOW，且真的在 registry 里。
    演示模式必须把它也挡住 —— 它用 eval 实现，
    屏蔽 builtins 并不能阻止 __subclasses__ 逃逸。
    """

    result = run_async(
        execute_tool_call(
            ToolCall(
                tool="calculator",
                arguments={"expression": "1+1"},
            )
        )
    )

    assert result.success is False
    assert result.policy_action == "deny"
    assert spy_get_tool == []


def test_demo_deny_beats_allow_policy(demo_mode):
    """
    直接查策略引擎：这条 SQL 的 ALLOW 是写在 TOOL_POLICIES 里的，
    演示模式的拒绝表必须压过它。
    """

    from app.tools.policy import tool_policy_engine

    policy = tool_policy_engine.evaluate(
        "mcp.filesystem.read_text_file"
    )

    assert policy.action.value == "deny"


def test_demo_still_allows_read_only_local_tools(demo_mode):
    """
    别一刀切。演示要能跑：搜索与文档检索必须保留，
    否则整个 demo 只剩寒暄。
    """

    from app.tools.policy import tool_policy_engine

    for name in ("search", "browser", "document_search"):

        assert (
            tool_policy_engine.evaluate(name).action.value
            == "allow"
        ), name


# ============================================================
# 2. dev 模式：策略表原样，零回归
# ============================================================

def test_dev_keeps_original_policy_for_write(dev_mode):
    from app.tools.policy import tool_policy_engine

    policy = tool_policy_engine.evaluate(
        "mcp.filesystem.write_file"
    )

    assert policy.action.value == "require_approval"


def test_dev_keeps_original_policy_for_read(dev_mode):
    from app.tools.policy import tool_policy_engine

    policy = tool_policy_engine.evaluate(
        "mcp.filesystem.read_text_file"
    )

    assert policy.action.value == "allow"


def test_dev_calculator_still_works(dev_mode):
    """正向对照：dev 模式下 calculator 真的会执行。"""

    result = run_async(
        execute_tool_call(
            ToolCall(
                tool="calculator",
                arguments={"expression": "2*(3+4)"},
            )
        )
    )

    assert result.success is True
    assert result.result["result"] == 14


def test_unknown_tool_falls_through_to_default_deny(dev_mode):
    result = run_async(
        execute_tool_call(
            ToolCall(tool="totally.unknown.tool")
        )
    )

    assert result.success is False
    assert result.policy_action == "deny"


# ============================================================
# 3. calculator 的 eval 替换
#
# 与演示模式无关，但它是一个真实的代码执行面：
# 原来用 eval(expr, {"__builtins__": {}}, {})，
# 屏蔽 builtins 拦不住 __subclasses__ 这类逃逸。
# ============================================================

ESCAPE_PAYLOADS = [
    "().__class__.__base__.__subclasses__()",
    "__import__('os').system('echo pwned')",
    "open('/etc/passwd').read()",
    "[c for c in ().__class__.__base__.__subclasses__()]",
    "1 if True else 2",          # 布尔字面量
    "lambda: 1",
    "x + 1",                     # 未定义变量
    "'a' * 3",                   # 字符串
]


@pytest.mark.parametrize("payload", ESCAPE_PAYLOADS)
def test_calculator_rejects_non_arithmetic(payload):
    from app.tools.calculator import (
        safe_eval_expression,
    )

    with pytest.raises(Exception):
        safe_eval_expression(payload)


def test_calculator_result_shape_unchanged(dev_mode):
    """合法算术的行为必须与替换前完全一致（含错误结构）。"""

    result = run_async(
        execute_tool_call(
            ToolCall(
                tool="calculator",
                arguments={"expression": "10 % 3"},
            )
        )
    )

    assert result.success is True
    assert result.result == {
        "expression": "10 % 3",
        "result": 1,
    }


def test_calculator_error_shape_unchanged(dev_mode):
    result = run_async(
        execute_tool_call(
            ToolCall(
                tool="calculator",
                arguments={"expression": "1+"},
            )
        )
    )

    assert result.success is True
    assert "error" in result.result
    assert result.result["expression"] == "1+"


def test_calculator_blocks_runaway_power():
    from app.tools.calculator import (
        safe_eval_expression,
    )

    with pytest.raises(Exception):
        safe_eval_expression("9**9**9")


def test_calculator_allows_normal_power():
    from app.tools.calculator import (
        safe_eval_expression,
    )

    assert safe_eval_expression("2**10") == 1024
