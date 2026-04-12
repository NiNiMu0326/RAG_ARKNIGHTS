"""
DeepSeek Official API client for LLM chat.
Uses DeepSeek's official API instead of SiliconFlow for better response speed.
"""

import sys
import json
import time
import logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List, Dict, Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from backend import config

# Event types yielded by chat_with_tools_stream
STREAM_EVENT_THINKING_DELTA = "thinking_delta"
STREAM_EVENT_CONTENT_DELTA = "content_delta"
STREAM_EVENT_TOOL_CALLS = "tool_calls"
STREAM_EVENT_DONE = "done"

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

    async def chat_with_tools_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict] = None,
        model: str = None,
        temperature: float = 0.3,
        **kwargs,
    ):
        """Stream chat completion with tool support.

        Yields event dicts:
          {"type": "thinking_delta", "content": "..."}   — reasoning content chunk
          {"type": "content_delta", "delta": "..."}      — answer content chunk
          {"type": "tool_calls", "tool_calls": [...], "content": "...", "reasoning_content": "..."}
          {"type": "done", "content": "...", "reasoning_content": "...", "finish_reason": "..."}

        This uses httpx with streaming so each SSE chunk is parsed immediately.
        """
        import httpx

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
            "stream": True,
        }

        if tools:
            payload["tools"] = tools

        payload.update(kwargs)

        logger.info(f"[API STREAM CALL] POST {url} model={model} messages={len(messages)} tools={len(tools) if tools else 0}")

        # Accumulators
        reasoning_content_parts = []
        content_parts = []
        tool_calls_map = {}  # index -> {id, name, arguments_str}
        finish_reason = ""

        # State machine for parsing <think/> tags in content delta
        # Some models (MiniMax-M2.x) embed reasoning inside <think...</think > tags
        # in the content field instead of using the reasoning_content field.
        in_think_tag = False
        think_buffer = ""  # Buffer for detecting <think and </think > across chunks

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    try:
                        err_data = json.loads(body)
                        err_msg = err_data.get("error", {}).get("message", body.decode()[:300])
                    except Exception:
                        err_msg = body.decode()[:300]
                    logger.error(f"[API STREAM ERROR] {resp.status_code}: {err_msg}")
                    raise Exception(f"{resp.status_code} Error: {err_msg}")

                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]  # strip "data: "
                    if data_str == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})
                    choice_finish = choices[0].get("finish_reason")

                    if choice_finish:
                        finish_reason = choice_finish

                    # Reasoning content (DeepSeek reasoner models)
                    reasoning_delta = delta.get("reasoning_content")
                    if reasoning_delta:
                        reasoning_content_parts.append(reasoning_delta)
                        yield {"type": STREAM_EVENT_THINKING_DELTA, "content": reasoning_delta}

                    # Content delta — parse <think/> tags for models like MiniMax
                    content_delta = delta.get("content")
                    if content_delta:
                        think_buffer += content_delta
                        # Process the buffer — may contain thinking tags and/or content
                        while think_buffer:
                            if in_think_tag:
                                # Inside <think...> — look for </think closing tag
                                close_idx = think_buffer.find("</think")
                                if close_idx != -1:
                                    thinking_chunk = think_buffer[:close_idx]
                                    if thinking_chunk:
                                        reasoning_content_parts.append(thinking_chunk)
                                        yield {"type": STREAM_EVENT_THINKING_DELTA, "content": thinking_chunk}
                                    rest = think_buffer[close_idx:]
                                    close_end = rest.find(">")
                                    if close_end != -1:
                                        think_buffer = rest[close_end + 1:]
                                        in_think_tag = False
                                        # Continue loop to process remaining content (now in content mode)
                                    else:
                                        think_buffer = rest
                                        break
                                else:
                                    # No closing tag yet — check for partial "</think" at end
                                    partial_len = 0
                                    for i in range(1, min(len(think_buffer), 8) + 1):
                                        if "</think"[:i] == think_buffer[-i:]:
                                            partial_len = i
                                    if partial_len > 0:
                                        emit_part = think_buffer[:-partial_len]
                                        if emit_part:
                                            reasoning_content_parts.append(emit_part)
                                            yield {"type": STREAM_EVENT_THINKING_DELTA, "content": emit_part}
                                        think_buffer = think_buffer[-partial_len:]
                                        break
                                    else:
                                        reasoning_content_parts.append(think_buffer)
                                        yield {"type": STREAM_EVENT_THINKING_DELTA, "content": think_buffer}
                                        think_buffer = ""
                                        break
                            else:
                                # Not inside <think...> — look for opening <think tag
                                open_idx = think_buffer.find("<think")
                                if open_idx != -1:
                                    before = think_buffer[:open_idx]
                                    if before:
                                        content_parts.append(before)
                                        yield {"type": STREAM_EVENT_CONTENT_DELTA, "delta": before}
                                    rest = think_buffer[open_idx:]
                                    import re
                                    self_close_match = re.match(r"<think\s*/>", rest)
                                    if self_close_match:
                                        think_buffer = rest[self_close_match.end():]
                                    else:
                                        gt_idx = rest.find(">")
                                        if gt_idx != -1:
                                            think_buffer = rest[gt_idx + 1:]
                                            in_think_tag = True
                                        else:
                                            break
                                else:
                                    # No <think tag — check for partial "<think" at end
                                    partial_start = -1
                                    for i in range(min(len(think_buffer), 6)):
                                        suffix = think_buffer[-(i+1):]
                                        if "<think"[:i+1] == suffix:
                                            partial_start = len(think_buffer) - (i+1)
                                            break
                                    if partial_start >= 0:
                                        before = think_buffer[:partial_start]
                                        if before:
                                            content_parts.append(before)
                                            yield {"type": STREAM_EVENT_CONTENT_DELTA, "delta": before}
                                        think_buffer = think_buffer[partial_start:]
                                        break
                                    else:
                                        content_parts.append(think_buffer)
                                        yield {"type": STREAM_EVENT_CONTENT_DELTA, "delta": think_buffer}
                                        think_buffer = ""
                                        break

                    # Tool calls delta
                    tc_deltas = delta.get("tool_calls")
                    if tc_deltas:
                        for tc_delta in tc_deltas:
                            idx = tc_delta.get("index", 0)
                            if idx not in tool_calls_map:
                                tool_calls_map[idx] = {
                                    "id": "",
                                    "name": "",
                                    "arguments_str": "",
                                }
                            entry = tool_calls_map[idx]
                            if tc_delta.get("id"):
                                entry["id"] = tc_delta["id"]
                            fn = tc_delta.get("function", {})
                            if fn.get("name"):
                                entry["name"] = fn["name"]
                            if fn.get("arguments"):
                                entry["arguments_str"] += fn["arguments"]

        # Flush any remaining think_buffer content after stream ends
        if think_buffer:
            if in_think_tag:
                # Still in think tag at end of stream — treat as thinking
                reasoning_content_parts.append(think_buffer)
                yield {"type": STREAM_EVENT_THINKING_DELTA, "content": think_buffer}
            else:
                # Not in think tag — treat as answer content
                content_parts.append(think_buffer)
                yield {"type": STREAM_EVENT_CONTENT_DELTA, "delta": think_buffer}
            think_buffer = ""

        # Build final results
        full_content = "".join(content_parts)
        full_reasoning = "".join(reasoning_content_parts)

        # Build tool_calls list if any
        tool_calls_list = None
        if tool_calls_map:
            tool_calls_list = []
            for idx in sorted(tool_calls_map.keys()):
                entry = tool_calls_map[idx]
                tool_calls_list.append(ToolCall(
                    id=entry["id"],
                    name=entry["name"],
                    arguments=entry["arguments_str"],
                ))

        if tool_calls_list:
            yield {
                "type": STREAM_EVENT_TOOL_CALLS,
                "tool_calls": tool_calls_list,
                "content": full_content,
                "reasoning_content": full_reasoning,
            }
        else:
            yield {
                "type": STREAM_EVENT_DONE,
                "content": full_content,
                "reasoning_content": full_reasoning,
                "finish_reason": finish_reason,
            }
