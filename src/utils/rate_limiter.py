from __future__ import annotations

import asyncio
import time
from collections import deque

from src.config import settings


class RateLimiter:
    """Token-bucket rate limiter for API requests."""

    def __init__(self, requests_per_second: float | None = None) -> None:
        self.rate = requests_per_second or settings.requests_per_second
        self.tokens = self.rate
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock() if hasattr(asyncio, "Lock") else None

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
        self.last_refill = now

    def acquire(self) -> None:
        """Block until a token is available (sync version)."""
        while True:
            self._refill()
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return
            time.sleep(1.0 / self.rate)

    async def async_acquire(self) -> None:
        """Wait until a token is available (async version)."""
        while True:
            self._refill()
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return
            await asyncio.sleep(1.0 / self.rate)


class SlidingWindowRateLimiter:
    """Sliding window rate limiter for API requests."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: deque[float] = deque()

    def acquire(self) -> None:
        now = time.monotonic()
        # Remove expired timestamps
        while self.requests and self.requests[0] < now - self.window_seconds:
            self.requests.popleft()

        if len(self.requests) >= self.max_requests:
            sleep_time = self.requests[0] + self.window_seconds - now
            if sleep_time > 0:
                time.sleep(sleep_time)

        self.requests.append(time.monotonic())
