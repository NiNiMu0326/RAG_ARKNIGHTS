"""
Tests for backend.rag.parent_document: LRUCache.
Usage: cd test && python -m pytest test_parent_document.py -v
"""
import sys
import time
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.rag.parent_document import LRUCache


class TestLRUCache:
    def test_set_and_get(self):
        c = LRUCache(max_size=5)
        c.set("a", "value_a")
        assert c.get("a") == "value_a"

    def test_get_missing(self):
        c = LRUCache(max_size=5)
        assert c.get("missing") is None

    def test_contains(self):
        c = LRUCache(max_size=5)
        c.set("a", "v")
        assert "a" in c
        assert "b" not in c

    def test_eviction_when_full(self):
        c = LRUCache(max_size=3)
        c.set("a", "1")
        c.set("b", "2")
        c.set("c", "3")
        # "a" is least recently used
        c.set("d", "4")
        assert c.get("a") is None
        assert c.get("b") == "2"
        assert c.get("c") == "3"
        assert c.get("d") == "4"

    def test_mru_move_on_access(self):
        c = LRUCache(max_size=3)
        c.set("a", "1")
        c.set("b", "2")
        c.set("c", "3")
        # Access "a" to make it most recently used
        c.get("a")
        # Now "b" is LRU
        c.set("d", "4")
        assert c.get("b") is None
        assert c.get("a") == "1"

    def test_overwrite_existing(self):
        c = LRUCache(max_size=5)
        c.set("a", "old")
        c.set("a", "new")
        assert c.get("a") == "new"
        assert len(c) == 1

    def test_len(self):
        c = LRUCache(max_size=10)
        assert len(c) == 0
        c.set("a", "1")
        c.set("b", "2")
        assert len(c) == 2

    def test_ttl_expiry_get(self):
        c = LRUCache(max_size=10, ttl_seconds=0.01)
        c.set("a", "v")
        time.sleep(0.02)
        assert c.get("a") is None

    def test_ttl_not_expired(self):
        c = LRUCache(max_size=10, ttl_seconds=5)
        c.set("a", "v")
        assert c.get("a") == "v"

    def test_ttl_expiry_contains(self):
        c = LRUCache(max_size=10, ttl_seconds=0.01)
        c.set("a", "v")
        time.sleep(0.02)
        assert "a" not in c
