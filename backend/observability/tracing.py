"""
LangFuse tracing for Agent observability.
Traces LLM calls, tool executions, and overall agent sessions.
"""

import time
import json
import logging
import functools
from typing import Optional, Dict, Any, Callable
from contextvars import ContextVar

logger = logging.getLogger(__name__)

# Context variable to track current trace across async boundaries
_current_trace: ContextVar[Optional[Dict]] = ContextVar("langfuse_trace", default=None)

_langfuse_client = None


def get_langfuse_client():
    """Get or create the LangFuse client singleton."""
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client

    from backend import config
    if not config.LANGFUSE_ENABLED:
        logger.info("LangFuse not configured, tracing disabled")
        return None

    try:
        from langfuse import Langfuse
        _langfuse_client = Langfuse(
            public_key=config.LANGFUSE_PUBLIC_KEY,
            secret_key=config.LANGFUSE_SECRET_KEY,
            host=config.LANGFUSE_HOST,
        )
        logger.info(f"LangFuse client initialized (host={config.LANGFUSE_HOST})")
        return _langfuse_client
    except ImportError:
        logger.warning("langfuse package not installed, tracing disabled")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize LangFuse: {e}")
        return None


class AgentTrace:
    """Manages a single agent conversation trace."""

    def __init__(self, session_id: str, user_message: str, model_id: str):
        self.session_id = session_id
        self.user_message = user_message
        self.model_id = model_id
        self.trace = None
        self.start_time = time.time()
        self.total_llm_calls = 0
        self.total_tool_calls = 0
        self.total_tokens = 0

        client = get_langfuse_client()
        if client:
            try:
                self.trace = client.trace(
                    id=f"agent-{session_id}",
                    name="agent-conversation",
                    metadata={
                        "session_id": session_id,
                        "model": model_id,
                    },
                    input=user_message[:500],
                )
            except Exception as e:
                logger.warning(f"Failed to create LangFuse trace: {e}")
                self.trace = None

    def add_llm_generation(self, round_num: int, messages_count: int,
                           input_tokens: int = 0, output_tokens: int = 0,
                           latency_ms: float = 0, model: str = "",
                           tool_calls_count: int = 0, error: str = ""):
        """Record an LLM call as a generation span."""
        self.total_llm_calls += 1
        self.total_tokens += input_tokens + output_tokens

        if not self.trace:
            return

        try:
            metadata = {
                "round": round_num,
                "messages_count": messages_count,
                "tool_calls_count": tool_calls_count,
            }
            if error:
                metadata["error"] = error

            self.trace.generation(
                name=f"llm-round-{round_num}",
                model=model or self.model_id,
                start_time=self.start_time,
                end_time=time.time(),
                usage={
                    "input": input_tokens,
                    "output": output_tokens,
                    "total": input_tokens + output_tokens,
                },
                metadata=metadata,
            )
        except Exception as e:
            logger.warning(f"Failed to record LangFuse generation: {e}")

    def add_tool_span(self, tool_name: str, round_num: int,
                      args: Dict = None, result_summary: str = "",
                      latency_ms: float = 0, error: str = ""):
        """Record a tool execution as a span."""
        self.total_tool_calls += 1

        if not self.trace:
            return

        try:
            metadata = {
                "round": round_num,
                "tool_name": tool_name,
                "latency_ms": round(latency_ms),
            }
            if args:
                # Truncate args for storage
                args_str = json.dumps(args, ensure_ascii=False)[:500]
                metadata["arguments"] = args_str
            if result_summary:
                metadata["result_summary"] = result_summary[:200]
            if error:
                metadata["error"] = error

            self.trace.span(
                name=f"tool-{tool_name}",
                metadata=metadata,
            )
        except Exception as e:
            logger.warning(f"Failed to record LangFuse span: {e}")

    def end(self, total_rounds: int = 0, total_time_ms: float = 0,
            answer_length: int = 0, error: str = ""):
        """End the trace with final metadata."""
        if not self.trace:
            return

        try:
            self.trace.update(
                output=f"rounds={total_rounds}, llm_calls={self.total_llm_calls}, tool_calls={self.total_tool_calls}, tokens={self.total_tokens}, answer_len={answer_length}"[:500],
                metadata={
                    "total_rounds": total_rounds,
                    "total_time_ms": round(total_time_ms),
                    "total_llm_calls": self.total_llm_calls,
                    "total_tool_calls": self.total_tool_calls,
                    "total_tokens": self.total_tokens,
                    "answer_length": answer_length,
                    "status": "error" if error else "success",
                    "error": error[:200] if error else "",
                },
            )
        except Exception as e:
            logger.warning(f"Failed to update LangFuse trace: {e}")

        # Flush to ensure data is sent
        client = get_langfuse_client()
        if client:
            try:
                client.flush()
            except Exception:
                pass


def trace_agent_loop(func: Callable):
    """Decorator for agent_loop that wraps the entire conversation with a trace."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        session_id = kwargs.get("session_id", args[0] if args else "unknown")
        user_message = kwargs.get("user_message", args[1] if len(args) > 1 else "")
        model_id = kwargs.get("model_id", "default")

        trace = AgentTrace(session_id, user_message, model_id)
        _current_trace.set(trace)

        try:
            async for event in func(*args, **kwargs):
                yield event
        finally:
            _current_trace.set(None)

    return wrapper


def get_current_trace() -> Optional[AgentTrace]:
    """Get the current trace from context."""
    return _current_trace.get()
