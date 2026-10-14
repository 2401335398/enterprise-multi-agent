from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    llm_api_key: str
    llm_base_url: str
    llm_model: str

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def is_demo(self) -> bool:
        return self.app_mode.strip().lower() == "demo"


settings = Settings()

"""
.env
 ↓
Settings
 ↓
整个应用统一读取配置

以后 Redis、PostgreSQL、Langfuse 都放这里。
"""
