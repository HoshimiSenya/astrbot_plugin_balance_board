"""Small in-memory caches used to avoid repeated work."""

from __future__ import annotations

import os
import threading
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


class ImageCache:
    """Remember rendered PNG files by the fingerprint of their content.

    Drawing a card costs tens of milliseconds of Pillow work. When the next
    query returns exactly the same data the previous PNG can simply be sent
    again, so a hit costs nothing beyond a ``stat`` call.

    Rendering happens in a worker thread (``asyncio.to_thread``), so unlike
    :class:`TTLCache` this cache is guarded by a lock. ``maxsize`` of ``0``
    turns the cache off, which is what the ``image_cache`` option does.

    Evicted entries are dropped from the index only; their files are left to
    the renderer's age-based temp-file cleanup, because AstrBot may still be
    reading the path returned for the previous message.
    """

    def __init__(self, maxsize: int = 16) -> None:
        self.maxsize = max(0, int(maxsize))
        self._items: dict[str, str] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        """Return the cached image path, or ``None`` when it cannot be reused."""

        if self.maxsize <= 0:
            return None

        with self._lock:
            path = self._items.get(key)
            if path is None:
                return None

            if not _is_reusable(path):
                self._items.pop(key, None)
                return None

            # Refresh recency so the hottest fingerprint survives eviction.
            self._items.pop(key, None)
            self._items[key] = path
            return path

    def set(self, key: str, path: str) -> None:
        if self.maxsize <= 0:
            return

        with self._lock:
            self._items.pop(key, None)
            while len(self._items) >= self.maxsize:
                oldest = next(iter(self._items), None)
                if oldest is None:
                    break
                self._items.pop(oldest, None)
            self._items[key] = path

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)


def _is_reusable(path: str) -> bool:
    """Return whether *path* still points at a non-empty file."""

    try:
        return os.path.getsize(path) > 0
    except OSError:
        return False
