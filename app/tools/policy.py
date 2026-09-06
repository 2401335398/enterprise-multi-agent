from fnmatch import fnmatch

from app.schemas.policy import (
    ToolPolicy,
    ToolPolicyAction,
)

from app.tools.policies import (
    TOOL_POLICIES,
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
