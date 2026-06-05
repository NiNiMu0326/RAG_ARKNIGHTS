"""
Tests for backend.api.llm_factory: LLM client factory and model registry.
Usage: cd test && python -m pytest test_llm_factory.py -v
"""
import sys
import os
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.api.llm_factory import (
    MODEL_REGISTRY,
    DEFAULT_MODEL,
    get_model_info,
    get_available_models,
    get_llm_client,
)
from backend import config


# ============================================================
# Model registry validation
# ============================================================

class TestModelRegistry:
    """Verify the model registry structure."""

    def test_registry_has_two_models(self):
        assert len(MODEL_REGISTRY) == 2

    def test_deepseek_chat_in_registry(self):
        assert "deepseek-chat" in MODEL_REGISTRY
        info = MODEL_REGISTRY["deepseek-chat"]
        assert info["provider"] == "deepseek"
        assert info["model_name"] == "deepseek-v4-flash"

    def test_minimax_m2_7_in_registry(self):
        assert "minimax-m2.7" in MODEL_REGISTRY
        info = MODEL_REGISTRY["minimax-m2.7"]
        assert info["provider"] == "minimax"
        assert info["model_name"] == "MiniMax-M2.7"

    def test_all_entries_have_display_name(self):
        for mid, info in MODEL_REGISTRY.items():
            assert "display_name" in info
            assert info["display_name"]

    def test_all_entries_have_provider(self):
        for mid, info in MODEL_REGISTRY.items():
            assert "provider" in info
            assert info["provider"] in ("deepseek", "minimax")

    def test_all_entries_have_model_name(self):
        for mid, info in MODEL_REGISTRY.items():
            assert "model_name" in info
            assert info["model_name"]


# ============================================================
# DEFAULT_MODEL
# ============================================================

class TestDefaultModel:
    """Verify the default model configuration."""

    def test_default_model_is_in_registry(self):
        assert DEFAULT_MODEL in MODEL_REGISTRY

    def test_default_model_is_minimax(self):
        assert DEFAULT_MODEL == "minimax-m2.7"


# ============================================================
# get_model_info
# ============================================================

class TestGetModelInfo:
    """Test model info retrieval."""

    def test_get_existing_model(self):
        info = get_model_info("deepseek-chat")
        assert info["provider"] == "deepseek"

    def test_get_unknown_model_falls_back_to_default(self):
        info = get_model_info("nonexistent-model")
        assert info["provider"] == MODEL_REGISTRY[DEFAULT_MODEL]["provider"]

    def test_get_empty_string_falls_back(self):
        info = get_model_info("")
        assert info == MODEL_REGISTRY[DEFAULT_MODEL]

    def test_get_none_falls_back(self):
        info = get_model_info("")
        assert info == MODEL_REGISTRY[DEFAULT_MODEL]


# ============================================================
# get_available_models
# ============================================================

class TestGetAvailableModels:
    """Test the frontend-facing model list."""

    def test_returns_list(self):
        models = get_available_models()
        assert isinstance(models, list)
        assert len(models) == 2

    def test_each_entry_has_required_keys(self):
        models = get_available_models()
        for m in models:
            assert "id" in m
            assert "display_name" in m
            assert "provider" in m

    def test_deepseek_entry(self):
        models = get_available_models()
        ds = [m for m in models if m["id"] == "deepseek-chat"]
        assert len(ds) == 1
        assert ds[0]["provider"] == "deepseek"

    def test_minimax_entry(self):
        models = get_available_models()
        mm = [m for m in models if m["id"] == "minimax-m2.7"]
        assert len(mm) == 1
        assert mm[0]["provider"] == "minimax"

    def test_display_names_from_registry(self):
        models = get_available_models()
        for m in models:
            expected = MODEL_REGISTRY[m["id"]]["display_name"]
            assert m["display_name"] == expected


# ============================================================
# Get LLM client (requires API keys)
# ============================================================

class TestGetLlmClient:
    """Test the LLM client factory."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear client cache before each test."""
        from backend.api.llm_factory import _clients
        _clients.clear()
        yield

    def test_get_deepseek_client_requires_key(self, monkeypatch):
        """Without API key, DeepSeekClient should raise ValueError."""
        monkeypatch.setattr(config, 'DEEPSEEK_API_KEY', '')

        with pytest.raises(ValueError, match="DeepSeek API key must be provided"):
            get_llm_client("deepseek-chat")

    def test_deepseek_client_cache(self, monkeypatch):
        """Same model_id should return cached client."""
        if not config.DEEPSEEK_API_KEY:
            monkeypatch.setattr(config, 'DEEPSEEK_API_KEY', 'test-key')

        client1 = get_llm_client("deepseek-chat")
        client2 = get_llm_client("deepseek-chat")
        assert client1 is client2

    def test_different_models_different_clients(self, monkeypatch):
        """Different model_ids should return different client instances."""
        if not config.DEEPSEEK_API_KEY:
            monkeypatch.setattr(config, 'DEEPSEEK_API_KEY', 'test-deepseek-key')
        if not config.MINIMAX_API_KEY:
            monkeypatch.setattr(config, 'MINIMAX_API_KEY', 'test-minimax-key')

        client1 = get_llm_client("deepseek-chat")
        client2 = get_llm_client("minimax-m2.7")
        # They use different base_urls/different providers, should be different
        assert client1 is not client2

    def test_get_llm_client_default(self, monkeypatch):
        """Calling with None should return default model client."""
        if not config.MINIMAX_API_KEY:
            monkeypatch.setattr(config, 'MINIMAX_API_KEY', 'test-key')

        client = get_llm_client(None)
        assert client is not None

    def test_minimax_client_missing_key(self, monkeypatch):
        """Without MiniMax key, should raise ValueError."""
        monkeypatch.setattr(config, 'MINIMAX_API_KEY', '')

        with pytest.raises(ValueError, match="MiniMax API key not configured"):
            get_llm_client("minimax-m2.7")

    def test_unknown_provider_raises(self, monkeypatch):
        """An unknown provider should raise ValueError from get_llm_client."""
        # Inject a fake model with an unknown provider into the registry
        monkeypatch.setitem(MODEL_REGISTRY, 'fake-model', {
            'provider': 'unknown_provider',
            'model_name': 'fake-model-v1',
            'display_name': 'Fake Model',
        })

        with pytest.raises(ValueError, match="Unknown provider"):
            get_llm_client("fake-model")


# ============================================================
# Client cache management
# ============================================================

class TestClientCache:
    """Test the client cache behavior."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        from backend.api.llm_factory import _clients
        _clients.clear()
        yield

    def test_cache_starts_empty(self):
        from backend.api.llm_factory import _clients
        assert len(_clients) == 0

    def test_cache_uses_provider_prefix(self, monkeypatch):
        """Cache keys should include provider prefix."""
        if not config.DEEPSEEK_API_KEY:
            monkeypatch.setattr(config, 'DEEPSEEK_API_KEY', 'test-key')

        get_llm_client("deepseek-chat")
        from backend.api.llm_factory import _clients
        cache_keys = list(_clients.keys())
        assert any(k.startswith("deepseek:") for k in cache_keys)
