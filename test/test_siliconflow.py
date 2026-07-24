"""
Tests for backend.api.siliconflow: SiliconFlowClient.
Usage: cd test && python -m pytest test_siliconflow.py -v
"""
import sys
import json
import pytest
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests


# ============================================================
# SiliconFlowClient unit tests (with mocked HTTP)
# ============================================================

class TestSiliconFlowClientInit:
    """Test SiliconFlowClient initialization."""

    def test_init_with_api_key(self):
        from backend.api.siliconflow import SiliconFlowClient
        client = SiliconFlowClient(api_key="sk-test-key")
        assert client.api_key == "sk-test-key"

    def test_init_requires_api_key(self):
        """Should raise ValueError if no API key is available."""
        from backend.api.siliconflow import SiliconFlowClient
        with mock.patch('backend.api.siliconflow.config') as mock_config:
            mock_config.SILICONFLOW_API_KEY = ""
            with pytest.raises(ValueError, match="API key must be provided"):
                SiliconFlowClient(api_key=None)

    def test_init_defaults_to_config(self):
        from backend.api.siliconflow import SiliconFlowClient
        with mock.patch('backend.api.siliconflow.config') as mock_config:
            mock_config.SILICONFLOW_API_KEY = "sk-from-config"
            mock_config.SILICONFLOW_BASE_URL = "https://api.test.com/v1"
            mock_config.EMBEDDING_MODEL = "test-embed-model"
            mock_config.RERANKER_MODEL = "test-rerank-model"
            client = SiliconFlowClient(api_key=None)
            assert client.api_key == "sk-from-config"

    def test_init_uses_config_base_url(self):
        from backend.api.siliconflow import SiliconFlowClient
        with mock.patch('backend.api.siliconflow.config') as mock_config:
            mock_config.SILICONFLOW_API_KEY = "sk-test"
            mock_config.SILICONFLOW_BASE_URL = "https://custom.api.com/v1"
            mock_config.EMBEDDING_MODEL = "embed-model"
            mock_config.RERANKER_MODEL = "rerank-model"
            client = SiliconFlowClient(api_key=None)
            assert client.base_url == "https://custom.api.com/v1"


class TestSiliconFlowClientEmbed:
    """Test the embed method."""

    @pytest.fixture
    def client(self):
        from backend.api.siliconflow import SiliconFlowClient
        return SiliconFlowClient(api_key="sk-test")

    def test_embed_empty_texts(self, client):
        result = client.embed([])
        assert result == []

    def test_embed_single_text(self, client):
        mock_response = mock.MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1, 0.2, 0.3], "index": 0}]
        }
        mock_response.raise_for_status = mock.MagicMock()

        with mock.patch.object(client._session, 'post', return_value=mock_response):
            result = client.embed(["测试文本"])
            assert len(result) == 1
            assert result[0] == [0.1, 0.2, 0.3]

    def test_embed_multiple_texts(self, client):
        mock_response = mock.MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"embedding": [1.0, 0.0], "index": 0},
                {"embedding": [0.0, 1.0], "index": 1},
            ]
        }
        mock_response.raise_for_status = mock.MagicMock()

        with mock.patch.object(client._session, 'post', return_value=mock_response):
            result = client.embed(["文本A", "文本B"])
            assert len(result) == 2
            assert result[0] == [1.0, 0.0]
            assert result[1] == [0.0, 1.0]

    def test_embed_uses_custom_model(self, client):
        mock_response = mock.MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.5], "index": 0}]
        }
        mock_response.raise_for_status = mock.MagicMock()

        with mock.patch.object(client._session, 'post', return_value=mock_response) as mock_post:
            client.embed(["text"], model="custom/model")
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            assert payload['model'] == "custom/model"

    def test_embed_uses_default_model(self, client):
        mock_response = mock.MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.5], "index": 0}]
        }
        mock_response.raise_for_status = mock.MagicMock()

        with mock.patch.object(client._session, 'post', return_value=mock_response) as mock_post:
            client.embed(["text"])
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            assert payload['model'] == client.embedding_model

    def test_embed_invalid_json_response(self, client):
        mock_response = mock.MagicMock()
        mock_response.json.side_effect = ValueError("not json")
        mock_response.text = "invalid response text"
        mock_response.raise_for_status = mock.MagicMock()

        with mock.patch.object(client._session, 'post', return_value=mock_response):
            with pytest.raises(Exception, match="Invalid JSON response"):
                client.embed(["text"])

    def test_embed_http_error(self, client):
        mock_response = mock.MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")

        with mock.patch.object(client._session, 'post', return_value=mock_response):
            with pytest.raises(requests.HTTPError):
                client.embed(["text"])


class TestSiliconFlowClientRerank:
    """Test the rerank method."""

    @pytest.fixture
    def client(self):
        from backend.api.siliconflow import SiliconFlowClient
        return SiliconFlowClient(api_key="sk-test")

    def test_rerank_empty_documents(self, client):
        result = client.rerank("query", [])
        assert result == []

    def test_rerank_with_documents(self, client):
        mock_response = mock.MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"index": 0, "relevance_score": 0.95},
                {"index": 1, "relevance_score": 0.30},
            ]
        }
        mock_response.raise_for_status = mock.MagicMock()

        with mock.patch.object(client._session, 'post', return_value=mock_response):
            result = client.rerank("银灰是谁", ["银灰是喀兰贸易领袖", "阿米娅是罗德岛CEO"])
            assert len(result) == 2
            assert result[0]["index"] == 0
            assert result[1]["relevance_score"] == 0.30

    def test_rerank_uses_custom_model(self, client):
        mock_response = mock.MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = mock.MagicMock()

        with mock.patch.object(client._session, 'post', return_value=mock_response) as mock_post:
            client.rerank("q", ["doc"], model="custom/reranker")
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            assert payload['model'] == "custom/reranker"

    def test_rerank_invalid_json(self, client):
        mock_response = mock.MagicMock()
        mock_response.json.side_effect = ValueError("not json")
        mock_response.text = "bad response"
        mock_response.raise_for_status = mock.MagicMock()

        with mock.patch.object(client._session, 'post', return_value=mock_response):
            with pytest.raises(Exception, match="Invalid JSON response"):
                client.rerank("q", ["doc"])

    def test_rerank_http_error(self, client):
        mock_response = mock.MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("503 Service Unavailable")

        with mock.patch.object(client._session, 'post', return_value=mock_response):
            with pytest.raises(requests.HTTPError):
                client.rerank("q", ["doc"])
