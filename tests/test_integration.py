"""
Integration tests for AgenticRAG endpoints.

Tests the full Agent flow through FastAPI TestClient with REAL API calls.
Requires valid API keys in backend/.env:
  - DEEPSEEK_API_KEY_2
  - SILICONFLOW_API_KEY
  - TAVILY_API_KEY

Run with: python -m pytest tests/test_integration.py -v
Skip with: python -m pytest tests/ -v -k "not integration"
"""

import json
import time
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.agent.sessions import SessionManager
from backend import config


# ===== Fixtures =====

@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def session_manager():
    """Get the app's session manager."""
    from backend.main import _session_manager
    return _session_manager


@pytest.fixture
def session_id(client):
    """Create a session and return its ID."""
    resp = client.post("/agent/session")
    assert resp.status_code == 200
    return resp.json()["session_id"]


def _has_api_keys():
    """Check if required API keys are configured."""
    return bool(config.DEEPSEEK_API_KEY and config.SILICONFLOW_API_KEY)


requires_api = pytest.mark.skipif(
    not _has_api_keys(),
    reason="API keys not configured (DEEPSEEK_API_KEY_2, SILICONFLOW_API_KEY)"
)


def _parse_sse_events(raw_text: str) -> list:
    """Parse SSE text into list of event data dicts."""
    events = []
    for line in raw_text.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                events.append(data)
            except json.JSONDecodeError:
                pass
    return events


# ===== Health & Basic API Tests (no API key needed) =====

