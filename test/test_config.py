"""
Tests for backend.config: paths, API keys, model settings.
Usage: cd test && python -m pytest test_config.py -v
"""
import sys
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend import config


# ============================================================
# Path configuration
# ============================================================

class TestConfigPaths:
    """Test path constants are correctly set."""

    def test_base_dir_exists(self):
        assert config.BASE_DIR.exists()
        assert config.BASE_DIR.is_dir()

    def test_base_dir_is_project_root(self):
        """BASE_DIR should point to the project root (one level above backend/)."""
        assert (config.BASE_DIR / "backend").exists()
        assert (config.BASE_DIR / "data").exists()

    def test_chunks_dir(self):
        assert config.CHUNKS_DIR == config.BASE_DIR / "chunks"

    def test_graph_dir(self):
        assert config.GRAPH_DIR == config.CHUNKS_DIR / "graphrag"

    def test_entity_relations_file(self):
        assert config.ENTITY_RELATIONS_FILE == config.GRAPH_DIR / "entity_relations.json"

    def test_data_dir(self):
        assert config.DATA_DIR == config.BASE_DIR / "data"

    def test_faiss_index_dir(self):
        assert config.FAISS_INDEX_DIR == config.BASE_DIR / "faiss_index"
        assert config.FAISS_INDEX_DIR_STR == str(config.FAISS_INDEX_DIR)


# ============================================================
# API configuration
# ============================================================

class TestConfigAPI:
    """Test API-related configuration values."""

    def test_siliconflow_base_url(self):
        assert config.SILICONFLOW_BASE_URL == "https://api.siliconflow.cn/v1"

    def test_deepseek_base_url(self):
        assert config.DEEPSEEK_BASE_URL == "https://api.deepseek.com"

    def test_api_keys_are_strings(self):
        assert isinstance(config.SILICONFLOW_API_KEY, str)
        assert isinstance(config.TAVILY_API_KEY, str)
        assert isinstance(config.DEEPSEEK_API_KEY, str)


# ============================================================
# Model settings
# ============================================================

class TestConfigModels:
    """Test model-related configuration."""

    def test_embedding_model(self):
        assert config.EMBEDDING_MODEL == "Pro/BAAI/bge-m3"

    def test_reranker_model(self):
        assert config.RERANKER_MODEL == "BAAI/bge-reranker-v2-m3"

    def test_deepseek_llm_model(self):
        assert config.DEEPSEEK_LLM_MODEL == "deepseek-v4-flash"

    def test_default_temperature(self):
        assert 0 <= config.DEFAULT_TEMPERATURE <= 2.0


# ============================================================
# Search settings
# ============================================================

class TestConfigSearch:
    """Test search-related configuration."""

    def test_rrf_k_is_positive(self):
        assert config.RRF_K > 0

    def test_vector_weight_is_valid(self):
        assert 0.0 <= config.VECTOR_WEIGHT <= 1.0


# ============================================================
# get_bm25_index_path
# ============================================================

class TestGetBm25IndexPath:
    """Test BM25 index path helper function."""

    def test_returns_string(self):
        path = config.get_bm25_index_path("operators")
        assert isinstance(path, str)

    def test_ends_with_collection_name(self):
        path = config.get_bm25_index_path("operators")
        assert path.endswith("operators_bm25.pkl")

    def test_starts_with_chunks_dir(self):
        path = config.get_bm25_index_path("stories")
        assert path.startswith(str(config.CHUNKS_DIR))

    def test_different_collections_different_paths(self):
        p1 = config.get_bm25_index_path("operators")
        p2 = config.get_bm25_index_path("stories")
        assert p1 != p2


# ============================================================
# JWT_SECRET
# ============================================================

class TestJWTSecret:
    """JWT_SECRET should be set (from conftest.py)."""

    def test_jwt_secret_is_set(self):
        """conftest.py sets JWT_SECRET for tests."""
        import os
        assert os.environ.get("JWT_SECRET") == "test-jwt-secret-for-tests"
