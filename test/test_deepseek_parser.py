"""
Tests for backend.api.deepseek: real ThinkTagParser, _partial_suffix_len,
and chat_with_tools_stream against a mocked httpx streaming layer.

Unlike test_deepseek_think.py (which tests a simulated copy of the logic),
these tests exercise the actual production classes.
Usage: cd test && python -m pytest test_deepseek_parser.py -v
"""
import asyncio
import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.api.deepseek import (
    DeepSeekClient,
    ThinkTagParser,
    ToolCall,
    _partial_suffix_len,
    STREAM_EVENT_THINKING_DELTA,
    STREAM_EVENT_CONTENT_DELTA,
    STREAM_EVENT_TOOL_CALLS,
    STREAM_EVENT_DONE,
)


def run_parser(chunks):
    """Feed chunks through the real ThinkTagParser and collect fragments."""
    p = ThinkTagParser()
    out = []
    for c in chunks:
        out.extend(p.feed(c))
    out.extend(p.flush())
    return out


def joined(fragments, kind):
    return "".join(t for k, t in fragments if k == kind)


# ============================================================
# _partial_suffix_len
# ============================================================

class TestPartialSuffixLen:
    def test_full_prefix_match(self):
        assert _partial_suffix_len("abc<think", "<think", 6) == 6

    def test_partial_match(self):
        assert _partial_suffix_len("hello<thi", "<think", 6) == 4

    def test_no_match(self):
        assert _partial_suffix_len("hello", "<think", 6) == 0

    def test_empty_string(self):
        assert _partial_suffix_len("", "<think", 6) == 0

    def test_shorter_than_prefix(self):
        assert _partial_suffix_len("<t", "<think", 6) == 2


# ============================================================
# ThinkTagParser (real implementation)
# ============================================================

class TestThinkTagParserReal:
    def test_plain_content(self):
        frags = run_parser(["hello world"])
        assert joined(frags, "content") == "hello world"
        assert joined(frags, "think") == ""

    def test_complete_think_block_single_chunk(self):
        frags = run_parser(["<think>reasoning</think>answer"])
        assert joined(frags, "think") == "reasoning"
        assert joined(frags, "content") == "answer"

    def test_open_tag_split_across_chunks(self):
        frags = run_parser(["<thi", "nk>thinking text</think>real answer"])
        assert joined(frags, "think") == "thinking text"
        assert joined(frags, "content") == "real answer"

    def test_close_tag_split_across_chunks(self):
        frags = run_parser(["<think>reasoning</thi", "nk>answer"])
        assert joined(frags, "think") == "reasoning"
        assert joined(frags, "content") == "answer"

    def test_partial_close_tag_suffix_held_back(self):
        # "</th" at buffer end must not be emitted as thinking yet
        p = ThinkTagParser()
        out1 = list(p.feed("<think>abc</th"))
        assert joined(out1, "think") == "abc"
        out2 = list(p.feed("ink>done"))
        assert joined(out2, "content") == "done"

    def test_partial_open_tag_suffix_held_back(self):
        p = ThinkTagParser()
        out1 = list(p.feed("text<th"))
        assert joined(out1, "content") == "text"
        out2 = list(p.feed("ink>thinking</think>rest"))
        assert joined(out2, "think") == "thinking"
        assert joined(out2, "content") == "rest"

    def test_self_closing_tag_skipped(self):
        frags = run_parser(["before <think/> after"])
        assert joined(frags, "content") == "before  after"
        assert joined(frags, "think") == ""

    def test_think_tag_with_attributes(self):
        frags = run_parser(['<think process="reasoning">inner</think>outer'])
        assert joined(frags, "think") == "inner"
        assert joined(frags, "content") == "outer"

    def test_multiple_think_blocks(self):
        frags = run_parser(["<think>one</think>mid<think>two</think>final"])
        assert joined(frags, "think") == "onetwo"
        assert joined(frags, "content") == "midfinal"

    def test_unclosed_think_flushed_as_thinking(self):
        frags = run_parser(["<think>unfinished"])
        assert joined(frags, "think") == "unfinished"
        assert joined(frags, "content") == ""

    def test_unflushed_plain_content_flushed_as_content(self):
        p = ThinkTagParser()
        out = list(p.feed("abc<th"))  # partial tag held
        out += list(p.flush())  # stream ends without completing tag
        # The held-back "<th" is emitted as content on flush
        assert joined(out, "content") == "abc<th"

    def test_chinese_content(self):
        frags = run_parser(["<think>我在思考</think>这是答案"])
        assert joined(frags, "think") == "我在思考"
        assert joined(frags, "content") == "这是答案"

    def test_empty_feed(self):
        frags = run_parser([])
        assert frags == []


