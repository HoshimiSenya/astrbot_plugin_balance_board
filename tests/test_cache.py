"""Tests for the TTL cache and the rendered-image cache."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

from src.cache import ImageCache, TTLCache


class _Clock:
    """A manually advanced stand-in for ``time.monotonic``."""

    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TTLCacheTests(unittest.TestCase):
    def test_value_survives_until_the_ttl_expires(self) -> None:
        clock = _Clock()
        cache = TTLCache(60.0)

        with mock.patch("src.cache.time.monotonic", new=clock):
            cache.set("key", "value")
            clock.advance(59.0)
            self.assertEqual(cache.get("key"), "value")
            clock.advance(2.0)
            self.assertIsNone(cache.get("key"))

        self.assertEqual(len(cache), 0)

    def test_zero_ttl_disables_storing(self) -> None:
        cache = TTLCache(0)
        cache.set("key", "value")
        self.assertIsNone(cache.get("key"))

    def test_oldest_entry_is_evicted_when_full(self) -> None:
        clock = _Clock()
        cache = TTLCache(60.0, maxsize=2)

        with mock.patch("src.cache.time.monotonic", new=clock):
            cache.set("a", 1)
            cache.set("b", 2)
            cache.set("c", 3)
            self.assertIsNone(cache.get("a"))
            self.assertEqual(cache.get("b"), 2)
            self.assertEqual(cache.get("c"), 3)


class ImageCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.path = os.path.join(self._directory.name, "card.png")
        with open(self.path, "wb") as handle:
            handle.write(b"png")

    def test_returns_the_stored_path(self) -> None:
        cache = ImageCache(4)
        cache.set("fingerprint", self.path)

        self.assertEqual(cache.get("fingerprint"), self.path)

    def test_unknown_fingerprint_misses(self) -> None:
        cache = ImageCache(4)
        cache.set("fingerprint", self.path)

        self.assertIsNone(cache.get("other"))

    def test_missing_file_is_not_reused(self) -> None:
        cache = ImageCache(4)
        cache.set("fingerprint", self.path)
        os.unlink(self.path)

        self.assertIsNone(cache.get("fingerprint"))
        self.assertEqual(len(cache), 0)

    def test_empty_file_is_not_reused(self) -> None:
        cache = ImageCache(4)
        cache.set("fingerprint", self.path)
        with open(self.path, "wb"):
            pass

        self.assertIsNone(cache.get("fingerprint"))

    def test_zero_size_disables_the_cache(self) -> None:
        cache = ImageCache(0)
        cache.set("fingerprint", self.path)

        self.assertIsNone(cache.get("fingerprint"))
        self.assertEqual(len(cache), 0)

    def test_oldest_fingerprint_is_evicted_when_full(self) -> None:
        cache = ImageCache(2)
        cache.set("a", self.path)
        cache.set("b", self.path)
        cache.set("c", self.path)

        self.assertIsNone(cache.get("a"))
        self.assertEqual(cache.get("b"), self.path)
        self.assertEqual(cache.get("c"), self.path)

    def test_hits_refresh_recency(self) -> None:
        cache = ImageCache(2)
        cache.set("a", self.path)
        cache.set("b", self.path)
        self.assertEqual(cache.get("a"), self.path)

        cache.set("c", self.path)

        self.assertIsNone(cache.get("b"))
        self.assertEqual(cache.get("a"), self.path)

    def test_storing_a_key_twice_keeps_one_entry(self) -> None:
        cache = ImageCache(4)
        cache.set("fingerprint", self.path)
        cache.set("fingerprint", self.path)

        self.assertEqual(len(cache), 1)

    def test_clear_drops_every_entry(self) -> None:
        cache = ImageCache(4)
        cache.set("fingerprint", self.path)
        cache.clear()

        self.assertEqual(len(cache), 0)
        self.assertIsNone(cache.get("fingerprint"))


if __name__ == "__main__":
    unittest.main()
