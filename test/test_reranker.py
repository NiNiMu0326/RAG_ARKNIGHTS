"""
Tests for backend.lc.reranker: SiliconFlowReranker (LangChain compressor).
Usage: cd test && python -m pytest test_reranker.py -v
"""
import sys
import pytest
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.documents import Document
from backend.lc.reranker import SiliconFlowReranker


# ============================================================
# SiliconFlowReranker tests
# ============================================================

class TestSiliconFlowReranker:
    """Test the LangChain-compatible reranker."""

    @pytest.fixture
    def sample_docs(self):
        return [
            Document(page_content="银灰是喀兰贸易的领袖", metadata={"chunk_id": "c1"}),
            Document(page_content="初雪是银灰的妹妹", metadata={"chunk_id": "c2"}),
            Document(page_content="崖心在罗德岛", metadata={"chunk_id": "c3"}),
            Document(page_content="无关内容", metadata={"chunk_id": "c4"}),
        ]

    def test_init_defaults(self):
        with mock.patch('backend.lc.reranker.config') as mock_config:
            mock_config.SILICONFLOW_API_KEY = "sk-test"
            reranker = SiliconFlowReranker()
            assert reranker.api_key == "sk-test"
            assert reranker.top_n == 5

    def test_init_custom_top_n(self):
        with mock.patch('backend.lc.reranker.config') as mock_config:
            mock_config.SILICONFLOW_API_KEY = "sk-test"
            reranker = SiliconFlowReranker(top_n=3)
            assert reranker.top_n == 3

    def test_compress_documents_empty(self):
        with mock.patch('backend.lc.reranker.config') as mock_config:
            mock_config.SILICONFLOW_API_KEY = "sk-test"
            reranker = SiliconFlowReranker()
            result = reranker.compress_documents([], "query")
            assert result == []

    def test_compress_documents_happy_path(self, sample_docs):
        with mock.patch('backend.lc.reranker.config') as mock_config:
            mock_config.SILICONFLOW_API_KEY = "sk-test"
            reranker = SiliconFlowReranker(top_n=2)

            fake_rerank_results = [
                {"index": 0, "relevance_score": 0.95},
                {"index": 2, "relevance_score": 0.80},
                {"index": 1, "relevance_score": 0.60},
            ]

            with mock.patch.object(reranker._client, 'rerank', return_value=fake_rerank_results):
                result = reranker.compress_documents(sample_docs, "银灰")

            # Should return top 2
            assert len(result) == 2
            # First result should have highest score
            assert result[0].metadata["chunk_id"] == "c1"
            assert result[0].metadata["relevance_score"] == 0.95
            # Second result
            assert result[1].metadata["chunk_id"] == "c3"
            assert result[1].metadata["relevance_score"] == 0.80

    def test_compress_documents_dedup_by_chunk_id(self, sample_docs):
        """When reranker returns same chunk multiple times, only keep the first (highest score)."""
        with mock.patch('backend.lc.reranker.config') as mock_config:
            mock_config.SILICONFLOW_API_KEY = "sk-test"
            reranker = SiliconFlowReranker(top_n=3)

            fake_rerank_results = [
                {"index": 0, "relevance_score": 0.95},  # c1
                {"index": 0, "relevance_score": 0.80},  # c1 again (duplicate)
                {"index": 1, "relevance_score": 0.70},  # c2
            ]

            with mock.patch.object(reranker._client, 'rerank', return_value=fake_rerank_results):
                result = reranker.compress_documents(sample_docs, "query")

            assert len(result) == 2  # c1 appears once + c2

    def test_compress_documents_respects_top_n(self, sample_docs):
        with mock.patch('backend.lc.reranker.config') as mock_config:
            mock_config.SILICONFLOW_API_KEY = "sk-test"
            reranker = SiliconFlowReranker(top_n=1)

            fake_rerank_results = [
                {"index": 0, "relevance_score": 0.95},
                {"index": 1, "relevance_score": 0.80},
                {"index": 2, "relevance_score": 0.70},
                {"index": 3, "relevance_score": 0.60},
            ]

            with mock.patch.object(reranker._client, 'rerank', return_value=fake_rerank_results):
                result = reranker.compress_documents(sample_docs, "query")

            assert len(result) == 1

    def test_compress_documents_preserves_original_metadata(self, sample_docs):
        with mock.patch('backend.lc.reranker.config') as mock_config:
            mock_config.SILICONFLOW_API_KEY = "sk-test"
            reranker = SiliconFlowReranker(top_n=3)

            fake_rerank_results = [
                {"index": 0, "relevance_score": 0.95},
            ]

            with mock.patch.object(reranker._client, 'rerank', return_value=fake_rerank_results):
                result = reranker.compress_documents(sample_docs, "query")

            assert result[0].metadata["chunk_id"] == "c1"
            assert "relevance_score" in result[0].metadata
            assert "original_index" in result[0].metadata

    def test_is_base_document_compressor(self):
        from langchain_core.documents.compressor import BaseDocumentCompressor
        with mock.patch('backend.lc.reranker.config') as mock_config:
            mock_config.SILICONFLOW_API_KEY = "sk-test"
            reranker = SiliconFlowReranker()
            assert isinstance(reranker, BaseDocumentCompressor)

    def test_top_n_capped_when_fewer_documents(self, sample_docs):
        """When top_n exceeds number of unique documents, return all."""
        with mock.patch('backend.lc.reranker.config') as mock_config:
            mock_config.SILICONFLOW_API_KEY = "sk-test"
            reranker = SiliconFlowReranker(top_n=10)

            fake_rerank_results = [
                {"index": 0, "relevance_score": 0.9},
                {"index": 1, "relevance_score": 0.8},
            ]

            with mock.patch.object(reranker._client, 'rerank', return_value=fake_rerank_results):
                result = reranker.compress_documents(sample_docs[:2], "query")

            assert len(result) == 2

    def test_reranker_uses_correct_texts(self, sample_docs):
        with mock.patch('backend.lc.reranker.config') as mock_config:
            mock_config.SILICONFLOW_API_KEY = "sk-test"
            reranker = SiliconFlowReranker()

            with mock.patch.object(reranker._client, 'rerank', return_value=[]) as mock_rerank:
                reranker.compress_documents(sample_docs[:1], "测试查询")
                mock_rerank.assert_called_once()
                args = mock_rerank.call_args[0]
                assert args[0] == "测试查询"
                assert args[1] == ["银灰是喀兰贸易的领袖"]
