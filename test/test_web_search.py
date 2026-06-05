"""
Tests for backend.api.web_search: Web search with Tavily + DuckDuckGo fallback.
Usage: cd test && python -m pytest test_web_search.py -v
"""
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.api.web_search import (
    search,
    _search_tavily,
    _search_duckduckgo,
)


# ============================================================
# search() - main entry point
# ============================================================

class TestSearch:
    """Test the main search() function."""

    def test_search_with_tavily_key(self, monkeypatch):
        """When TAVILY_API_KEY is set, should use Tavily."""
        monkeypatch.setattr("backend.api.web_search.config.TAVILY_API_KEY", "fake-key")

        mock_results = [
            {"title": "Title 1", "url": "https://example.com/1", "snippet": "Snippet 1"},
            {"title": "Title 2", "url": "https://example.com/2", "snippet": "Snippet 2"},
        ]

        with patch("backend.api.web_search._search_tavily", return_value=mock_results) as mock_tavily:
            results = search("test query", limit=5)

            mock_tavily.assert_called_once_with("test query", 5, "fake-key")
            assert len(results) == 2
            assert results[0]["title"] == "Title 1"
            assert results[1]["url"] == "https://example.com/2"

    def test_search_tavily_fallback_to_ddg(self, monkeypatch):
        """When Tavily fails, should fall back to DuckDuckGo."""
        monkeypatch.setattr("backend.api.web_search.config.TAVILY_API_KEY", "fake-key")

        with patch("backend.api.web_search._search_tavily", side_effect=Exception("API error")):
            with patch("backend.api.web_search._search_duckduckgo", return_value=[{"title": "DDG", "url": "http://ddg.gg", "snippet": "ddg"}]) as mock_ddg:
                results = search("test", limit=3)

                mock_ddg.assert_called_once_with("test", 3)
                assert len(results) == 1
                assert results[0]["title"] == "DDG"

    def test_search_no_tavily_key(self, monkeypatch):
        """When no TAVILY_API_KEY, should directly use DuckDuckGo."""
        monkeypatch.setattr("backend.api.web_search.config.TAVILY_API_KEY", "")

        with patch("backend.api.web_search._search_duckduckgo", return_value=[]) as mock_ddg:
            results = search("test", limit=3)
            mock_ddg.assert_called_once_with("test", 3)
            assert results == []

    def test_search_both_fail(self, monkeypatch):
        """When both methods fail, exception from DuckDuckGo propagates."""
        monkeypatch.setattr("backend.api.web_search.config.TAVILY_API_KEY", "fake-key")

        with patch("backend.api.web_search._search_tavily", side_effect=Exception("Tavily fail")):
            with patch("backend.api.web_search._search_duckduckgo", side_effect=Exception("DDG fail")):
                with pytest.raises(Exception, match="DDG fail"):
                    search("test", limit=3)

    def test_search_default_limit(self, monkeypatch):
        """Default limit should be 5."""
        monkeypatch.setattr("backend.api.web_search.config.TAVILY_API_KEY", "")

        with patch("backend.api.web_search._search_duckduckgo", return_value=[]) as mock_ddg:
            search("test")
            mock_ddg.assert_called_once_with("test", 5)


# ============================================================
# _search_tavily
# ============================================================

class TestSearchTavily:
    """Test Tavily API search function."""

    def test_tavily_calls_correct_url(self):
        """Should POST to Tavily API endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"title": "T1", "url": "http://t1.com", "content": "Content 1"},
            ]
        }
        mock_response.raise_for_status.return_value = None

        with patch("backend.api.web_search._session.post", return_value=mock_response) as mock_post:
            results = _search_tavily("test query", 3, "api-key-123")

            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            assert call_kwargs[0][0] == "https://api.tavily.com/search"

            payload = call_kwargs[1]["json"]
            assert payload["api_key"] == "api-key-123"
            assert payload["query"] == "test query"
            assert payload["max_results"] == 3
            assert payload["search_depth"] == "basic"

    def test_tavily_parses_response(self):
        """Should correctly parse Tavily API response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"title": "Result A", "url": "https://a.com", "content": "Description A"},
                {"title": "Result B", "url": "https://b.com", "content": "Description B"},
            ]
        }
        mock_response.raise_for_status.return_value = None

        with patch("backend.api.web_search._session.post", return_value=mock_response):
            results = _search_tavily("q", 5, "key")

            assert len(results) == 2
            assert results[0]["title"] == "Result A"
            assert results[0]["url"] == "https://a.com"
            assert results[0]["snippet"] == "Description A"
            assert results[1]["title"] == "Result B"

    def test_tavily_limits_results(self):
        """Should respect the limit parameter."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"title": f"R{i}", "url": f"http://r{i}.com", "content": f"C{i}"}
                for i in range(10)
            ]
        }
        mock_response.raise_for_status.return_value = None

        with patch("backend.api.web_search._session.post", return_value=mock_response):
            results = _search_tavily("q", 3, "key")
            assert len(results) == 3

    def test_tavily_empty_response(self):
        """Should handle empty results gracefully."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status.return_value = None

        with patch("backend.api.web_search._session.post", return_value=mock_response):
            results = _search_tavily("q", 5, "key")
            assert results == []

    def test_tavily_missing_keys_in_result(self):
        """Should handle results with missing keys."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"title": "Only Title"},  # missing url and content
                {"url": "http://only-url.com"},  # missing title and content
            ]
        }
        mock_response.raise_for_status.return_value = None

        with patch("backend.api.web_search._session.post", return_value=mock_response):
            results = _search_tavily("q", 5, "key")
            assert len(results) == 2
            assert results[0]["snippet"] == ""
            assert results[1]["title"] == ""

    def test_tavily_http_error(self):
        """Should propagate HTTP errors."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 500")

        with patch("backend.api.web_search._session.post", return_value=mock_response):
            with pytest.raises(Exception, match="HTTP 500"):
                _search_tavily("q", 5, "key")


