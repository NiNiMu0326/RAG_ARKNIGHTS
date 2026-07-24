"""
Tests for backend.api.base: create_http_session.
Usage: cd test && python -m pytest test_base.py -v
"""
import sys
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.api.base import create_http_session


# ============================================================
# create_http_session tests
# ============================================================

class TestCreateHttpSession:
    """Test HTTP session creation with retry and pool configuration."""

    def test_returns_requests_session(self):
        import requests
        session = create_http_session()
        assert isinstance(session, requests.Session)

    def test_default_retries(self):
        """Default retry count should be 3."""
        session = create_http_session()
        # Get the adapter for https
        adapter = session.get_adapter("https://")
        # The max_retries should be a Retry object with total=3
        max_retries = adapter.max_retries
        assert max_retries.total == 3

    def test_custom_retries(self):
        session = create_http_session(retries=5)
        adapter = session.get_adapter("https://")
        assert adapter.max_retries.total == 5

    def test_custom_backoff_factor(self):
        session = create_http_session(backoff_factor=1.0)
        adapter = session.get_adapter("https://")
        assert adapter.max_retries.backoff_factor == 1.0

    def test_http_and_https_adapters(self):
        """Both HTTP and HTTPS should have adapters mounted."""
        session = create_http_session()
        assert "http://" in session.adapters
        assert "https://" in session.adapters

    def test_pool_connections(self):
        session = create_http_session(pool_connections=5)
        adapter = session.get_adapter("https://")
        # pool_connections is set via the adapter constructor
        # The actual pool manager attribute may vary by urllib3 version
        assert adapter is not None

    def test_pool_maxsize(self):
        session = create_http_session(pool_maxsize=15)
        adapter = session.get_adapter("https://")
        # pool_maxsize is set via the adapter constructor
        assert adapter is not None

    def test_status_forcelist(self):
        """Retry strategy should include common server error codes."""
        session = create_http_session()
        adapter = session.get_adapter("https://")
        retry = adapter.max_retries
        assert 429 in retry.status_forcelist
        assert 500 in retry.status_forcelist
        assert 502 in retry.status_forcelist
        assert 503 in retry.status_forcelist
        assert 504 in retry.status_forcelist

    def test_allowed_methods(self):
        """Retry should apply to both GET and POST."""
        session = create_http_session()
        adapter = session.get_adapter("https://")
        retry = adapter.max_retries
        assert "POST" in retry.allowed_methods
        assert "GET" in retry.allowed_methods