# ============================================================
# chat_with_tools_stream (mocked httpx)
# ============================================================

class FakeStreamResponse:
    def __init__(self, lines, status_code=200, body=b""):
        self._lines = lines
        self.status_code = status_code
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aread(self):
        return self._body


class FakeHttpxClient:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def stream(self, method, url, headers=None, json=None):
        return self._response


def sse(obj):
    return "data: " + json.dumps(obj, ensure_ascii=False)


def stream_events(lines, status_code=200, body=b"", messages=None):
    resp = FakeStreamResponse(lines, status_code=status_code, body=body)
    client = DeepSeekClient(api_key="test-key", base_url="http://api.test", model="test-model")
    with patch("httpx.AsyncClient", lambda **kw: FakeHttpxClient(resp)):
        async def collect():
            return [e async for e in client.chat_with_tools_stream(
                messages or [{"role": "user", "content": "hi"}]
            )]
        return asyncio.run(collect())


class TestChatWithToolsStream:
    def test_content_streaming_and_done(self):
        events = stream_events([
            sse({"choices": [{"delta": {"content": "你好"}, "finish_reason": None}]}),
            sse({"choices": [{"delta": {"content": "世界"}, "finish_reason": None}]}),
            sse({"choices": [{"delta": {}, "finish_reason": "stop"}]}),
            "data: [DONE]",
        ])
        deltas = [e for e in events if e["type"] == STREAM_EVENT_CONTENT_DELTA]
        assert "".join(d["delta"] for d in deltas) == "你好世界"
        done = [e for e in events if e["type"] == STREAM_EVENT_DONE]
        assert len(done) == 1
        assert done[0]["content"] == "你好世界"
        assert done[0]["finish_reason"] == "stop"

    def test_reasoning_content_streamed(self):
        events = stream_events([
            sse({"choices": [{"delta": {"reasoning_content": "首先分析问题"}, "finish_reason": None}]}),
            sse({"choices": [{"delta": {"content": "答案"}, "finish_reason": "stop"}]}),
            "data: [DONE]",
        ])
        thinking = [e for e in events if e["type"] == STREAM_EVENT_THINKING_DELTA]
        assert "".join(t["content"] for t in thinking) == "首先分析问题"
        done = [e for e in events if e["type"] == STREAM_EVENT_DONE][0]
        assert done["reasoning_content"] == "首先分析问题"

    def test_think_tags_in_content_rerouted(self):
        """<think> tags embedded in content field become thinking deltas."""
        events = stream_events([
            sse({"choices": [{"delta": {"content": "<think>内部推理</think>外部回答"}, "finish_reason": "stop"}]}),
            "data: [DONE]",
        ])
        thinking = [e for e in events if e["type"] == STREAM_EVENT_THINKING_DELTA]
        content = [e for e in events if e["type"] == STREAM_EVENT_CONTENT_DELTA]
        assert "".join(t["content"] for t in thinking) == "内部推理"
        assert "".join(c["delta"] for c in content) == "外部回答"
        done = [e for e in events if e["type"] == STREAM_EVENT_DONE][0]
        assert done["content"] == "外部回答"
        assert done["reasoning_content"] == "内部推理"

    def test_tool_calls_accumulated_across_deltas(self):
        events = stream_events([
            sse({"choices": [{"delta": {"tool_calls": [
                {"index": 0, "id": "call_1", "function": {"name": "web_search", "arguments": '{"que'}}
            ]}, "finish_reason": None}]}),
            sse({"choices": [{"delta": {"tool_calls": [
                {"index": 0, "function": {"arguments": 'ry":"银灰"}'}}
            ]}, "finish_reason": None}]}),
            sse({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}),
            "data: [DONE]",
        ])
        tc_events = [e for e in events if e["type"] == STREAM_EVENT_TOOL_CALLS]
        assert len(tc_events) == 1
        tool_calls = tc_events[0]["tool_calls"]
        assert len(tool_calls) == 1
        assert isinstance(tool_calls[0], ToolCall)
        assert tool_calls[0].id == "call_1"
        assert tool_calls[0].name == "web_search"
        assert tool_calls[0].arguments == '{"query":"银灰"}'

    def test_multiple_parallel_tool_calls_ordered_by_index(self):
        events = stream_events([
            sse({"choices": [{"delta": {"tool_calls": [
                {"index": 0, "id": "c0", "function": {"name": "rag", "arguments": "{}"}},
                {"index": 1, "id": "c1", "function": {"name": "web", "arguments": "{}"}},
            ]}, "finish_reason": None}]}),
            "data: [DONE]",
        ])
        tool_calls = [e for e in events if e["type"] == STREAM_EVENT_TOOL_CALLS][0]["tool_calls"]
        assert [tc.id for tc in tool_calls] == ["c0", "c1"]

    def test_http_error_raises_with_message(self):
        resp = FakeStreamResponse([], status_code=401,
                                  body=b'{"error": {"message": "invalid api key"}}')
        client = DeepSeekClient(api_key="bad", base_url="http://api.test", model="m")

        async def collect():
            with patch("httpx.AsyncClient", lambda **kw: FakeHttpxClient(resp)):
                return [e async for e in client.chat_with_tools_stream([{"role": "user", "content": "hi"}])]

        with pytest.raises(Exception, match="401 Error: invalid api key"):
            asyncio.run(collect())

    def test_http_error_non_json_body(self):
        resp = FakeStreamResponse([], status_code=500, body=b"internal server error")
        client = DeepSeekClient(api_key="k", base_url="http://api.test", model="m")

        async def collect():
            with patch("httpx.AsyncClient", lambda **kw: FakeHttpxClient(resp)):
                return [e async for e in client.chat_with_tools_stream([{"role": "user", "content": "hi"}])]

        with pytest.raises(Exception, match="500 Error"):
            asyncio.run(collect())

    def test_malformed_sse_lines_skipped(self):
        events = stream_events([
            "data: {not valid json",
            "",
            ": comment line",
            sse({"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]}),
            "data: [DONE]",
        ])
        done = [e for e in events if e["type"] == STREAM_EVENT_DONE][0]
        assert done["content"] == "ok"

    def test_chunk_without_choices_skipped(self):
        events = stream_events([
            sse({"usage": {"total_tokens": 10}}),
            sse({"choices": []}),
            sse({"choices": [{"delta": {"content": "x"}, "finish_reason": "stop"}]}),
            "data: [DONE]",
        ])
        done = [e for e in events if e["type"] == STREAM_EVENT_DONE][0]
        assert done["content"] == "x"

    def test_large_content_split_into_stream_chunks(self):
        """Content longer than STREAM_CHUNK_SIZE must be split for smooth rendering."""
        long_text = "a" * 100
        events = stream_events([
            sse({"choices": [{"delta": {"content": long_text}, "finish_reason": "stop"}]}),
            "data: [DONE]",
        ])
        deltas = [e for e in events if e["type"] == STREAM_EVENT_CONTENT_DELTA]
        assert len(deltas) > 1
        assert all(len(d["delta"]) <= 8 for d in deltas)
        assert "".join(d["delta"] for d in deltas) == long_text


class TestDeepSeekClientInit:
    def test_missing_api_key_raises(self):
        with patch("backend.config.DEEPSEEK_API_KEY", ""):
            with pytest.raises(ValueError, match="API key"):
                DeepSeekClient(api_key=None)

    def test_explicit_params(self):
        client = DeepSeekClient(api_key="k", base_url="http://x", model="m")
        assert client.api_key == "k"
        assert client.base_url == "http://x"
        assert client.model == "m"
        assert client.disable_thinking is False
