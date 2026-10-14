"""
请求限流与并发限制。

都是**进程内**实现 —— 演示固定单 uvicorn worker，够用且不引新依赖。
若将来上多 worker，计数会各算各的，等于限额乘以 worker 数，
届时需要换成 Redis 之类的共享后端。
"""

from __future__ import annotations

import asyncio
import time

from fastapi import HTTPException

from app.core.config import settings


class RateLimiter:
    """按 principal 的固定窗口限流。"""

    def __init__(
        self,
        limit_per_minute: int,
        window_seconds: float = 60.0,
    ):
        self.limit = limit_per_minute
        self.window_seconds = window_seconds

        # principal -> (窗口起点, 本窗口已用次数)
        self._buckets: dict[str, tuple[float, int]] = {}

    def check(self, key: str) -> None:
        """
        用掉一次配额。超限抛 429（带 Retry-After）。

        limit <= 0 视为不限流。
        """

        # 只在演示模式生效。
        # dev 模式必须与改动前完全一致，否则本地评测跑 40+ 条请求
        # 时会被自己限流（评测套件是无感的，不能要求它改配置）。
        if not settings.is_demo:
            return

        if self.limit <= 0:
            return

        now = time.monotonic()

        window_start, used = self._buckets.get(
            key, (now, 0)
        )

        if now - window_start >= self.window_seconds:
            window_start, used = now, 0

        if used >= self.limit:

            retry_after = max(
                1,
                int(
                    self.window_seconds
                    - (now - window_start)
                ),
            )

            raise HTTPException(
                status_code=429,
                detail=(
                    "Rate limit exceeded. "
                    f"Try again in {retry_after}s."
                ),
                headers={"Retry-After": str(retry_after)},
            )

        self._buckets[key] = (window_start, used + 1)

    def reset(self) -> None:
        """测试用。"""
        self._buckets.clear()


class ConcurrencyLimiter:
    """
    同时在跑的 workflow 数上限。

    刻意不用 asyncio.Semaphore：Semaphore 只能阻塞等待，
    而这里要的是"满了就直接拒绝"（429），不是让请求排队堆积。
    """

    def __init__(self, max_concurrent: int):
        self.max_concurrent = max_concurrent
        self._active = 0
        self._lock = asyncio.Lock()

    @property
    def active(self) -> int:
        return self._active

    async def acquire(self) -> None:

        if not settings.is_demo:
            return

        if self.max_concurrent <= 0:
            return

        async with self._lock:

            if self._active >= self.max_concurrent:

                raise HTTPException(
                    status_code=429,
                    detail=(
                        "Too many concurrent requests, "
                        "please retry shortly."
                    ),
                    headers={"Retry-After": "5"},
                )

            self._active += 1

    async def release(self) -> None:

        if not settings.is_demo:
            return

        if self.max_concurrent <= 0:
            return

        async with self._lock:
            self._active = max(0, self._active - 1)


# ============================================================
# 单例
#
# 惰性构建：若在 import 时就把 settings 值固化进去，测试改了配置
# 也影响不到；而且配置一旦变化，实例会与 settings 不一致。
# ============================================================

_rate_limiter: RateLimiter | None = None
_concurrency_limiter: ConcurrencyLimiter | None = None


def get_rate_limiter() -> RateLimiter:

    global _rate_limiter

    if _rate_limiter is None:
        _rate_limiter = RateLimiter(
            limit_per_minute=(
                settings.demo_rate_limit_per_minute
            )
        )

    return _rate_limiter


def get_concurrency_limiter() -> ConcurrencyLimiter:

    global _concurrency_limiter

    if _concurrency_limiter is None:
        _concurrency_limiter = ConcurrencyLimiter(
            max_concurrent=(
                settings.demo_max_concurrent_requests
            )
        )

    return _concurrency_limiter


def reset_limiters() -> None:
    """按当前 settings 重建。测试用。"""

    global _rate_limiter, _concurrency_limiter

    _rate_limiter = None
    _concurrency_limiter = None
