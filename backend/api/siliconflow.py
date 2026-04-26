"""
SiliconFlow API client for embedding, reranking, and LLM chat.
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

    def __init__(self, api_key: str = None):
        """
        Initialize SiliconFlow client.

        Args:
            api_key: SiliconFlow API key. If not provided, loads from config.SILICONFLOW_API_KEY.
        """
        self.api_key = api_key or config.SILICONFLOW_API_KEY
        if not self.api_key:
            raise ValueError("API key must be provided or set in SILICONFLOW_API_KEY environment variable.")
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

    def chat(self, messages: List[Dict[str, str]], model: str = None,
             temperature: float = 0.7, **kwargs) -> str:
        """Send chat completion request via SiliconFlow."""
        model = model or "Pro/deepseek-ai/DeepSeek-V3"
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
