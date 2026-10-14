from fastapi import FastAPI

from app.api.chat import router as chat_router

from contextlib import (
    asynccontextmanager,
)

from app.core.config import settings

from app.mcp.manager import (
    mcp_manager,
)

from app.mcp.discovery import (
    discover_all_mcp_tools,
)

from app.security.auth import (
    validate_demo_config,
)


@asynccontextmanager
async def lifespan(
    app: FastAPI
):

    # =========================
    # Startup
    # =========================

    # 演示模式必须配好鉴权，否则拒绝启动。
    # 放在最前面：宁可起不来，也不能"以为有保护其实没有"。
    validate_demo_config()

    print(
        f"[APP] mode = {settings.app_mode}"
    )

    if settings.is_demo:

        # 演示模式不连 MCP：不 connect、不 discover，
        # 也就不会有 npx 子进程和宿主目录读写能力。
        print(
            "[MCP] skipped (demo mode)"
        )

        yield

        print("[APP] Shutting down...")
        return

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


# 演示/生产模式关闭 Swagger、ReDoc 与 OpenAPI schema。
# None 会让 FastAPI 直接不注册这些路由（404），
# 而不是渲染一个空的文档页。
_DOCS_ENABLED = not settings.is_demo


app = FastAPI(
    title="Enterprise Multi-Agent Research & Decision Copilot",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if _DOCS_ENABLED else None,
    redoc_url="/redoc" if _DOCS_ENABLED else None,
    openapi_url=(
        "/openapi.json" if _DOCS_ENABLED else None
    ),
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "mode": settings.app_mode,
    }


app.include_router(
    chat_router,
    prefix="/api"
)
