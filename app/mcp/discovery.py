from app.mcp.adapter import (
    MCPToolAdapter,
)

from app.mcp.manager import (
    mcp_manager,
)

from app.tools.registry import (
    register_tool,
)

from app.schemas.policy import (
    ToolPolicyAction,
)

from app.tools.policy import (
    tool_policy_engine,
)



async def discover_mcp_tools(
    server_name: str
) -> list[MCPToolAdapter]:
    """
    从 MCP Server 动态发现 Tool，
    并转换成项目内部统一 Tool 接口。
    """

    client = (
        mcp_manager.get_client(
            server_name
        )
    )

    remote_tools = (
        await client.list_tools()
    )

    adapters = []

    for tool in remote_tools:

        local_name = (
            f"mcp.{server_name}."
            f"{tool.name}"
        )

        adapter = MCPToolAdapter(
            name=local_name,

            description=(
                tool.description
                or ""
            ),

            client=client,

            remote_tool_name=(
                tool.name
            ),
        )

        adapters.append(
            adapter
        )

    return adapters

async def discover_and_register_mcp_tools(
    server_name: str
) -> list[str]:

    adapters = (
        await discover_mcp_tools(
            server_name
        )
    )

    registered_names = []

    for adapter in adapters:

        policy = (
            tool_policy_engine.evaluate(
                adapter.name
            )
        )

        if (
            policy.action
            == ToolPolicyAction.DENY
        ):

            print(
                f"[POLICY] denied discovery: "
                f"{adapter.name}"
            )

            continue

        register_tool(
            adapter
        )

        registered_names.append(
            adapter.name
        )

        print(
            f"[POLICY] registered "
            f"{adapter.name}: "
            f"{policy.action}"
        )

    return registered_names


async def discover_all_mcp_tools(
) -> dict[str, list[str]]:

    discovered = {}

    for server_name, client in (
        mcp_manager.clients.items()
    ):

        if not client.connected:

            continue

        try:

            names = (
                await
                discover_and_register_mcp_tools(
                    server_name
                )
            )

            discovered[
                server_name
            ] = names

        except Exception as exc:

            print(
                f"[MCP] discovery failed: "
                f"{server_name}: {exc}"
            )

    return discovered
