"""
Tests for backend.observability.tracing: LangFuse client singleton,
AgentTrace counters/degradation, trace_agent_loop decorator.
Usage: cd test && python -m pytest test_tracing.py -v
"""
import asyncio
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.observability import tracing


@pytest.fixture(autouse=True)
def reset_singleton():
    tracing._langfuse_client = None
    tracing._current_trace.set(None)
    yield
    tracing._langfuse_client = None
    tracing._current_trace.set(None)


# ============================================================
# get_langfuse_client
# ============================================================

class TestGetLangfuseClient:
    def test_disabled_returns_none(self):
        with patch("backend.config.LANGFUSE_ENABLED", False):
            assert tracing.get_langfuse_client() is None

    def test_missing_package_returns_none(self):
        with patch("backend.config.LANGFUSE_ENABLED", True), \
             patch.dict("sys.modules", {"langfuse": None}):
            assert tracing.get_langfuse_client() is None

    def test_enabled_creates_and_caches_client(self):
        fake_langfuse_cls = MagicMock()
        fake_module = MagicMock(Langfuse=fake_langfuse_cls)
        with patch("backend.config.LANGFUSE_ENABLED", True), \
             patch("backend.config.LANGFUSE_PUBLIC_KEY", "pk"), \
             patch("backend.config.LANGFUSE_SECRET_KEY", "sk"), \
             patch("backend.config.LANGFUSE_HOST", "http://lf.local"), \
             patch.dict("sys.modules", {"langfuse": fake_module}):
            first = tracing.get_langfuse_client()
            assert first is fake_langfuse_cls.return_value
            second = tracing.get_langfuse_client()
            assert second is first
            fake_langfuse_cls.assert_called_once_with(
                public_key="pk", secret_key="sk", host="http://lf.local"
            )

    def test_init_exception_returns_none(self):
        fake_module = MagicMock()
        fake_module.Langfuse.side_effect = RuntimeError("bad config")
        with patch("backend.config.LANGFUSE_ENABLED", True), \
             patch.dict("sys.modules", {"langfuse": fake_module}):
            assert tracing.get_langfuse_client() is None


# ============================================================
# AgentTrace without client (degraded mode)
# ============================================================

class TestAgentTraceDegraded:
    def test_counters_work_without_client(self):
        with patch.object(tracing, "get_langfuse_client", return_value=None):
            t = tracing.AgentTrace("s1", "user msg", "model-x")
            assert t.trace is None
            t.add_llm_generation(1, 5, input_tokens=10, output_tokens=5, latency_ms=100)
            t.add_llm_generation(2, 8, input_tokens=20, output_tokens=10)
            t.add_tool_span("web_search", 1, args={"q": "x"}, result_summary="ok")
            assert t.total_llm_calls == 2
            assert t.total_tokens == 45
            assert t.total_tool_calls == 1
            # end() must not raise without a trace
            t.end(total_rounds=2, total_time_ms=500, answer_length=42)

    def test_trace_creation_failure_degrades(self):
        mock_client = MagicMock()
        mock_client.trace.side_effect = RuntimeError("network")
        with patch.object(tracing, "get_langfuse_client", return_value=mock_client):
            t = tracing.AgentTrace("s1", "msg", "m")
            assert t.trace is None
            t.add_llm_generation(1, 1)
            t.end()  # no raise


# ============================================================
# AgentTrace with mocked client
# ============================================================

