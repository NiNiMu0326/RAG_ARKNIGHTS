"""
SiliconFlow API client for LLM, embedding, reranking, and web search.
Uses Tavily for internet search (SiliconFlow internet search API is deprecated).
"""

from typing import List, Dict, Any

import requests

import config


class SiliconFlowClient:
    """Client for SiliconFlow API calls."""

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
        self.llm_model = config.LLM_MODEL

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

        response = requests.post(url, headers=headers, json=payload, timeout=120)
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

        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()

        try:
            result = response.json()
        except ValueError:
            raise Exception(f"Invalid JSON response from {url}: {response.text[:200]}")
        return result["results"]

    def chat(self, messages: List[Dict[str, str]], model: str = None,
             temperature: float = 0.7, **kwargs) -> str:
        """
        Send chat completion request.

        Args:
            messages: List of message dicts with "role" and "content" keys.
            model: LLM model to use. Defaults to config LLM_MODEL.
            temperature: Sampling temperature. Defaults to 0.7.
            **kwargs: Additional arguments passed to the API.

        Returns:
            Assistant message content string.
        """
        model = model or self.llm_model
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

        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()

        try:
            result = response.json()
        except ValueError:
            raise Exception(f"Invalid JSON response from {url}: {response.text[:200]}")
        return result["choices"][0]["message"]["content"]

    def chat_stream(self, messages: List[Dict[str, str]], model: str = None,
                    temperature: float = 0.7, **kwargs):
        """
        Send streaming chat completion request.

        Args:
            messages: List of message dicts with "role" and "content" keys.
            model: LLM model to use. Defaults to config LLM_MODEL.
            temperature: Sampling temperature. Defaults to 0.7.
            **kwargs: Additional arguments passed to the API.

        Yields:
            Chunks of assistant message content.
        """
        model = model or self.llm_model
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
            **kwargs
        }

        response = requests.post(url, headers=headers, json=payload, timeout=300, stream=True)
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = line[6:]  # Remove 'data: ' prefix
                    if data == '[DONE]':
                        break
                    try:
                        import json
                        chunk = json.loads(data)
                        delta = chunk.get('choices', [{}])[0].get('delta', {})
                        content = delta.get('content', '')
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

    def search(self, query: str) -> List[Dict[str, str]]:
        """
        Perform web search using Tavily internet search.

        Args:
            query: Search query string.

        Returns:
            List of search result dicts with "title", "url", and "snippet" keys.
        """
        if not self.tavily_api_key:
            raise ValueError("Tavily API key must be provided for web search. Set TAVILY_API_KEY in config or environment.")

        url = "https://api.tavily.com/search"

        headers = {
            "Content-Type": "application/json"
        }

        payload = {
            "api_key": self.tavily_api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": 10
        }

        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()

        try:
            result = response.json()
        except ValueError:
            raise Exception(f"Invalid JSON response from {url}: {response.text[:200]}")

        # Transform Tavily response to match expected format
        tavily_results = result.get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", "")
            }
            for r in tavily_results
        ]