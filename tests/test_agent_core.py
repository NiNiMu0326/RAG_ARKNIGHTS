"""
Tests for backend.agent.core - SSE formatters and loop detection.
"""
import json
import pytest
from backend.agent.core import (
    format_tool_calls_start,
    format_tool_call_result,
    format_answer_delta,
    format_answer_done,
    format_error,
    detect_loop,
)
from backend.api.deepseek import ToolCall


class TestSSEFormatters:
    def test_format_tool_calls_start(self):
        tool_calls = [
            ToolCall(id="tc1", name="arknights_rag_search", arguments='{"query": "银灰"}'),
        ]
        result = format_tool_calls_start(tool_calls, round_num=1)
        assert result.startswith("data: ")
        data = json.loads(result[6:].strip())
        assert data["type"] == "tool_calls_start"
        assert data["round"] == 1
        assert len(data["tool_calls"]) == 1
        assert data["tool_calls"][0]["name"] == "arknights_rag_search"
        assert data["tool_calls"][0]["arguments"]["query"] == "银灰"

    def test_format_tool_call_result_list(self):
        result = format_tool_call_result("tc1", [{"content": "test"}], time_ms=100)
        data = json.loads(result[6:].strip())
        assert data["type"] == "tool_call_result"
        assert data["tool_call_id"] == "tc1"
        assert data["summary"] == "返回 1 条结果"
        assert data["time_ms"] == 100

    def test_format_tool_call_result_error(self):
        result = format_tool_call_result("tc2", {"error": "查询失败"}, time_ms=50)
        data = json.loads(result[6:].strip())
        assert "错误" in data["summary"]

    def test_format_tool_call_result_graphrag_path(self):
        result = format_tool_call_result("tc3", {"mode": "path", "path": ["银灰", "崖心"]}, time_ms=200)
        data = json.loads(result[6:].strip())
        assert "银灰 → 崖心" in data["summary"]

    def test_format_tool_call_result_graphrag_neighbors(self):
        result = format_tool_call_result("tc4", {"mode": "neighbors", "neighbors": ["A", "B", "C"]}, time_ms=150)
        data = json.loads(result[6:].strip())
        assert "3 个关联实体" in data["summary"]

    def test_format_answer_delta(self):
        result = format_answer_delta("你好")
        data = json.loads(result[6:].strip())
        assert data["type"] == "answer_delta"
        assert data["delta"] == "你好"

    def test_format_answer_done(self):
        metrics = {"total_time_ms": 3000, "num_tool_rounds": 2}
        result = format_answer_done("完整回答", metrics)
        data = json.loads(result[6:].strip())
        assert data["type"] == "answer_done"
        assert data["answer"] == "完整回答"
        assert data["metrics"]["total_time_ms"] == 3000

    def test_format_error(self):
        result = format_error("出错了")
        data = json.loads(result[6:].strip())
        assert data["type"] == "error"
        assert data["message"] == "出错了"


class TestLoopDetection:
    def test_no_loop(self):
        messages = [
            {"role": "assistant", "tool_calls": [{"function": {"name": "rag_search", "arguments": "q1"}}]},
            {"role": "tool", "content": "result"},
            {"role": "assistant", "tool_calls": [{"function": {"name": "web_search", "arguments": "q2"}}]},
        ]
        assert detect_loop(messages, window=4) is False

    def test_detect_loop(self):
        same_call = {"function": {"name": "rag_search", "arguments": '{"query": "银灰"}'}}
        messages = [
            {"role": "assistant", "tool_calls": [same_call]},
            {"role": "tool", "content": "result"},
            {"role": "assistant", "tool_calls": [same_call]},
            {"role": "tool", "content": "result"},
            {"role": "assistant", "tool_calls": [same_call]},
            {"role": "tool", "content": "result"},
            {"role": "assistant", "tool_calls": [same_call]},
        ]
        assert detect_loop(messages, window=4) is True

    def test_insufficient_messages_no_loop(self):
        messages = [
            {"role": "assistant", "tool_calls": [{"function": {"name": "rag_search", "arguments": "q1"}}]},
        ]
        assert detect_loop(messages, window=4) is False

    def test_mixed_calls_no_loop(self):
        messages = [
            {"role": "assistant", "tool_calls": [{"function": {"name": "rag_search", "arguments": "q1"}}]},
            {"role": "tool", "content": "result"},
            {"role": "assistant", "tool_calls": [{"function": {"name": "rag_search", "arguments": "q2"}}]},
            {"role": "tool", "content": "result"},
            {"role": "assistant", "tool_calls": [{"function": {"name": "web_search", "arguments": "q3"}}]},
        ]
        assert detect_loop(messages, window=4) is False
