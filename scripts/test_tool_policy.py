import asyncio
from pathlib import Path

from app.mcp.discovery import (
    discover_and_register_mcp_tools,
)

from app.mcp.manager import (
    mcp_manager,
)

from app.schemas.tool import (
    ToolCall,
)

from app.tools.executor import (
    execute_tool_call,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

MCP_WORKSPACE = (
    PROJECT_ROOT
    / "mcp_workspace"
)

TEST_FILE = (
    MCP_WORKSPACE
    / "company_profile.txt"
)

WRITE_TEST_FILE = (
    MCP_WORKSPACE
    / "policy_write_test.txt"
)


async def main():

    print(
        "\n=============================="
    )
    print(
        "1. CONNECT MCP"
    )
    print(
        "=============================="
    )

    await mcp_manager.connect_server(
        "filesystem"
    )

    try:

        print(
            "\n=============================="
        )
        print(
            "2. DISCOVER MCP TOOLS"
        )
        print(
            "=============================="
        )

        registered = (
            await discover_and_register_mcp_tools(
                "filesystem"
            )
        )

        for name in registered:

            print(
                "registered:",
                name
            )

        # ====================================================
        # TEST 1
        # READ -> ALLOW
        # ====================================================

        print(
            "\n=============================="
        )
        print(
            "TEST 1: READ TOOL"
        )
        print(
            "expected: ALLOW + SUCCESS"
        )
        print(
            "=============================="
        )

        read_call = ToolCall(
            tool=(
                "mcp.filesystem."
                "read_text_file"
            ),

            arguments={
                "path":
                    str(TEST_FILE)
            }
        )

        read_result = (
            await execute_tool_call(
                read_call
            )
        )

        print(
            read_result.model_dump()
        )

        # ====================================================
        # TEST 2
        # WRITE -> REQUIRE_APPROVAL
        # ====================================================

        print(
            "\n=============================="
        )
        print(
            "TEST 2: WRITE TOOL"
        )
        print(
            "expected: REQUIRE_APPROVAL"
        )
        print(
            "expected: success=False"
        )
        print(
            "=============================="
        )

        # 如果之前测试产生过文件，先删除
        if WRITE_TEST_FILE.exists():

            WRITE_TEST_FILE.unlink()

        write_call = ToolCall(
            tool=(
                "mcp.filesystem."
                "write_file"
            ),

            arguments={
                "path":
                    str(
                        WRITE_TEST_FILE
                    ),

                "content":
                    (
                        "THIS SHOULD NOT "
                        "BE WRITTEN"
                    )
            }
        )

        write_result = (
            await execute_tool_call(
                write_call
            )
        )

        print(
            write_result.model_dump()
        )

        print(
            "file exists after call:",
            WRITE_TEST_FILE.exists()
        )

        # ====================================================
        # TEST 3
        # UNKNOWN -> DENY
        # ====================================================

        print(
            "\n=============================="
        )
        print(
            "TEST 3: UNKNOWN TOOL"
        )
        print(
            "expected: DENY"
        )
        print(
            "expected: success=False"
        )
        print(
            "=============================="
        )

        unknown_call = ToolCall(
            tool=(
                "mcp.filesystem."
                "super_delete_everything"
            ),

            arguments={}
        )

        unknown_result = (
            await execute_tool_call(
                unknown_call
            )
        )

        print(
            unknown_result.model_dump()
        )

        # ====================================================
        # SUMMARY
        # ====================================================

        print(
            "\n=============================="
        )
        print(
            "SUMMARY"
        )
        print(
            "=============================="
        )

        print(
            "READ:"
        )

        print(
            "  success =",
            read_result.success
        )

        print(
            "  policy =",
            read_result.policy_action
        )

        print(
            "WRITE:"
        )

        print(
            "  success =",
            write_result.success
        )

        print(
            "  policy =",
            write_result.policy_action
        )

        print(
            "  file exists =",
            WRITE_TEST_FILE.exists()
        )

        print(
            "UNKNOWN:"
        )

        print(
            "  success =",
            unknown_result.success
        )

        print(
            "  policy =",
            unknown_result.policy_action
        )

    finally:

        print(
            "\n=============================="
        )
        print(
            "DISCONNECT MCP"
        )
        print(
            "=============================="
        )

        await mcp_manager.disconnect_server(
            "filesystem"
        )


if __name__ == "__main__":

    asyncio.run(
        main()
    )
