import asyncio

from app.mcp.discovery import (
    discover_and_register_mcp_tools,
)

from app.schemas.tool import (
    ToolCall,
)

from app.tools.executor import (
    execute_tool_call,
)


async def main():

    await discover_and_register_mcp_tools(
        "filesystem"
    )

    call = ToolCall(
        tool=(
            "mcp.filesystem."
            "read_text_file"
        ),

        arguments={
            "path":
                (
                    r"D:\enterprise-multi-agent"
                    r"\mcp_workspace"
                    r"\company_profile.txt"
                )
        }
    )

    result = (
        await execute_tool_call(
            call
        )
    )

    print(
        result.model_dump()
    )


if __name__ == "__main__":

    asyncio.run(
        main()
    )
