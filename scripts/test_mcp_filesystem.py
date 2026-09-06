import asyncio

from app.mcp.manager import (
    mcp_manager,
)


async def main():

    tools = (
        await mcp_manager.list_server_tools(
            "filesystem"
        )
    )

    print(
        "\n===== MCP TOOLS ====="
    )

    for tool in tools:

        print(
            "name:",
            tool.name
        )

        print(
            "description:",
            tool.description
        )

        print(
            "inputSchema:",
            tool.input_schema
        )

        print(
            "----------------------"
        )


if __name__ == "__main__":

    asyncio.run(
        main()
    )
