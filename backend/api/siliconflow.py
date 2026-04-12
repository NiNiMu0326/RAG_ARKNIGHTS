"""
SiliconFlow API client for LLM, embedding, reranking, and web search.
Uses Tavily for internet search (SiliconFlow internet search API is deprecated).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List, Dict, Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from backend import config


class SiliconFlowClient:
    """Client for SiliconFlow API calls with connection pooling and retry logic."""

    def __init__(self, api_key: str = None, tavily_api_key: str = None):
        """
        Initialize SiliconFlow client.

        Args:
            api_key: SiliconFlow API key. If not provided, loads from config.SILICONFLOW_API_KEY.
            tavily_api_key: Tavily API key for internet search. If not provided, loads from config.TAVILY_API_KEY.
        """
        self.api_key = api_key or config.SILICONFLOW_API_KEY
        if not self.api_key:
            raise ValueError("API key must be provided or set in SILICONFLOW_API_KEY environment variable.")
        self.tavily_api_key = tavily_api_key or getattr(config, 'TAVILY_API_KEY', None)
        self.base_url = config.SILICONFLOW_BASE_URL
        self.embedding_model = config.EMBEDDING_MODEL
        self.reranker_model = config.RERANKER_MODEL
        # Create session with connection pooling and retry logic
        self._session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST", "GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

    def embed(self, texts: List[str], model: str = None) -> List[List[float]]:
        """
        Generate embeddings for texts.

        Args:
            texts: List of text strings to embed.
            model: Embedding model to use. Defaults to config EMBEDDING_MODEL.

        Returns:
            List of embedding vectors (each vector is a list of floats).
        """
        if not texts:
            return []
        model = model or self.embedding_model
        url = f"{self.base_url}/embeddings"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "input": texts
        }

        response = self._session.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()

        try:
            result = response.json()
        except ValueError:
            raise Exception(f"Invalid JSON response from {url}: {response.text[:200]}")
        return [item["embedding"] for item in result["data"]]

    def rerank(self, query: str, documents: List[str], model: str = None) -> List[Dict[str, Any]]:
        """
        Rerank documents based on query relevance.

        Args:
            query: The query string.
            documents: List of document strings to rerank.
            model: Reranker model to use. Defaults to config RERANKER_MODEL.

        Returns:
            List of dicts with "index" and "relevance_score" keys.
        """
        if not documents:
            return []
        model = model or self.reranker_model
        url = f"{self.base_url}/rerank"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "query": query,
            "documents": documents
        }

        response = self._session.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()

        try:
            result = response.json()
        except ValueError:
            raise Exception(f"Invalid JSON response from {url}: {response.text[:200]}")
        return result["results"]

    def search(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Perform web search. Tries Tavily first, falls back to DuckDuckGo Lite.

        Args:
            query: Search query string.
            limit: Maximum number of results to return (default: 10).

        Returns:
            List of search result dicts with "title", "url", and "snippet" keys.
        """
        # Try Tavily first
        if self.tavily_api_key:
            try:
                return self._search_tavily(query, limit)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Tavily search failed: {e}, falling back to DuckDuckGo")

        # Fallback to DuckDuckGo Lite (no API key needed)
        return self._search_duckduckgo(query, limit)

    def _search_tavily(self, query: str, limit: int) -> List[Dict[str, str]]:
        """Search using Tavily API."""
        url = "https://api.tavily.com/search"
        headers = {"Content-Type": "application/json"}
        payload = {
            "api_key": self.tavily_api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": limit
        }
        response = self._session.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        tavily_results = result.get("results", [])
        return [
            {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")}
            for r in tavily_results[:limit]
        ]

    def _search_duckduckgo(self, query: str, limit: int) -> List[Dict[str, str]]:
        """Search using DuckDuckGo Lite HTML (no API key needed, free)."""
        import re
        import logging
        logger = logging.getLogger(__name__)

        url = "https://lite.duckduckgo.com/lite/"
        # GET the search form first to get a token
        try:
            resp = self._session.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            # Extract vqd token from the page
            vqd_match = re.search(r'name="vqd"\s+value="([^"]+)"', resp.text)
            if not vqd_match:
                vqd_match = re.search(r'vqd=([^&"]+)', resp.text)
            vqd = vqd_match.group(1) if vqd_match else ""

            # POST the search query
            data = {"q": query, "vqd": vqd, "kl": "wt-wt", "l": "wt-wt"}
            resp = self._session.post(url, data=data, timeout=15,
                                       headers={"User-Agent": "Mozilla/5.0"})
            html = resp.text

            # Parse results from the HTML table
            results = []
            # Each result is in a <tr class="result-link"> followed by a <tr class="result-snippet">
            result_blocks = re.findall(
                r'<a[^>]+class="result-link"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?'
                r'<td[^>]*class="result-snippet"[^>]*>(.*?)</td>',
                html, re.DOTALL
            )
            for href, title_html, snippet_html in result_blocks[:limit]:
                title = re.sub(r'<[^>]+>', '', title_html).strip()
                snippet = re.sub(r'<[^>]+>', '', snippet_html).strip()
                if title and snippet:
                    results.append({
                        "title": title,
                        "url": href,
                        "snippet": snippet,
                    })

            if not results:
                # Fallback: parse any links from the page
                links = re.findall(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
                for href, title_html in links[:limit]:
                    title = re.sub(r'<[^>]+>', '', title_html).strip()
                    if title and len(title) > 5 and 'duckduckgo' not in href.lower():
                        results.append({"title": title, "url": href, "snippet": ""})

            logger.info(f"[DuckDuckGo] got {len(results)} results for: {query}")
            return results[:limit]

        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")
            return []

    def chat(self, messages: List[Dict[str, str]], model: str = None,
             temperature: float = 0.7, **kwargs) -> str:
        """Send chat completion request via SiliconFlow."""
        model = model or "Pro/Qwen/Qwen2.5-7B-Instruct"
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            **kwargs
        }

        response = self._session.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()

        try:
            result = response.json()
        except ValueError:
            raise Exception(f"Invalid JSON response: {response.text[:200]}")
        return result["choices"][0]["message"]["content"]
