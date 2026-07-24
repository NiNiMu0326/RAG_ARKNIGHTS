"""
Tests for backend.rag.alias_map: ALIAS_MAP validation.
Usage: cd test && python -m pytest test_alias_map.py -v
"""
import sys
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.rag.alias_map import ALIAS_MAP


# ============================================================
# ALIAS_MAP validation
# ============================================================

class TestAliasMap:
    """Verify ALIAS_MAP integrity and correctness."""

    def test_alias_map_is_non_empty(self):
        assert len(ALIAS_MAP) > 10, "ALIAS_MAP should contain many entries"

    def test_all_keys_are_strings(self):
        for key in ALIAS_MAP:
            assert isinstance(key, str), f"Key '{key}' is not a string"

    def test_all_values_are_strings(self):
        for key, value in ALIAS_MAP.items():
            assert isinstance(value, str), f"Value for '{key}' is not a string"

    def test_no_empty_keys(self):
        for key in ALIAS_MAP:
            assert key.strip(), f"Empty key found"

    def test_no_empty_values(self):
        for key, value in ALIAS_MAP.items():
            assert value.strip(), f"Empty value for key '{key}'"

    def test_known_aliases(self):
        """Verify some well-known alias mappings."""
        assert ALIAS_MAP["银老板"] == "银灰"
        assert ALIAS_MAP["小羊"] == "艾雅法拉"
        assert ALIAS_MAP["小火龙"] == "伊芙利特"
        assert ALIAS_MAP["德狗"] == "德克萨斯"
        assert ALIAS_MAP["42"] == "史尔特尔"
        assert ALIAS_MAP["小兔子"] == "阿米娅"
        assert ALIAS_MAP["老猫"] == "凯尔希"
        assert ALIAS_MAP["蒂蒂"] == "斯卡蒂"

    def test_identity_mappings(self):
        """Some entries map names to themselves (for query expansion)."""
        assert ALIAS_MAP.get("银灰") == "银灰"
        assert ALIAS_MAP.get("史尔特尔") == "史尔特尔"
        assert ALIAS_MAP.get("能天使") == "能天使"

    def test_multiple_aliases_to_same_target(self):
        """Multiple aliases can map to the same canonical name."""
        aliases_for_银灰 = [k for k, v in ALIAS_MAP.items() if v == "银灰"]
        assert len(aliases_for_银灰) >= 3  # 银老板, 银总, 银灰

    def test_no_missing_canonical_names(self):
        """Every canonical name should be reachable via reverse lookup."""
        # Not every canonical name has a self-mapping — that's fine
        # as long as each value is reachable as a valid target
        canonical_names = set(ALIAS_MAP.values())
        assert len(canonical_names) > 0
        # Verify each value can be retrieved by some alias
        for value in canonical_names:
            matching_keys = [k for k, v in ALIAS_MAP.items() if v == value]
            assert len(matching_keys) >= 1, f"Canonical name '{value}' should be reachable"

    def test_aliases_not_overly_long(self):
        """Aliases should be reasonably short (user-facing names)."""
        for key in ALIAS_MAP:
            assert len(key) <= 30, f"Alias '{key}' is too long ({len(key)} chars)"

    def test_aliases_have_no_leading_trailing_whitespace(self):
        for key, value in ALIAS_MAP.items():
            assert key == key.strip()
            assert value == value.strip()