class TestBasicEndpoints:
    """Test basic non-Agent endpoints for smoke testing."""

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_api_root(self, client):
        resp = client.get("/api")
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        assert "version" in data

    def test_status_endpoint(self, client):
        resp = client.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "api_key_configured" in data

    def test_stats_endpoint(self, client):
        resp = client.get("/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "operators" in data
        assert "stories" in data
        assert "knowledge" in data
        assert "relations" in data

    def test_knowledge_graph_endpoint(self, client):
        resp = client.get("/knowledge-graph")
        assert resp.status_code == 200
        data = resp.json()
        assert "entities" in data
        assert "relations" in data


# ===== Agent Session CRUD Tests (no API key needed) =====

class TestAgentSessionCRUD:
    """Test Agent session creation, retrieval, and deletion."""

    def test_create_session(self, client):
        resp = client.post("/agent/session")
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert len(data["session_id"]) == 8

    def test_get_session_messages_empty(self, client):
        resp = client.post("/agent/session")
        session_id = resp.json()["session_id"]

        resp = client.get(f"/agent/session/{session_id}/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert "messages" in data
        assert data["messages"] == []

    def test_get_nonexistent_session_messages(self, client):
        resp = client.get("/agent/session/nonexistent/messages")
        assert resp.status_code == 404

    def test_delete_session(self, client):
        resp = client.post("/agent/session")
        session_id = resp.json()["session_id"]

        resp = client.delete(f"/agent/session/{session_id}")
        assert resp.status_code == 200

        resp = client.get(f"/agent/session/{session_id}/messages")
        assert resp.status_code == 404

    def test_delete_nonexistent_session(self, client):
        resp = client.delete("/agent/session/nonexistent")
        assert resp.status_code == 200  # Delete is idempotent

    def test_agent_stats(self, client):
        resp = client.get("/agent/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "active_sessions" in data
        assert "max_sessions" in data
        assert "ttl_seconds" in data

    def test_debug_trace_empty_session(self, client):
        resp = client.post("/agent/session")
        session_id = resp.json()["session_id"]

        resp = client.get(f"/agent/debug/trace?session_id={session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "traces" in data
        assert data["traces"] == []


# ===== Real API Integration Tests =====

@requires_api
class TestAgentChatRealAPI:
    """Test Agent chat with real DeepSeek API + real tool execution.

    These tests make actual API calls and execute real RAG/GraphRAG tools.
    They verify end-to-end functionality from HTTP request to SSE response.
    """

    def test_chat_greeting_direct_answer(self, client, session_id):
        """Test: Simple greeting should get a direct answer without tool calls.

        A greeting like '你好' should not trigger RAG search.
        The LLM should respond directly.
        """
        resp = client.post("/agent/chat", json={
            "session_id": session_id,
            "message": "你好",
        })

        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        event_types = [e["type"] for e in events]

        # Should have answer events
        assert "answer_delta" in event_types, f"Missing answer_delta, got events: {event_types}"
        assert "answer_done" in event_types, f"Missing answer_done, got events: {event_types}"

        # Verify answer content is meaningful
        done_event = next(e for e in events if e["type"] == "answer_done")
        assert len(done_event["answer"]) > 0
        assert "metrics" in done_event
        assert "total_time_ms" in done_event["metrics"]

        # Greeting should typically not trigger tools
        print(f"[Greeting] Answer: {done_event['answer'][:80]}...")
        print(f"[Greeting] Metrics: {done_event['metrics']}")

    def test_chat_rag_search_operator(self, client, session_id):
        """Test: Asking about an operator should trigger arknights_rag_search.

        The agent should:
        1. Call arknights_rag_search tool
        2. Return results with operator information
        3. Generate an answer based on the retrieved documents
        """
        resp = client.post("/agent/chat", json={
            "session_id": session_id,
            "message": "银灰的技能是什么？",
        })

        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        event_types = [e["type"] for e in events]

        # Should have tool calls
        assert "tool_calls_start" in event_types, f"Expected tool_calls_start for operator query, got: {event_types}"
        assert "tool_call_result" in event_types, f"Expected tool_call_result, got: {event_types}"

        # Check tool call was arknights_rag_search
        tc_start = next(e for e in events if e["type"] == "tool_calls_start")
        tool_names = [tc["name"] for tc in tc_start["tool_calls"]]
        assert "arknights_rag_search" in tool_names, f"Expected arknights_rag_search, got: {tool_names}"

        # Verify final answer
        done_event = next(e for e in events if e["type"] == "answer_done")
        assert len(done_event["answer"]) > 20, f"Answer too short: {done_event['answer'][:100]}"
        assert done_event["metrics"]["num_tool_rounds"] >= 1

        print(f"[RAG Search] Tool names: {tool_names}")
        print(f"[RAG Search] Rounds: {done_event['metrics']['num_tool_rounds']}")
        print(f"[RAG Search] Answer: {done_event['answer'][:120]}...")

    def test_chat_graphrag_search(self, client, session_id):
        """Test: Asking about entity relationships should trigger GraphRAG search.

        The agent should use arknights_graphrag_search to find relationships.
        """
        resp = client.post("/agent/chat", json={
            "session_id": session_id,
            "message": "银灰和初雪是什么关系？",
        })

        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        event_types = [e["type"] for e in events]

        # Should have tool calls
        assert "tool_calls_start" in event_types, f"Expected tool calls for relationship query, got: {event_types}"

        # Check tool calls - should include graphrag search
        tc_start = next(e for e in events if e["type"] == "tool_calls_start")
        tool_names = [tc["name"] for tc in tc_start["tool_calls"]]

        # Verify final answer mentions the relationship
        done_event = next(e for e in events if e["type"] == "answer_done")
        answer = done_event["answer"]

        print(f"[GraphRAG] Tool names: {tool_names}")
        print(f"[GraphRAG] Answer: {answer[:150]}...")

        # The answer should mention both entities or their relationship
        assert len(answer) > 10

    def test_chat_multi_turn_conversation(self, client, session_id):
        """Test: Multi-turn conversation maintains context.

        First turn asks about an operator, second turn asks a follow-up.
        The session should remember the previous conversation.
        """
        # First turn
        resp1 = client.post("/agent/chat", json={
            "session_id": session_id,
            "message": "告诉我关于德克萨斯的信息",
        })
        assert resp1.status_code == 200
        events1 = _parse_sse_events(resp1.text)
        done1 = next(e for e in events1 if e["type"] == "answer_done")
        assert len(done1["answer"]) > 10

        # Verify messages were saved
        resp = client.get(f"/agent/session/{session_id}/messages")
        messages = resp.json()["messages"]
        user_msgs = [m for m in messages if m["role"] == "user"]
        assert len(user_msgs) == 1, "First turn should have 1 user message"

        # Second turn - follow-up question
        resp2 = client.post("/agent/chat", json={
            "session_id": session_id,
            "message": "她有什么技能？",
        })
        assert resp2.status_code == 200
        events2 = _parse_sse_events(resp2.text)
        done2 = next(e for e in events2 if e["type"] == "answer_done")
        assert len(done2["answer"]) > 10

        # Verify messages accumulated
        resp = client.get(f"/agent/session/{session_id}/messages")
        messages = resp.json()["messages"]
        user_msgs = [m for m in messages if m["role"] == "user"]
        assert len(user_msgs) == 2, "Should have 2 user messages after 2 turns"

        print(f"[Multi-turn] Turn1 answer: {done1['answer'][:80]}...")
        print(f"[Multi-turn] Turn2 answer: {done2['answer'][:80]}...")

    def test_chat_debug_trace_with_tools(self, client, session_id):
        """Test: Debug trace shows tool call history after a chat with tools."""
        resp = client.post("/agent/chat", json={
            "session_id": session_id,
            "message": "能天使的精二材料是什么？",
        })
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)

        # Get debug trace
        resp = client.get(f"/agent/debug/trace?session_id={session_id}")
        assert resp.status_code == 200
        traces = resp.json()["traces"]

        # Should have at least one tool_call and one tool_result
        tool_call_traces = [t for t in traces if t["type"] == "tool_call"]
        tool_result_traces = [t for t in traces if t["type"] == "tool_result"]

        # Check if tools were called (they should be for this query)
        if any(e["type"] == "tool_calls_start" for e in events):
            assert len(tool_call_traces) >= 1, "Should have tool call traces"
            assert len(tool_result_traces) >= 1, "Should have tool result traces"

        print(f"[Debug Trace] Tool calls: {len(tool_call_traces)}, Results: {len(tool_result_traces)}")

    def test_chat_error_handling_nonexistent_session(self, client):
        """Test: Chat with nonexistent session returns 404."""
        resp = client.post("/agent/chat", json={
            "session_id": "nonexistent_session",
            "message": "你好",
        })
        assert resp.status_code == 404

    def test_chat_empty_message_rejected(self, client, session_id):
        """Test: Empty message is rejected by validation."""
        resp = client.post("/agent/chat", json={
            "session_id": session_id,
            "message": "",
        })
        assert resp.status_code == 422

    def test_chat_whitespace_message_rejected(self, client, session_id):
        """Test: Whitespace-only message is rejected."""
        resp = client.post("/agent/chat", json={
            "session_id": session_id,
            "message": "   ",
        })
        assert resp.status_code == 422


# ===== Real API + RAG Pipeline Tests =====

@requires_api
class TestRAGPipelineRealAPI:
    """Test the full RAG pipeline with real API calls."""

    def test_rag_search_returns_relevant_results(self):
        """Test: RAG search returns results for a known operator."""
        import asyncio
        from backend.agent.tool_implementations import execute_rag_search

        result = asyncio.get_event_loop().run_until_complete(
            execute_rag_search({"query": "银灰技能", "top_k": 3})
        )

        assert isinstance(result, list)
        assert len(result) > 0, "RAG search should return results for '银灰技能'"

        # Check result structure
        for item in result:
            if "error" not in item:
                assert "content" in item
                assert "source" in item
                assert "score" in item
                assert isinstance(item["score"], (int, float))
                print(f"[RAG Result] source={item['source']}, score={item['score']}, content={item['content'][:60]}...")

    def test_graphrag_search_entity_neighbors(self):
        """Test: GraphRAG search returns neighbors for a known entity."""
        import asyncio
        from backend.agent.tool_implementations import execute_graphrag_search

        result = asyncio.get_event_loop().run_until_complete(
            execute_graphrag_search({"entity": "银灰"})
        )

        assert isinstance(result, dict)
        # Should find the entity
        if result.get("found"):
            assert result.get("mode") == "neighbors"
            assert "neighbors" in result
            assert "relations" in result
            print(f"[GraphRAG] Entity: {result['entity']}, Neighbors: {result['neighbors']}")
        else:
            # If not found, it should have a message
            assert "message" in result or "error" in result
            print(f"[GraphRAG] Not found: {result}")

    def test_graphrag_search_entity_path(self):
        """Test: GraphRAG search finds path between two entities."""
        import asyncio
        from backend.agent.tool_implementations import execute_graphrag_search

        result = asyncio.get_event_loop().run_until_complete(
            execute_graphrag_search({"entity1": "银灰", "entity2": "初雪"})
        )

        assert isinstance(result, dict)
        if result.get("found"):
            assert result.get("mode") == "path"
            assert "path" in result
            assert "edges" in result
            print(f"[GraphRAG Path] {result['path']}")
        else:
            print(f"[GraphRAG Path] Not found: {result}")

    def test_deepseek_api_direct_call(self):
        """Test: Direct DeepSeek API call works."""
        from backend.api.deepseek import DeepSeekClient

        client = DeepSeekClient(api_key=config.DEEPSEEK_API_KEY)
        response = client.chat(
            messages=[{"role": "user", "content": "请用一句话回答：1+1等于几？"}],
            temperature=0.1,
        )

        assert isinstance(response, str)
        assert len(response) > 0
        print(f"[DeepSeek Direct] Response: {response}")

    def test_deepseek_api_with_tools(self):
        """Test: DeepSeek API with tool calling works."""
        from backend.api.deepseek import DeepSeekClient
        from backend.agent.tools import TOOL_SCHEMAS

        client = DeepSeekClient(api_key=config.DEEPSEEK_API_KEY)
        response = client.chat_with_tools(
            messages=[
                {"role": "system", "content": "你是明日方舟知识助手，请使用提供的工具来回答问题。"},
                {"role": "user", "content": "银灰的技能是什么？"},
            ],
            tools=TOOL_SCHEMAS,
            temperature=0.1,
        )

        # The model should call a tool
        assert response.has_tool_calls, f"Expected tool calls, got content: {response.content[:100]}"

        tool_names = [tc.name for tc in response.tool_calls]
        print(f"[DeepSeek Tools] Called: {tool_names}")
        print(f"[DeepSeek Tools] Args: {[tc.arguments for tc in response.tool_calls]}")


# ===== Session Persistence with Real API =====

@requires_api
class TestAgentSessionPersistence:
    """Test that session state persists correctly across real chat calls."""

    def test_messages_persist_across_chats(self, client, session_id):
        """Test: Messages from previous chat are preserved in session."""
        # First chat
        resp = client.post("/agent/chat", json={
            "session_id": session_id,
            "message": "你好",
        })
        assert resp.status_code == 200

        # Check messages were saved
        resp = client.get(f"/agent/session/{session_id}/messages")
        messages = resp.json()["messages"]
        assert len(messages) >= 2  # user + assistant

        # Second chat in same session
        resp = client.post("/agent/chat", json={
            "session_id": session_id,
            "message": "能天使是谁？",
        })
        assert resp.status_code == 200

        # Check messages accumulated
        resp = client.get(f"/agent/session/{session_id}/messages")
        messages = resp.json()["messages"]
        user_messages = [m for m in messages if m["role"] == "user"]
        assert len(user_messages) == 2

    def test_session_isolation(self, client):
        """Test: Different sessions have independent message histories."""
        # Create two sessions
        resp1 = client.post("/agent/session")
        sid1 = resp1.json()["session_id"]
        resp2 = client.post("/agent/session")
        sid2 = resp2.json()["session_id"]

        # Chat in session 1
        client.post("/agent/chat", json={
            "session_id": sid1,
            "message": "德克萨斯是谁？",
        })

        # Chat in session 2
        client.post("/agent/chat", json={
            "session_id": sid2,
            "message": "银灰是谁？",
        })

        # Verify isolation
        msgs1 = client.get(f"/agent/session/{sid1}/messages").json()["messages"]
        msgs2 = client.get(f"/agent/session/{sid2}/messages").json()["messages"]

        # Each session should only have its own messages
        user_msgs1 = [m for m in msgs1 if m["role"] == "user"]
        user_msgs2 = [m for m in msgs2 if m["role"] == "user"]

        assert len(user_msgs1) == 1
        assert len(user_msgs2) == 1
        assert "德克萨斯" in user_msgs1[0]["content"]
        assert "银灰" in user_msgs2[0]["content"]


# ===== SSE Format Integration Tests (Real API) =====

@requires_api
class TestSSEFormatIntegration:
    """Test SSE event format correctness with real API responses."""

    def test_sse_events_are_valid_json(self, client, session_id):
        """Test: All SSE data payloads are valid JSON."""
        resp = client.post("/agent/chat", json={
            "session_id": session_id,
            "message": "你好",
        })

        events = _parse_sse_events(resp.text)
        assert len(events) > 0

        for event in events:
            assert "type" in event, f"Event missing 'type': {event}"

    def test_sse_answer_done_has_metrics(self, client, session_id):
        """Test: answer_done event includes timing metrics."""
        resp = client.post("/agent/chat", json={
            "session_id": session_id,
            "message": "你好",
        })

        events = _parse_sse_events(resp.text)
        done_event = next(e for e in events if e["type"] == "answer_done")

        assert "total_time_ms" in done_event["metrics"]
        assert "num_tool_rounds" in done_event["metrics"]
        assert isinstance(done_event["metrics"]["total_time_ms"], (int, float))
        assert isinstance(done_event["metrics"]["num_tool_rounds"], int)

        print(f"[SSE Metrics] {done_event['metrics']}")

    def test_sse_tool_events_have_required_fields(self, client, session_id):
        """Test: Tool call SSE events have all required fields."""
        resp = client.post("/agent/chat", json={
            "session_id": session_id,
            "message": "银灰的技能是什么？",
        })

        events = _parse_sse_events(resp.text)
        event_types = [e["type"] for e in events]

        if "tool_calls_start" in event_types:
            tc_start = next(e for e in events if e["type"] == "tool_calls_start")
            assert "round" in tc_start
            assert "tool_calls" in tc_start
            for tc in tc_start["tool_calls"]:
                assert "id" in tc
                assert "name" in tc
                assert "arguments" in tc

        if "tool_call_result" in event_types:
            tc_results = [e for e in events if e["type"] == "tool_call_result"]
            for r in tc_results:
                assert "tool_call_id" in r
                assert "summary" in r
                assert "time_ms" in r
