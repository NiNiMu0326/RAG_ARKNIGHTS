"""
Tests for backend.agent.sessions - Session and SessionManager.
"""
import time
import pytest
from backend.agent.sessions import Session, SessionManager


class TestSession:
    def test_add_message(self):
        session = Session(session_id="test1")
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there")
        assert len(session.messages) == 2
        assert session.messages[0]["role"] == "user"
        assert session.messages[0]["content"] == "Hello"
        assert session.messages[1]["role"] == "assistant"

    def test_add_assistant_tool_calls(self):
        from backend.api.deepseek import ToolCall
        session = Session(session_id="test2")
        tool_calls = [
            ToolCall(id="tc1", name="arknights_rag_search", arguments='{"query": "银灰"}'),
            ToolCall(id="tc2", name="web_search", arguments='{"query": "最新活动"}'),
        ]
        session.add_assistant_tool_calls(tool_calls, content="")
        assert len(session.messages) == 1
        msg = session.messages[0]
        assert msg["role"] == "assistant"
        assert len(msg["tool_calls"]) == 2
        assert msg["tool_calls"][0]["function"]["name"] == "arknights_rag_search"
        assert msg["tool_calls"][1]["function"]["name"] == "web_search"

    def test_add_tool_result(self):
        session = Session(session_id="test3")
        session.add_tool_result("tc1", [{"content": "result1"}])
        session.add_tool_result("tc2", "string result")
        assert len(session.messages) == 2
        assert session.messages[0]["role"] == "tool"
        assert session.messages[0]["tool_call_id"] == "tc1"
        assert session.messages[1]["tool_call_id"] == "tc2"

    def test_get_context_messages(self):
        session = Session(session_id="test4")
        for i in range(25):
            session.add_message("user", f"msg {i}")
        context = session.get_context_messages(max_turns=10)
        assert len(context) == 10
        assert context[0]["content"] == "msg 15"

    def test_session_id(self):
        session = Session(session_id="abc123")
        assert session.session_id == "abc123"


class TestSessionManager:
    def test_create_session(self):
        manager = SessionManager(max_sessions=10, ttl_seconds=3600)
        sid = manager.create_session()
        assert sid is not None
        assert len(sid) == 8  # UUID[:8]

    def test_get_session(self):
        manager = SessionManager(max_sessions=10, ttl_seconds=3600)
        sid = manager.create_session()
        session = manager.get_session(sid)
        assert session is not None
        assert session.session_id == sid

    def test_get_nonexistent_session(self):
        manager = SessionManager(max_sessions=10, ttl_seconds=3600)
        assert manager.get_session("nonexistent") is None

    def test_delete_session(self):
        manager = SessionManager(max_sessions=10, ttl_seconds=3600)
        sid = manager.create_session()
        manager.delete_session(sid)
        assert manager.get_session(sid) is None

    def test_ttl_expiry(self):
        manager = SessionManager(max_sessions=10, ttl_seconds=0)  # immediate expiry
        sid = manager.create_session()
        time.sleep(0.01)
        assert manager.get_session(sid) is None

    def test_max_sessions_lru_eviction(self):
        manager = SessionManager(max_sessions=2, ttl_seconds=3600)
        sid1 = manager.create_session()
        sid2 = manager.create_session()
        sid3 = manager.create_session()
        # sid1 should be evicted
        assert manager.get_session(sid1) is None
        assert manager.get_session(sid2) is not None
        assert manager.get_session(sid3) is not None

    def test_get_active_count(self):
        manager = SessionManager(max_sessions=10, ttl_seconds=3600)
        manager.create_session()
        manager.create_session()
        assert manager.get_active_count() == 2
