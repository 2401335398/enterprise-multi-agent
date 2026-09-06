from enum import Enum

from pydantic import BaseModel, Field


class ToolPolicyAction(
    str,
    Enum
):
    ALLOW = "allow"

    REQUIRE_APPROVAL = (
        "require_approval"
    )

    DENY = "deny"


class ToolPolicy(BaseModel):

    tool_pattern: str

    action: ToolPolicyAction

    reason: str = ""

    allowed_agents: list[str] = Field(
        default_factory=list
    )
