"""
安全测试夹具。

设计原则：这个套件**不碰网络、不调 LLM、不花钱**。
所有请求都通过 httpx.ASGITransport 在进程内打 FastAPI app，
且把 LangGraph workflow 换成桩函数。
"""

from __future__ import annotations

import asyncio
import os

# ------------------------------------------------------------
# 必须在 import app.* 之前设置。
#
# app.rag.embeddings 在 import 时会构建 SentenceTransformer，
# 默认会去 HuggingFace 发 HEAD 请求；在无网环境下每次重试退避，
# 能把一次 import 拖到几分钟。模型在本地缓存里，离线即可加载。
# ------------------------------------------------------------

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


import httpx  # noqa: E402
import pytest  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.security import auth as auth_module  # noqa: E402
from app.security import limits as limits_module  # noqa: E402


# ============================================================
# 模式切换
# ============================================================

def _reset_security_state() -> None:
    """
    settings 是模块级单例，改了之后必须清掉两处派生状态：
      - key map 缓存（靠比对 raw 字符串自动失效，但显式清更稳）
      - 限流 / 并发单例（它们在构造时把配置固化了）
    """
    auth_module._KEY_MAP_CACHE = None
    limits_module.reset_limiters()


@pytest.fixture
def demo_mode(monkeypatch):
    """演示模式 + 两个测试身份。"""

    monkeypatch.setattr(settings, "app_mode", "demo")
    monkeypatch.setattr(
        settings,
        "demo_api_keys",
        "alice:test-key-alice,bob:test-key-bob",
    )
    monkeypatch.setattr(
        settings, "demo_rate_limit_per_minute", 10
    )
    monkeypatch.setattr(
        settings, "demo_max_concurrent_requests", 2
    )
    monkeypatch.setattr(
        settings, "demo_max_tokens_per_request", 50000
    )
    monkeypatch.setattr(
        settings, "demo_request_timeout_seconds", 30.0
    )

    _reset_security_state()

    yield

    _reset_security_state()


@pytest.fixture
def dev_mode(monkeypatch):
    """默认模式，用于证明"零回归"。"""

    monkeypatch.setattr(settings, "app_mode", "dev")
    monkeypatch.setattr(settings, "demo_api_keys", "")

    _reset_security_state()

    yield

    _reset_security_state()


ALICE_KEY = "test-key-alice"
BOB_KEY = "test-key-bob"


# ============================================================
# Workflow 桩
#
# 真实 workflow 会调 DeepSeek。这里只关心请求入口的守卫，
# 不关心 Agent 规划，所以整条链路替换掉。
# ============================================================

@pytest.fixture
def stub_workflow(monkeypatch):
    """
    返回一个 dict，用来观察"实际到达记忆层的 session_id"。
    """

    from app.api import chat as chat_module

    observed: dict = {
        "session_ids": [],
        "final_answer": "stub answer",
    }

    async def fake_ainvoke(state, config=None):
        return {
            "status": "completed",
            "task_type": "stub",
            "final_answer": observed["final_answer"],
            "tasks": [],
            "messages": [],
            "errors": [],
            "total_retries": 0,
        }

    def fake_add_conversation(session_id, role, content):
        if role == "user":
            observed["session_ids"].append(session_id)

    monkeypatch.setattr(
        chat_module.agent_graph, "ainvoke", fake_ainvoke
    )
    monkeypatch.setattr(
        chat_module.memory_manager,
        "add_conversation",
        fake_add_conversation,
    )
    monkeypatch.setattr(
        chat_module.memory_manager,
        "add_episode",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        chat_module, "build_memory_context", lambda **kwargs: ""
    )
    monkeypatch.setattr(
        chat_module, "should_process_memory", lambda message: False
    )
    # Langfuse 若在 .env 里配了，测试会真的去建 trace
    monkeypatch.setattr(
        chat_module, "get_langfuse_handler", lambda: None
    )

    return observed


# ============================================================
# ASGI 客户端
#
# 一次测试内所有请求跑在**同一个事件循环**上。
# 原因：asyncio.Lock 一旦在某个 loop 上用过，就绑定死了，
# 换 loop 会 RuntimeError。每个请求各来一个 asyncio.run() 会踩这个坑。
# ============================================================

class AsgiRunner:

    def __init__(self, app):
        self._transport = httpx.ASGITransport(app=app)
        self._loop = asyncio.new_event_loop()

    async def _request(self, method, url, **kwargs):
        async with httpx.AsyncClient(
            transport=self._transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, url, **kwargs)

    def request(self, method, url, **kwargs):
        return self._loop.run_until_complete(
            self._request(method, url, **kwargs)
        )

    def post_chat(self, payload, headers=None):
        return self.request(
            "POST", "/api/chat", json=payload, headers=headers or {}
        )

    def get(self, url):
        return self.request("GET", url)

    def close(self):
        self._loop.close()


@pytest.fixture
def asgi():
    from app.main import app

    runner = AsgiRunner(app)

    yield runner

    runner.close()
