"""Small in-memory TTL cache used to avoid hammering provider APIs."""

from __future__ import annotations

import time
from typing import Any


class TTLCache:
    """A tiny TTL cache with a bounded number of entries.

    AstrBot runs all handlers in one event loop, so no locking is required:
    ``get`` and ``set`` never await.
    """

    def __init__(self, ttl: float, maxsize: int = 256) -> None:
        self.ttl = max(0.0, float(ttl))
        self.maxsize = max(1, int(maxsize))
        self._items: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._items.get(key)
        if item is None:
            return None

        expires_at, value = item
        if time.monotonic() >= expires_at:
            self._items.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        if self.ttl <= 0:
            return

        self._purge_expired()
        if len(self._items) >= self.maxsize:
            # dict preserves insertion order, so the first key is the oldest.
            oldest = next(iter(self._items), None)
            if oldest is not None:
                self._items.pop(oldest, None)

        self._items[key] = (time.monotonic() + self.ttl, value)

    def clear(self) -> None:
        self._items.clear()

    def _purge_expired(self) -> None:
        now = time.monotonic()
        expired = [key for key, (expires_at, _) in self._items.items() if expires_at <= now]
        for key in expired:
            self._items.pop(key, None)

    def __len__(self) -> int:
        return len(self._items)
