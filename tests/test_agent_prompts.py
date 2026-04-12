"""
Tests for backend.agent.prompts - System prompt and message building.
"""
import pytest
from backend.agent.sessions import Session
from backend.agent.prompts import SYSTEM_PROMPT, build_messages


class TestSystemPrompt:
    def test_prompt_not_empty(self):
        assert len(SYSTEM_PROMPT) > 50

    def test_prompt_mentions_tools(self):
        assert "rag_search" in SYSTEM_PROMPT
        assert "graphrag" in SYSTEM_PROMPT
        assert "web_search" in SYSTEM_PROMPT

    def test_prompt_mentions_strategies(self):
        assert "并行" in SYSTEM_PROMPT
        assert "串行" in SYSTEM_PROMPT


class TestBuildMessages:
    def test_includes_system_prompt(self):
        session = Session(session_id="test")
        messages = build_messages(session)
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == SYSTEM_PROMPT

    def test_includes_session_messages(self):
        session = Session(session_id="test")
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi")
        messages = build_messages(session)
        assert len(messages) == 3  # system + user + assistant
        assert messages[1]["content"] == "Hello"
        assert messages[2]["content"] == "Hi"

    def test_respects_max_turns(self):
        session = Session(session_id="test")
        for i in range(30):
            session.add_message("user", f"msg {i}")
        messages = build_messages(session)
        # system + 20 most recent messages
        assert len(messages) == 21
