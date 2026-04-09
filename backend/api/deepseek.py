"""
DeepSeek Official API client for LLM chat.
Uses DeepSeek's official API instead of SiliconFlow for better response speed.
"""

import time
from typing import List, Dict

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config


class DeepSeekClient:
    """Client for DeepSeek official API with connection pooling and retry logic."""

    def __init__(self, api_key: str = None):
        """
        Initialize DeepSeek client.

        Args:
            api_key: DeepSeek API key. If not provided, loads from config.DEEPSEEK_API_KEY.
        """
        self.api_key = api_key or config.DEEPSEEK_API_KEY
        if not self.api_key:
            raise ValueError("DeepSeek API key must be provided or set in DEEPSEEK_API_KEY environment variable.")
        self.base_url = config.DEEPSEEK_BASE_URL
        self.model = config.DEEPSEEK_LLM_MODEL

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

    def chat(self, messages: List[Dict[str, str]], model: str = None,
             temperature: float = 0.7, **kwargs) -> str:
        """
        Send chat completion request to DeepSeek.

        Args:
            messages: List of message dicts with "role" and "content" keys.
            model: LLM model to use. Defaults to config DEEPSEEK_LLM_MODEL.
            temperature: Sampling temperature. Defaults to 0.7.
            **kwargs: Additional arguments passed to the API.

        Returns:
            Assistant message content string.
        """
        model = model or self.model
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
            raise Exception(f"Invalid JSON response from {url}: {response.text[:200]}")
        return result["choices"][0]["message"]["content"]
