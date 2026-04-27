"""
Tests for backend.agent.sessions: Session and SessionManager.
Usage: cd test && python -m pytest test_sessions.py -v
"""
import sys
import time
import asyncio
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.agent.sessions import Session, SessionManager
from backend.api.deepseek import ToolCall


# ============================================================
# Session
# ============================================================

class TestSession:
    def test_create(self):
        s = Session(session_id="test-1")
        assert s.session_id == "test-1"
        assert s.messages == []

    def test_add_message(self):
        s = Session(session_id="test-1")
        s.add_message("user", "hello")
        assert len(s.messages) == 1
        assert s.messages[0]["role"] == "user"
        assert s.messages[0]["content"] == "hello"

    def test_add_message_with_extra(self):
        s = Session(session_id="test-1")
        s.add_message("assistant", "hi", extra_field="value")
        assert s.messages[0]["extra_field"] == "value"

    def test_add_assistant_tool_calls(self):
        s = Session(session_id="test-1")
        tc = ToolCall(id="call_1", name="test_tool", arguments='{"q": "x"}')
        s.add_assistant_tool_calls([tc], content="using tool", reasoning_content="think...")
        msg = s.messages[0]
        assert msg["role"] == "assistant"
        assert msg["content"] == "using tool"
        assert msg["reasoning_content"] == "think..."
        assert len(msg["tool_calls"]) == 1
        assert msg["tool_calls"][0]["id"] == "call_1"
        assert msg["tool_calls"][0]["function"]["name"] == "test_tool"

    def test_add_tool_result_dict(self):
        s = Session(session_id="test-1")
        s.add_tool_result("call_1", {"items": [1, 2, 3]})
        msg = s.messages[0]
        assert msg["role"] == "tool"
        assert msg["tool_call_id"] == "call_1"
        assert '"items"' in msg["content"]

    def test_add_tool_result_list(self):
        s = Session(session_id="test-1")
        s.add_tool_result("call_1", [1, 2, 3])
        assert "[1, 2, 3]" in s.messages[0]["content"]

    def test_add_tool_result_string(self):
        s = Session(session_id="test-1")
        s.add_tool_result("call_1", "done")
        assert s.messages[0]["content"] == "done"


class TestSessionGetContextMessages:
    def test_normal_messages(self):
        s = Session(session_id="test-1")
        s.add_message("user", "hello")
        s.add_message("assistant", "hi there")
        ctx = s.get_context_messages()
        assert len(ctx) == 2
        assert ctx[0]["role"] == "user"

    def test_strips_underscore_fields(self):
        s = Session(session_id="test-1")
        s.add_message("user", "hello", _internal="secret")
        ctx = s.get_context_messages()
        assert "_internal" not in ctx[0]

    def test_removes_orphaned_tool_calls(self):
        s = Session(session_id="test-1")
        tc = ToolCall(id="orphan_1", name="test", arguments="{}")
        s.add_assistant_tool_calls([tc], content="calling tool")
        ctx = s.get_context_messages()
        assert len(ctx) == 1
        assert "tool_calls" not in ctx[0]

    def test_removes_orphaned_tool_results(self):
        s = Session(session_id="test-1")
        s.add_tool_result("orphan_result", "result content")
        ctx = s.get_context_messages()
        assert len(ctx) == 0

    def test_keeps_valid_tool_pair(self):
        s = Session(session_id="test-1")
        tc = ToolCall(id="call_1", name="test", arguments="{}")
        s.add_assistant_tool_calls([tc], content="calling")
        s.add_tool_result("call_1", "result")
        ctx = s.get_context_messages()
        assert len(ctx) == 2
        assert "tool_calls" in ctx[0]
        assert ctx[1]["tool_call_id"] == "call_1"

    def test_max_turns_limits_output(self):
        s = Session(session_id="test-1")
        for i in range(30):
            s.add_message("user", f"msg{i}")
        ctx = s.get_context_messages(max_turns=20)
        assert len(ctx) == 20
        assert ctx[0]["content"] == "msg10"


# ============================================================
# SessionManager (sync wrappers around async methods)
# ============================================================

class TestSessionManager:
    def test_create_session(self):
        async def _test():
            sm = SessionManager(max_sessions=10)
            sid = await sm.create_session()
            assert isinstance(sid, str)
            assert len(sid) == 8
        asyncio.run(_test())

    def test_get_session(self):
        async def _test():
            sm = SessionManager(max_sessions=10)
            sid = await sm.create_session()
            s = await sm.get_session(sid)
            assert s is not None
            assert s.session_id == sid
        asyncio.run(_test())

    def test_get_nonexistent(self):
        async def _test():
            sm = SessionManager(max_sessions=10)
            s = await sm.get_session("nonexist")
            assert s is None
        asyncio.run(_test())

    def test_get_expired_session(self):
        async def _test():
            sm = SessionManager(max_sessions=10, ttl_seconds=-1)  # negative TTL: all sessions expired
            sid = await sm.create_session()
            s = await sm.get_session(sid)
            assert s is None
        asyncio.run(_test())

    def test_delete_session(self):
        async def _test():
            sm = SessionManager(max_sessions=10)
            sid = await sm.create_session()
            await sm.delete_session(sid)
            s = await sm.get_session(sid)
            assert s is None
        asyncio.run(_test())

    def test_lru_eviction_at_capacity(self):
        async def _test():
            sm = SessionManager(max_sessions=3)
            s1 = await sm.create_session()
            s2 = await sm.create_session()
            s3 = await sm.create_session()
            s4 = await sm.create_session()  # should evict s1
            assert await sm.get_session(s1) is None
            assert await sm.get_session(s4) is not None
        asyncio.run(_test())

    def test_active_count(self):
        async def _test():
            sm = SessionManager(max_sessions=10)
            assert await sm.get_active_count() == 0
            await sm.create_session()
            await sm.create_session()
            assert await sm.get_active_count() == 2
        asyncio.run(_test())

    def test_cleanup_expired(self):
        async def _test():
            sm = SessionManager(max_sessions=10, ttl_seconds=-1)
            sid = await sm.create_session()
            await sm.create_session()  # trigger cleanup
            s = await sm.get_session(sid)
            assert s is None
        asyncio.run(_test())
