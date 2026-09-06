from app.mcp.client import (
    MCPClient,
)

from app.mcp.config import (
    MCPServerConfig,
)

from app.mcp.servers import (
    MCP_SERVER_CONFIGS,
)


class MCPManager:

    def __init__(
        self
    ):

        self.clients: dict[
            str,
            MCPClient
        ] = {}

    # =========================
    # Register
    # =========================

    def register_server(
        self,
        config: MCPServerConfig
    ) -> None:

        self.clients[
            config.name
        ] = MCPClient(
            config
        )

    def register_defaults(
        self
    ) -> None:

        for config in (
            MCP_SERVER_CONFIGS.values()
        ):

            self.register_server(
                config
            )

    # =========================
    # Get Client
    # =========================

    def get_client(
        self,
        server_name: str
    ) -> MCPClient:

        client = self.clients.get(
            server_name
        )

        if client is None:

            raise ValueError(
                f"Unknown MCP server: "
                f"{server_name}"
            )

        return client

    # =========================
    # Connect One
    # =========================

    async def connect_server(
        self,
        server_name: str
    ) -> None:

        client = (
            self.get_client(
                server_name
            )
        )

        await client.connect()

    # =========================
    # Disconnect One
    # =========================

    async def disconnect_server(
        self,
        server_name: str
    ) -> None:

        client = (
            self.get_client(
                server_name
            )
        )

        await client.disconnect()

    # =========================
    # Connect All
    # =========================

    async def connect_all(
        self
    ) -> None:

        for name, client in (
            self.clients.items()
        ):

            try:

                await client.connect()

                print(
                    f"[MCP] connected: "
                    f"{name}"
                )

            except Exception as exc:

                print(
                    f"[MCP] failed: "
                    f"{name}: {exc}"
                )

    # =========================
    # Disconnect All
    # =========================

    async def disconnect_all(
        self
    ) -> None:

        for name, client in (
            self.clients.items()
        ):

            try:

                await client.disconnect()

                print(
                    f"[MCP] disconnected: "
                    f"{name}"
                )

            except Exception as exc:

                print(
                    f"[MCP] disconnect "
                    f"failed: "
                    f"{name}: {exc}"
                )

    # =========================
    # List Server Tools
    # =========================

    async def list_server_tools(
        self,
        server_name: str
    ):

        client = (
            self.get_client(
                server_name
            )
        )

        return await client.list_tools()


mcp_manager = MCPManager()

mcp_manager.register_defaults()
