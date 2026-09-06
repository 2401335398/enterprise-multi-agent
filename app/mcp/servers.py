from pathlib import Path

from app.mcp.config import (
    MCPServerConfig,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

MCP_WORKSPACE = (
    PROJECT_ROOT
    / "mcp_workspace"
)


MCP_SERVER_CONFIGS = {

    "filesystem":
        MCPServerConfig(
            name="filesystem",

            command="npx.cmd",

            args=[
                "-y",
                (
                    "@modelcontextprotocol/"
                    "server-filesystem"
                ),
                str(
                    MCP_WORKSPACE
                ),
            ],
        )
}
