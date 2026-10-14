from fnmatch import fnmatch

from app.core.config import settings

from app.schemas.policy import (
    ToolPolicy,
    ToolPolicyAction,
)

from app.tools.policies import (
    TOOL_POLICIES,
)


# ============================================================
# 演示模式的硬拒绝表
#
# 这些能力在公网演示里一律不允许，**优先级高于 TOOL_POLICIES 里的
# 任何配置** —— 即使某条策略写了 ALLOW 也照样被拒。
#
# 放在这里而不是改 policies.py，是为了让"演示模式禁了什么"一目了然，
# 且 dev 模式的策略表保持原样、零改动。
#
# 覆盖范围：
#   - filesystem 写 / 移动 / 创建 / 删除（未登记的走默认 DENY，这里显式列出）
#   - filesystem 读取（演示不需要读宿主目录）
#   - 任何 shell / 命令执行类工具
#   - calculator：用 eval 实现，屏蔽 builtins 仍可用 __subclasses__ 逃逸
# ============================================================

DEMO_DENY_PATTERNS: tuple[str, ...] = (
    "mcp.filesystem.*",
    "mcp.*shell*",
    "mcp.*exec*",
    "mcp.*command*",
    "calculator",
)


def _demo_denied(tool_name: str) -> bool:

    return any(
        fnmatch(tool_name, pattern)
        for pattern in DEMO_DENY_PATTERNS
    )


class ToolPolicyEngine:

    def __init__(
        self,
        policies: list[ToolPolicy]
    ):
        self.policies = policies

    def evaluate(
        self,
        tool_name: str,
        agent_name: str | None = None
    ) -> ToolPolicy:

        # ---- 演示模式硬拒绝：先于一切配置 ----
        if settings.is_demo and _demo_denied(tool_name):

            return ToolPolicy(
                tool_pattern=tool_name,
                action=ToolPolicyAction.DENY,
                reason=(
                    "Disabled in demo mode: "
                    "high-risk tool."
                ),
            )

        for policy in self.policies:

            if not fnmatch(
                tool_name,
                policy.tool_pattern
            ):
                continue

            if (
                policy.allowed_agents
                and
                agent_name
                not in
                policy.allowed_agents
            ):
                continue

            return policy

        # =====================
        # 默认拒绝
        # =====================

        return ToolPolicy(
            tool_pattern=tool_name,

            action=(
                ToolPolicyAction.DENY
            ),

            reason=(
                "No matching tool policy."
            ),
        )


tool_policy_engine = (
    ToolPolicyEngine(
        TOOL_POLICIES
    )
)
