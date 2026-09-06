import asyncio

from app.mcp.discovery import (
    discover_and_register_mcp_tools,
)

from app.tools.registry import (
    list_tools,
)


async def main():

    print(
        "\nTOOLS BEFORE:"
    )

    print(
        list_tools()
    )

    names = (
        await discover_and_register_mcp_tools(
            "filesystem"
        )
    )

    print(
        "\nMCP REGISTERED:"
    )

    for name in names:

        print(
            name
        )

    print(
        "\nTOOLS AFTER:"
    )

    for name in list_tools():

        print(
            name
        )


if __name__ == "__main__":

    asyncio.run(
        main()
    )
