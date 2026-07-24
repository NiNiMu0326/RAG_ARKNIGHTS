"""
Tests for backend.lc.embeddings: SiliconFlowEmbeddings (LangChain wrapper).
Usage: cd test && python -m pytest test_embeddings.py -v
"""
import sys
import pytest
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.lc.embeddings import SiliconFlowEmbeddings


# ============================================================
# SiliconFlowEmbeddings tests
# ============================================================

class TestSiliconFlowEmbeddings:
    """Test the LangChain-compatible embeddings wrapper."""

    def test_init_defaults(self):
        with mock.patch('backend.lc.embeddings.config') as mock_config:
            mock_config.SILICONFLOW_API_KEY = "sk-test-config"
            emb = SiliconFlowEmbeddings()
            assert emb.api_key == "sk-test-config"
            assert emb.model == "Pro/BAAI/bge-m3"

    def test_init_custom_api_key(self):
        emb = SiliconFlowEmbeddings(api_key="sk-custom")
        assert emb.api_key == "sk-custom"

    def test_init_custom_model(self):
        with mock.patch('backend.lc.embeddings.config') as mock_config:
            mock_config.SILICONFLOW_API_KEY = "sk-test"
            emb = SiliconFlowEmbeddings(model="custom/model")
            assert emb.model == "custom/model"

    def test_embed_documents_empty(self):
        with mock.patch('backend.lc.embeddings.config') as mock_config:
            mock_config.SILICONFLOW_API_KEY = "sk-test"
            emb = SiliconFlowEmbeddings()
            result = emb.embed_documents([])
            assert result == []

    def test_embed_documents_delegates_to_client(self):
        with mock.patch('backend.lc.embeddings.config') as mock_config:
            mock_config.SILICONFLOW_API_KEY = "sk-test"
            emb = SiliconFlowEmbeddings()
            fake_embeddings = [[0.1, 0.2], [0.3, 0.4]]
            with mock.patch.object(emb._client, 'embed', return_value=fake_embeddings) as mock_embed:
                result = emb.embed_documents(["文本A", "文本B"])
                assert result == fake_embeddings
                mock_embed.assert_called_once_with(["文本A", "文本B"], model=emb.model)

    def test_embed_query_delegates_to_client(self):
        with mock.patch('backend.lc.embeddings.config') as mock_config:
            mock_config.SILICONFLOW_API_KEY = "sk-test"
            emb = SiliconFlowEmbeddings()
            fake_embedding = [[0.5, 0.6]]
            with mock.patch.object(emb._client, 'embed', return_value=fake_embedding) as mock_embed:
                result = emb.embed_query("单个查询")
                assert result == [0.5, 0.6]

    def test_embed_query_empty_result_returns_empty_list(self):
        with mock.patch('backend.lc.embeddings.config') as mock_config:
            mock_config.SILICONFLOW_API_KEY = "sk-test"
            emb = SiliconFlowEmbeddings()
            with mock.patch.object(emb._client, 'embed', return_value=[]):
                result = emb.embed_query("查询")
                assert result == []

    def test_is_langchain_embeddings_subclass(self):
        from langchain_core.embeddings import Embeddings
        with mock.patch('backend.lc.embeddings.config') as mock_config:
            mock_config.SILICONFLOW_API_KEY = "sk-test"
            emb = SiliconFlowEmbeddings()
            assert isinstance(emb, Embeddings)
