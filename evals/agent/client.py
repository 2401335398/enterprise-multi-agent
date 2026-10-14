"""
Agent Evaluation —— HTTP 客户端。

刻意走 HTTP 而不是进程内调用 app.graph：

1. 被测系统 hot path 里有大量 print()（chat.py / scheduler.py / supervisor.py，
   含原始 LLM 输出），进程内调用会污染评测脚本的 stdout；走 HTTP 时
   这些落在服务端终端，评测输出保持干净。
2. HTTP 是真实用户路径，测的就是部署形态本身。
"""

from __future__ import annotations

import httpx


# 复杂 DAG 实测约 33s，留足余量
DEFAULT_TIMEOUT_SECONDS = 180.0


class ChatClientError(RuntimeError):
    """调用 /api/chat 失败。"""


class ChatClient:

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        api_key: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.chat_url = f"{self.base_url}/api/chat"
        self.health_url = f"{self.base_url}/health"

        # 演示模式需要带 key。默认 None —— 对 dev 模式服务
        # 不发送任何鉴权头，行为与改动前完全一致。
        headers = (
            {"X-API-Key": api_key}
            if api_key
            else {}
        )

        self._client = httpx.Client(
            timeout=timeout_seconds,
            headers=headers,
        )

    # --------------------------------------------------------

    def health(self) -> bool:
        try:
            response = self._client.get(self.health_url)
        except httpx.HTTPError:
            return False

        return response.status_code == 200

    def preflight(self) -> None:
        """
        起跑前确认服务真的可用。

        不做这一步的话，40 条案例会全部失败在连不上服务上，
        浪费一次完整运行的时间和 token。
        """

        if not self.health():
            raise ChatClientError(
                f"服务不可用：GET {self.health_url} 未返回 200。"
                f"请先启动 python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
            )

        # 用一条最简请求确认 /api/chat 链路（而不仅是 /health）是通的
        try:
            self.chat(message="你好", session_id=None)
        except ChatClientError as exc:
            raise ChatClientError(
                f"/health 正常但 /api/chat 调用失败：{exc}"
            ) from exc

    # --------------------------------------------------------

    def chat(self, message: str, session_id: str | None = None) -> dict:
        payload = {"message": message}

        if session_id is not None:
            payload["session_id"] = session_id

        try:
            response = self._client.post(self.chat_url, json=payload)
        except httpx.HTTPError as exc:
            raise ChatClientError(f"请求失败：{exc}") from exc

        if response.status_code != 200:
            raise ChatClientError(
                f"HTTP {response.status_code}: {response.text[:500]}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise ChatClientError(
                f"响应不是合法 JSON：{response.text[:500]}"
            ) from exc

    # --------------------------------------------------------

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ChatClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
