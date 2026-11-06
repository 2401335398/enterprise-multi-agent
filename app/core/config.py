from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    llm_api_key: str
    llm_base_url: str
    llm_model: str

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/enterprise_multi_agent"
    )
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_timeout_seconds: float = 30.0
    database_connect_timeout_seconds: float = 10.0
    database_command_timeout_seconds: float = 30.0

    # ========================================================
    # 运行模式
    #
    #   dev  —— 现状：无鉴权、Swagger 开启、MCP 正常启动
    #   demo —— 公网演示：强制鉴权、关闭文档、不启 MCP、
    #           禁用高风险工具、限流限并发限 token
    #
    # 默认 dev，保证现有行为完全不变。
    # ========================================================

    app_mode: str = "dev"

    # ========================================================
    # 演示模式配置
    # ========================================================

    # "alice:key1,bob:key2"
    # 演示模式下为空则拒绝启动（fail closed）
    demo_api_keys: str = ""

    demo_rate_limit_per_minute: int = 10

    demo_max_concurrent_requests: int = 2

    # 单次请求（整个 DAG）的 token 上限
    demo_max_tokens_per_request: int = 50000

    demo_request_timeout_seconds: float = 180.0

    # ========================================================
    # 用户认证：JWT + Refresh Token
    #
    # 与 demo API Key 并存：
    #   dev  -> 无凭据时仍是 local
    #   demo -> X-API-Key / Bearer API Key 继续可用
    #   两者都接受有效的用户 JWT
    # ========================================================

    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "enterprise-multi-agent"
    jwt_audience: str = "enterprise-multi-agent-api"
    jwt_leeway_seconds: int = 30

    access_token_ttl_seconds: int = 900
    refresh_token_ttl_days: int = 7

    # cookie：浏览器使用 HttpOnly Cookie
    # body：CLI / 测试使用，登录响应里返回 refresh_token
    refresh_token_delivery: Literal["cookie", "body"] = "cookie"
    refresh_token_cookie_name: str = "refresh_token"
    refresh_token_cookie_secure: bool = False
    refresh_token_cookie_samesite: Literal[
        "lax", "strict", "none"
    ] = "lax"
    refresh_token_reuse_grace_seconds: int = 10

    # 不显式配置时：dev 允许注册，demo 默认关闭。
    auth_allow_registration: bool | None = None

    password_min_length: int = 8
    password_max_length: int = 128

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def is_demo(self) -> bool:
        return self.app_mode.strip().lower() == "demo"

    @property
    def registration_enabled(self) -> bool:
        if self.auth_allow_registration is None:
            return not self.is_demo
        return self.auth_allow_registration


settings = Settings()

"""
.env
 ↓
Settings
 ↓
整个应用统一读取配置

以后 Redis、PostgreSQL、Langfuse 都放这里。
"""
