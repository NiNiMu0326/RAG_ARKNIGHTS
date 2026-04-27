"""
Tests for backend.api.deepseek: think-tag state machine parsing.
Tests the chunk-based streaming parser used in chat_with_tools_stream.
Usage: cd test && python -m pytest test_deepseek_think.py -v
"""
import sys
import json
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.api.deepseek import DeepSeekClient, ToolCall, ChatResponse
from backend.api.deepseek import STREAM_EVENT_THINKING_DELTA, STREAM_EVENT_CONTENT_DELTA
from backend.api.deepseek import STREAM_EVENT_TOOL_CALLS, STREAM_EVENT_DONE


# ============================================================
# Helpers: simulate SSE chunks as the stream generator would yield them
# ============================================================

def chunks_to_events(chunks):
    """Convert raw SSE data chunks to list of event dicts.
    Each chunk is a dict like {"choices": [{"delta": {"content": "..."}}]}
    """
    # We test by feeding chunks through the think buffer logic manually
    pass


class TestToolCall:
    def test_create(self):
        tc = ToolCall(id="c1", name="search", arguments='{"q":"test"}')
        assert tc.id == "c1"
        assert tc.name == "search"
        assert tc.arguments == '{"q":"test"}'

    def test_to_dict(self):
        tc = ToolCall(id="c1", name="search", arguments='{"q":"x"}')
        d = tc.to_dict()
        assert d["id"] == "c1"
        assert d["type"] == "function"
        assert d["function"]["name"] == "search"


class TestChatResponse:
    def test_content_only(self):
        r = ChatResponse(content="hello")
        assert r.content == "hello"
        assert r.has_tool_calls is False
        assert r.tool_calls is None

    def test_with_tool_calls(self):
        tc = ToolCall(id="c1", name="search", arguments="{}")
        r = ChatResponse(content="using tool", tool_calls=[tc])
        assert r.has_tool_calls is True

    def test_empty(self):
        r = ChatResponse()
        assert r.content == ""
        assert r.has_tool_calls is False


# ============================================================
# Think tag state machine - component tests
# ============================================================

# These tests validate the core logic of the think-buffer state machine
# by running simplified versions of its branches.

def simulate_think_buffer(content_chunks):
    """Simulate the think buffer state machine with a sequence of content chunks.
    Returns (thinking_parts, content_parts, in_think_tag_at_end).
    """
    in_think_tag = False
    think_buffer = ""
    thinking_parts = []
    content_parts = []

    for content_delta in content_chunks:
        think_buffer += content_delta
        while think_buffer:
            if in_think_tag:
                close_idx = think_buffer.find("</think")
                if close_idx != -1:
                    thinking_chunk = think_buffer[:close_idx]
                    if thinking_chunk:
                        thinking_parts.append(thinking_chunk)
                    rest = think_buffer[close_idx:]
                    close_end = rest.find(">")
                    if close_end != -1:
                        think_buffer = rest[close_end + 1:]
                        in_think_tag = False
                    else:
                        think_buffer = rest
                        break
                else:
                    # Check for partial "</think" at end
                    partial_len = 0
                    for i in range(1, min(len(think_buffer), 8) + 1):
                        if "</think"[:i] == think_buffer[-i:]:
                            partial_len = i
                    if partial_len > 0:
                        emit_part = think_buffer[:-partial_len]
                        if emit_part:
                            thinking_parts.append(emit_part)
                        think_buffer = think_buffer[-partial_len:]
                        break
                    else:
                        thinking_parts.append(think_buffer)
                        think_buffer = ""
                        break
            else:
                open_idx = think_buffer.find("<think")
                if open_idx != -1:
                    before = think_buffer[:open_idx]
                    if before:
                        content_parts.append(before)
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
                    # Check for partial "<think" at end
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
                        think_buffer = think_buffer[partial_start:]
                        break
                    else:
                        content_parts.append(think_buffer)
                        think_buffer = ""
                        break

    return thinking_parts, content_parts, in_think_tag


class TestThinkBufferStateMachine:
    def test_simple_content_no_think(self):
        thinking, content, in_tag = simulate_think_buffer(["hello world"])
        assert len(thinking) == 0
        assert "".join(content) == "hello world"
        assert in_tag is False

    def test_simple_think_tag(self):
        thinking, content, in_tag = simulate_think_buffer([
            "<think>reasoning text</think>final answer"
        ])
        assert "".join(thinking) == "reasoning text"
        assert "final answer" in "".join(content)
        assert in_tag is False

    def test_think_tag_split_across_chunks(self):
        # Think tag split across multiple small chunks
        chunks = ["<thi", "nk>", "I think this is correct", "</think>", "Here is the answer"]
        thinking, content, in_tag = simulate_think_buffer(chunks)
        assert "I think this is correct" in "".join(thinking)
        assert "Here is the answer" in "".join(content)
        assert in_tag is False

    def test_closing_tag_split_across_chunks(self):
        chunks = ["<think>reasoning", "</thi", "nk>", "answer here"]
        thinking, content, in_tag = simulate_think_buffer(chunks)
        assert "reasoning" in "".join(thinking)
        assert "answer here" in "".join(content)
        assert in_tag is False

    def test_self_closing_think_tag(self):
        thinking, content, in_tag = simulate_think_buffer([
            "before <think/> after"
        ])
        assert "before  after" in "".join(content)

    def test_think_with_attributes(self):
        thinking, content, in_tag = simulate_think_buffer([
            '<think process="reasoning">internal thoughts</think>answer'
        ])
        assert "internal thoughts" in "".join(thinking)
        assert "answer" in "".join(content)

    def test_no_think_tags_at_all(self):
        thinking, content, in_tag = simulate_think_buffer([
            "The answer is 42. No thinking needed."
        ])
        assert len(thinking) == 0
        assert "42" in "".join(content)

    def test_unclosed_think_tag(self):
        # If think tag opens but never closes (stream ends), it's treated as thinking
        thinking, content, in_tag = simulate_think_buffer([
            "<think>unfinished reasoning..."
        ])
        # At end of stream, unclosed think treated as thinking
        assert in_tag is True
        assert "unfinished reasoning..." in "".join(thinking)

    def test_empty_think_tag(self):
        thinking, content, in_tag = simulate_think_buffer([
            "<think></think>content"
        ])
        assert "content" in "".join(content)

    def test_multiple_think_blocks(self):
        thinking, content, in_tag = simulate_think_buffer([
            "<think>step 1</think>middle<think>step 2</think>final"
        ])
        assert "step 1" in "".join(thinking)
        assert "step 2" in "".join(thinking)
        assert "middle" in "".join(content)
        assert "final" in "".join(content)

    def test_chinese_content_in_think(self):
        thinking, content, in_tag = simulate_think_buffer([
            "<think>我在思考这个问题...</think>这是答案"
        ])
        assert "我在思考这个问题" in "".join(thinking)
        assert "这是答案" in "".join(content)
