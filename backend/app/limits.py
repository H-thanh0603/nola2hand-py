"""Giới hạn theo IP trong RAM — thay express-rate-limit cho các route gửi mail.

shortcut: đếm theo tiến trình, không chia sẻ giữa nhiều worker; đủ dùng vì app
chạy một tiến trình như bản Node.
"""
import threading
import time
from collections.abc import Callable

from fastapi import Request

from .errors import ApiError


class MemoryLimiter:
    def __init__(
        self,
        max_calls: int,
        window_ms: int,
        message: str = "Bạn thao tác quá nhiều, hãy thử lại sau 1 giờ",
    ):
        self.max_calls = max_calls
        self.window_ms = window_ms
        self.message = message
        self._hits: dict[str, tuple[int, int]] = {}  # key -> (window_start_ms, count)
        self._lock = threading.Lock()

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()

    def check(self, key: str) -> None:
        now_ms = int(time.time() * 1000)
        start = (now_ms // self.window_ms) * self.window_ms
        with self._lock:
            stored_start, count = self._hits.get(key, (start, 0))
            if stored_start != start:
                stored_start, count = start, 0
            count += 1
            self._hits[key] = (stored_start, count)
            if len(self._hits) > 10_000:  # dọn rác của cửa sổ cũ
                self._hits = {k: v for k, v in self._hits.items() if v[0] == start}
        if count > self.max_calls:
            retry_after = ((start + self.window_ms - now_ms) // 1000) + 1
            raise ApiError(
                429,
                self.message,
                headers={"Retry-After": str(retry_after)},
            )


def ip_limit(max_calls: int, window_ms: int, message: str) -> Callable[[Request], None]:
    """Giống rateLimit({windowMs, max}) của express-rate-limit: đếm theo IP."""
    limiter = MemoryLimiter(max_calls, window_ms, message)

    def dependency(request: Request) -> None:
        limiter.check(request.client.host if request.client else "unknown")

    return dependency


def mail_limit(max_calls: int) -> Callable[[Request], None]:
    """Giống mailLimit(max) trong src/routes/auth.js: khung 1 giờ, đếm theo IP."""
    return ip_limit(max_calls, 60 * 60 * 1000, "Bạn thao tác quá nhiều, hãy thử lại sau 1 giờ")
