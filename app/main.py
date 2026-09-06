from fastapi import FastAPI

from app.api.chat import router as chat_router

from contextlib import (
    asynccontextmanager,
)

from fastapi import FastAPI

from app.mcp.manager import (
    mcp_manager,
)

from app.mcp.discovery import (
    discover_all_mcp_tools,
)


@asynccontextmanager
async def lifespan(
    app: FastAPI
):

    # =========================
    # Startup
    # =========================

    print(
        "[APP] Starting MCP..."
    )

    await (
        mcp_manager.connect_all()
    )

    discovered = (
        await discover_all_mcp_tools()
    )

    print(
        "[MCP] discovered tools:"
    )

    for server, tools in (
        discovered.items()
    ):

        print(
            f"  {server}:"
        )

        for tool in tools:

            print(
                f"    - {tool}"
            )

    # Application starts serving
    yield

    # =========================
    # Shutdown
    # =========================

    print(
        "[APP] Shutting down MCP..."
    )

    await (
        mcp_manager.disconnect_all()
    )


app = FastAPI(
    title=(
        "Enterprise Multi-Agent"
    ),
    lifespan=lifespan,
)



app = FastAPI(
    title="Enterprise Multi-Agent Research & Decision Copilot",
    version="0.1.0",
    lifespan=lifespan
)


@app.get("/health")
async def health():
    return {
        "status": "ok"
    }


app.include_router(
    chat_router,
    prefix="/api"
)