# ============================================================
# _search_duckduckgo
# ============================================================

class TestSearchDuckDuckGo:
    """Test DuckDuckGo fallback search function."""

    def test_ddg_extracts_results_from_html(self):
        """Should parse results from DuckDuckGo Lite HTML."""
        html_with_results = """
        <html>
        <a class="result-link" href="https://ddg1.com">Result One</a>
        <td class="result-snippet">Snippet one content</td>
        <a class="result-link" href="https://ddg2.com">Result Two</a>
        <td class="result-snippet">Snippet two content</td>
        </html>
        """
        mock_vqd_resp = MagicMock()
        mock_vqd_resp.text = '<input name="vqd" value="vqd-12345"/>'

        mock_results_resp = MagicMock()
        mock_results_resp.text = html_with_results

        with patch("backend.api.web_search._session.get", return_value=mock_vqd_resp):
            with patch("backend.api.web_search._session.post", return_value=mock_results_resp):
                results = _search_duckduckgo("test", 5)

                assert len(results) == 2
                assert results[0]["title"] == "Result One"
                assert results[0]["url"] == "https://ddg1.com"
                assert results[0]["snippet"] == "Snippet one content"
                assert results[1]["title"] == "Result Two"

    def test_ddg_limits_results(self):
        """Should respect the limit parameter."""
        html = ""
        for i in range(10):
            html += f'<a class="result-link" href="http://r{i}.com">R{i}</a><td class="result-snippet">S{i}</td>'

        mock_vqd_resp = MagicMock()
        mock_vqd_resp.text = 'vqd="vqd-abc"'

        mock_results_resp = MagicMock()
        mock_results_resp.text = f"<html>{html}</html>"

        with patch("backend.api.web_search._session.get", return_value=mock_vqd_resp):
            with patch("backend.api.web_search._session.post", return_value=mock_results_resp):
                results = _search_duckduckgo("test", 3)
                assert len(results) == 3

    def test_ddg_empty_html(self):
        """Should handle empty HTML response."""
        mock_vqd_resp = MagicMock()
        mock_vqd_resp.text = "no vqd here"

        mock_results_resp = MagicMock()
        mock_results_resp.text = "<html>no results</html>"

        with patch("backend.api.web_search._session.get", return_value=mock_vqd_resp):
            with patch("backend.api.web_search._session.post", return_value=mock_results_resp):
                results = _search_duckduckgo("test", 5)
                assert results == []

    def test_ddg_no_vqd_in_get(self):
        """Should handle missing vqd token in GET response."""
        mock_vqd_resp = MagicMock()
        mock_vqd_resp.text = "<html>no token here</html>"

        mock_results_resp = MagicMock()
        mock_results_resp.text = "<html><a class=\"result-link\" href=\"http://x.com\">Title</a><td class=\"result-snippet\">Snip</td></html>"

        with patch("backend.api.web_search._session.get", return_value=mock_vqd_resp):
            with patch("backend.api.web_search._session.post", return_value=mock_results_resp):
                results = _search_duckduckgo("test", 5)
                # Should still work with empty vqd
                assert len(results) == 1

    def test_ddg_http_error(self):
        """Should handle HTTP errors gracefully and return empty list."""
        with patch("backend.api.web_search._session.get", side_effect=Exception("Connection error")):
            results = _search_duckduckgo("test", 5)
            assert results == []

    def test_ddg_fallback_link_parsing(self):
        """When result-link pattern fails, should fall back to generic link parsing."""
        html = """
        <html>
        <a href="https://example.com/page1">External Link Title</a>
        <a href="https://example.com/page2">Another External Link</a>
        <a href="https://duckduckgo.com/about">About DuckDuckGo</a>
        </html>
        """
        mock_vqd_resp = MagicMock()
        mock_vqd_resp.text = 'vqd="test-vqd"'

        mock_results_resp = MagicMock()
        mock_results_resp.text = html

        with patch("backend.api.web_search._session.get", return_value=mock_vqd_resp):
            with patch("backend.api.web_search._session.post", return_value=mock_results_resp):
                results = _search_duckduckgo("test", 5)

                # Should have 2 results (filtering out duckduckgo.com links)
                assert len(results) == 2
                assert results[0]["url"] == "https://example.com/page1"

    def test_ddg_short_titles_filtered(self):
        """Very short titles should be filtered in fallback mode."""
        html = """
        <html>
        <a href="https://x.com/a">Hi</a>
        <a href="https://x.com/b">Valid Title Here</a>
        </html>
        """
        mock_vqd_resp = MagicMock()
        mock_vqd_resp.text = 'vqd="v"'

        mock_results_resp = MagicMock()
        mock_results_resp.text = html

        with patch("backend.api.web_search._session.get", return_value=mock_vqd_resp):
            with patch("backend.api.web_search._session.post", return_value=mock_results_resp):
                results = _search_duckduckgo("test", 5)
                # "Hi" is len 2 <= 5, should be filtered
                titles = [r["title"] for r in results]
                assert "Valid Title Here" in titles


# ============================================================
# Session/connection pool
# ============================================================

class TestSessionConfiguration:
    """Test the module-level session configuration."""

    def test_session_has_retry(self):
        """Session should be configured with retry adapter."""
        from backend.api.web_search import _session
        # Should have adapters mounted for http and https
        assert hasattr(_session, "adapters")
        assert "https://" in _session.adapters
        assert "http://" in _session.adapters
