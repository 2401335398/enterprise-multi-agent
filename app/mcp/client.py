from contextlib import AsyncExitStack
from typing import Any

from mcp import (
    ClientSession,
    StdioServerParameters,
)

from mcp.client.stdio import (
    stdio_client,
)

from app.mcp.config import (
    MCPServerConfig,
)


class MCPClient:

    def __init__(
        self,
        config: MCPServerConfig
    ):
        self.config = config

        self._exit_stack: (
            AsyncExitStack | None
        ) = None

        self._session: (
            ClientSession | None
        ) = None

        self._connected = False

    # =========================
    # Properties
    # =========================

    @property
    def connected(
        self
    ) -> bool:

        return self._connected

    # =========================
    # Connect
    # =========================

    async def connect(
        self
    ) -> None:

        if self._connected:
            return

        print(
            f"[MCP CLIENT] "
            f"creating session: "
            f"{self.config.name}"
        )

        server_params = (
            StdioServerParameters(
                command=self.config.command,
                args=self.config.args,
                env=self.config.env,
            )
        )

        exit_stack = (
            AsyncExitStack()
        )

        try:

            read, write = (
                await exit_stack.enter_async_context(
                    stdio_client(
                        server_params
                    )
                )
            )

            session = (
                await exit_stack.enter_async_context(
                    ClientSession(
                        read,
                        write
                    )
                )
            )

            await session.initialize()

            self._exit_stack = (
                exit_stack
            )

            self._session = (
                session
            )

            self._connected = True

        except Exception:

            await exit_stack.aclose()

            raise

    # =========================
    # Disconnect
    # =========================

    async def disconnect(
        self
    ) -> None:

        if not self._connected:
            return

        try:

            if self._exit_stack:

                await (
                    self._exit_stack
                    .aclose()
                )

        finally:

            self._exit_stack = None

            self._session = None

            self._connected = False

    # =========================
    # Get Session
    # =========================

    def _get_session(
        self
    ) -> ClientSession:

        if (
            not self._connected
            or self._session is None
        ):

            raise RuntimeError(
                f"MCP server "
                f"'{self.config.name}' "
                f"is not connected."
            )

        return self._session

    # =========================
    # List Tools
    # =========================

    async def list_tools(
        self
    ):

        session = (
            self._get_session()
        )

        result = (
            await session.list_tools()
        )

        return result.tools

    # =========================
    # Call Tool
    # =========================

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any]
    ):

        session = (
            self._get_session()
        )

        return await session.call_tool(
            tool_name,
            arguments=arguments
        )