class TestAgentTraceWithClient:
    def _make_trace(self):
        mock_client = MagicMock()
        mock_trace = MagicMock()
        mock_client.trace.return_value = mock_trace
        with patch.object(tracing, "get_langfuse_client", return_value=mock_client):
            t = tracing.AgentTrace("s1", "msg", "model-x")
        return t, mock_client, mock_trace

    def test_trace_created_with_metadata(self):
        t, mock_client, _ = self._make_trace()
        mock_client.trace.assert_called_once()
        kwargs = mock_client.trace.call_args.kwargs
        assert kwargs["id"] == "agent-s1"
        assert kwargs["metadata"]["session_id"] == "s1"

    def test_generation_recorded(self):
        t, _, mock_trace = self._make_trace()
        t.add_llm_generation(2, 7, input_tokens=100, output_tokens=50,
                             latency_ms=200, model="m", tool_calls_count=1, error="oops")
        mock_trace.generation.assert_called_once()
        kwargs = mock_trace.generation.call_args.kwargs
        assert kwargs["name"] == "llm-round-2"
        assert kwargs["usage"]["total"] == 150
        assert kwargs["metadata"]["error"] == "oops"

    def test_tool_span_recorded_and_truncated(self):
        t, _, mock_trace = self._make_trace()
        long_args = {"q": "x" * 1000}
        t.add_tool_span("web_search", 1, args=long_args,
                        result_summary="y" * 500, latency_ms=12.5, error="e")
        mock_trace.span.assert_called_once()
        meta = mock_trace.span.call_args.kwargs["metadata"]
        assert len(meta["arguments"]) <= 500
        assert len(meta["result_summary"]) <= 200
        assert meta["latency_ms"] == round(12.5)  # banker's rounding → 12

    def test_end_updates_and_flushes(self):
        t, mock_client, mock_trace = self._make_trace()
        t.add_llm_generation(1, 3, input_tokens=5, output_tokens=5)
        with patch.object(tracing, "get_langfuse_client", return_value=mock_client):
            t.end(total_rounds=1, total_time_ms=300.7, answer_length=99, error="boom")
        kwargs = mock_trace.update.call_args.kwargs
        assert kwargs["metadata"]["status"] == "error"
        assert kwargs["metadata"]["total_tokens"] == 10
        mock_client.flush.assert_called_once()

    def test_span_failure_does_not_raise(self):
        t, _, mock_trace = self._make_trace()
        mock_trace.span.side_effect = RuntimeError("api down")
        t.add_tool_span("tool", 1)  # must not raise
        assert t.total_tool_calls == 1


# ============================================================
# trace_agent_loop decorator & get_current_trace
# ============================================================

class TestTraceDecorator:
    def test_events_pass_through(self):
        async def fake_loop(session_id, user_message, model_id=None):
            yield "event1"
            yield "event2"

        async def collect():
            wrapped = tracing.trace_agent_loop(fake_loop)
            return [e async for e in wrapped("sid", "hello", model_id="m")]

        with patch.object(tracing, "get_langfuse_client", return_value=None):
            assert asyncio.run(collect()) == ["event1", "event2"]

    def test_current_trace_set_during_execution(self):
        seen = []

        async def fake_loop(session_id, user_message, model_id=None):
            seen.append(tracing.get_current_trace())
            yield "e"

        async def collect():
            wrapped = tracing.trace_agent_loop(fake_loop)
            return [e async for e in wrapped("sid", "hello")]

        with patch.object(tracing, "get_langfuse_client", return_value=None):
            asyncio.run(collect())
        assert len(seen) == 1
        assert isinstance(seen[0], tracing.AgentTrace)
        assert seen[0].session_id == "sid"
        # Context cleared after loop finishes
        assert tracing.get_current_trace() is None

    def test_context_cleared_on_exception(self):
        async def failing_loop(session_id, user_message, model_id=None):
            yield "partial"
            raise RuntimeError("loop crash")

        async def collect():
            wrapped = tracing.trace_agent_loop(failing_loop)
            events = []
            with pytest.raises(RuntimeError):
                async for e in wrapped("sid", "hello"):
                    events.append(e)
            return events

        with patch.object(tracing, "get_langfuse_client", return_value=None):
            assert asyncio.run(collect()) == ["partial"]
        assert tracing.get_current_trace() is None

    def test_get_current_trace_default_none(self):
        assert tracing.get_current_trace() is None
