"""
DeepSeek Official API client for LLM chat.
Uses DeepSeek's official API instead of SiliconFlow for better response speed.
"""

import sys
import logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List, Dict, Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from backend import config

logger = logging.getLogger(__name__)


class ToolCall:
    """Represents a single tool call from the model."""
    def __init__(self, id: str, name: str, arguments: str):
        self.id = id
        self.name = name
        self.arguments = arguments  # JSON string

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": self.arguments,
            }
        }


class ChatResponse:
    """Response from chat completion, may contain content and/or tool_calls."""
    def __init__(self, content: Optional[str] = None, tool_calls: Optional[List[ToolCall]] = None,
                 finish_reason: str = "", reasoning_content: str = ""):
        self.content = content or ""
        self.tool_calls = tool_calls
        self.finish_reason = finish_reason
        self.reasoning_content = reasoning_content or ""

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


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
        if response.status_code != 200:
            try:
                err_data = response.json()
                err_msg = err_data.get("error", {}).get("message", response.text[:300])
            except ValueError:
                err_msg = response.text[:300]
            logger.error(f"[API ERROR] {response.status_code} from {url}: {err_msg}")
            raise Exception(f"{response.status_code} Error: {err_msg}")

        try:
            result = response.json()
        except ValueError:
            raise Exception(f"Invalid JSON response from {url}: {response.text[:200]}")
        return result["choices"][0]["message"]["content"]

    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict] = None,
        model: str = None,
        temperature: float = 0.3,
        **kwargs,
    ) -> ChatResponse:
        """Send chat completion with tool support (Function Calling).
        
        IMPORTANT: Do NOT pass parallel_tool_calls parameter.
        DeepSeek-chat natively supports parallel tool_calls without it,
        and passing it makes the model MORE conservative (returns fewer parallel calls).
        
        Args:
            messages: List of message dicts. May include role="tool" messages.
            tools: List of tool definitions in OpenAI function calling format.
            model: LLM model. Defaults to config.
            temperature: Sampling temperature. Lower for more deterministic tool usage.
            **kwargs: Additional API arguments.
            
        Returns:
            ChatResponse with content and/or tool_calls.
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
        }
        
        if tools:
            payload["tools"] = tools

        payload.update(kwargs)

        logger.info(f"[API CALL] POST {url} model={model} messages={len(messages)} tools={len(tools) if tools else 0}")
        response = self._session.post(url, headers=headers, json=payload, timeout=120)
        if response.status_code != 200:
            try:
                err_data = response.json()
                err_msg = err_data.get("error", {}).get("message", response.text[:300])
            except ValueError:
                err_msg = response.text[:300]
            logger.error(f"[API ERROR] {response.status_code} from {url}: {err_msg}")
            raise Exception(f"{response.status_code} Error: {err_msg}")

        try:
            result = response.json()
        except ValueError:
            raise Exception(f"Invalid JSON response from {url}: {response.text[:200]}")

        choice = result["choices"][0]
        message = choice["message"]
        content = message.get("content") or ""
        finish_reason = choice.get("finish_reason", "")

        # Extract reasoning_content if present (DeepSeek reasoner models)
        reasoning_content = message.get("reasoning_content") or ""

        # Parse tool_calls if present
        tool_calls = None
        raw_tool_calls = message.get("tool_calls")
        if raw_tool_calls:
            tool_calls = []
            for tc in raw_tool_calls:
                fn = tc.get("function", {})
                tool_calls.append(ToolCall(
                    id=tc.get("id", ""),
                    name=fn.get("name", ""),
                    arguments=fn.get("arguments", "{}"),
                ))

        return ChatResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            reasoning_content=reasoning_content,
        )
