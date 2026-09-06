from app.schemas.policy import (
    ToolPolicy,
    ToolPolicyAction,
)


TOOL_POLICIES = [

    # =========================
    # Local Tools
    # =========================

    ToolPolicy(
        tool_pattern="search",
        action=(
            ToolPolicyAction.ALLOW
        ),
        reason=(
            "Read-only external search."
        ),
    ),

    ToolPolicy(
        tool_pattern="browser",
        action=(
            ToolPolicyAction.ALLOW
        ),
        reason=(
            "Read-only browser access."
        ),
    ),

    ToolPolicy(
        tool_pattern=(
            "document_search"
        ),
        action=(
            ToolPolicyAction.ALLOW
        ),
    ),

    ToolPolicy(
        tool_pattern="calculator",
        action=(
            ToolPolicyAction.ALLOW
        ),
    ),

    # =========================
    # Filesystem MCP
    # =========================

    ToolPolicy(
        tool_pattern=(
            "mcp.filesystem."
            "read_text_file"
        ),
        action=(
            ToolPolicyAction.ALLOW
        ),
        reason=(
            "Read-only filesystem access."
        ),
    ),

    ToolPolicy(
        tool_pattern=(
            "mcp.filesystem."
            "read_file"
        ),
        action=(
            ToolPolicyAction.ALLOW
        ),
    ),

    ToolPolicy(
        tool_pattern=(
            "mcp.filesystem."
            "list_directory"
        ),
        action=(
            ToolPolicyAction.ALLOW
        ),
    ),

    ToolPolicy(
        tool_pattern=(
            "mcp.filesystem."
            "search_files"
        ),
        action=(
            ToolPolicyAction.ALLOW
        ),
    ),

    # 写操作
    ToolPolicy(
        tool_pattern=(
            "mcp.filesystem."
            "write_file"
        ),
        action=(
            ToolPolicyAction.REQUIRE_APPROVAL
        ),
        reason=(
            "Filesystem mutation "
            "requires user approval."
        ),
    ),

    ToolPolicy(
        tool_pattern=(
            "mcp.filesystem."
            "move_file"
        ),
        action=(
            ToolPolicyAction.REQUIRE_APPROVAL
        ),
    ),

    # 默认可以根据需要再补
]
