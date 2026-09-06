from typing import Any

from app.mcp.client import (
    MCPClient,
)


class MCPToolAdapter:
    """
    将 MCP Tool 适配成项目内部
    Generic Tool 接口。
    """

    def __init__(
        self,
        name: str,
        description: str,
        client: MCPClient,
        remote_tool_name: str,
    ):

        self._name = name

        self._description = (
            description
        )

        self.client = client

        self.remote_tool_name = (
            remote_tool_name
        )

    @property
    def name(
        self
    ) -> str:

        return self._name

    @property
    def description(
        self
    ) -> str:

        return self._description

    async def run(
        self,
        **arguments: Any
    ):

        result = (
            await self.client.call_tool(
                tool_name=(
                    self.remote_tool_name
                ),
                arguments=arguments,
            )
        )

        return result
