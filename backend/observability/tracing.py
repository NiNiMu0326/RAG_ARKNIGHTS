"""
LangFuse tracing for Agent observability.
Traces LLM calls, tool executions, and overall agent sessions.
"""

import asyncio
import base64
import json
import logging
import time
from typing import Dict

logger = logging.getLogger(__name__)

# asyncio.to_thread 在 Python 3.9 才加入；服务器运行的是 3.8.10，此处提供兼容回退。
if not hasattr(asyncio, "to_thread"):
    async def _to_thread(func, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    asyncio.to_thread = _to_thread

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


# ── LangFuse Public API client ──────────────────────────────────────────────

def _langfuse_auth_header() -> str:
    """Build the Basic Auth header for LangFuse Public API."""
    from backend import config
    credentials = f"{config.LANGFUSE_PUBLIC_KEY}:{config.LANGFUSE_SECRET_KEY}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def _langfuse_api_url(path: str) -> str:
    """Build a full LangFuse Public API URL."""
    from backend import config
    host = config.LANGFUSE_HOST.rstrip("/")
    return f"{host}/api/public{path}"


async def fetch_langfuse_traces(page: int = 1, limit: int = 20,
                                 name: str = None, user_id: str = None) -> dict:
    """Fetch a paginated list of traces from LangFuse.

    Uses the LangFuse Public API (GET /api/public/traces).
    Returns {"traces": [...], "total": int, "page": int, "limit": int} or an error dict.
    """
    from backend import config
    if not config.LANGFUSE_ENABLED:
        return {"error": "LangFuse 未配置", "traces": [], "total": 0}

    url = _langfuse_api_url("/traces")
    params = {"page": page, "limit": limit, "orderBy": "timestamp.desc"}
    if name:
        params["name"] = name
    if user_id:
        params["user_id"] = user_id

    headers = {"Authorization": _langfuse_auth_header()}

    try:
        import requests as _requests
        resp = await asyncio.to_thread(
            _requests.get, url, params=params, headers=headers, timeout=15
        )
        if resp.status_code == 401:
            return {"error": "LangFuse 认证失败，请检查 API Key", "traces": [], "total": 0}
        resp.raise_for_status()
        data = resp.json()
        traces = data.get("data", [])
        meta = data.get("meta", {})
        return {
            "traces": [
                {
                    "id": t.get("id"),
                    "name": t.get("name"),
                    "userId": t.get("userId"),
                    "sessionId": t.get("sessionId"),
                    "timestamp": t.get("timestamp"),
                    "input": str(t.get("input", ""))[:200] if t.get("input") else "",
                    "output": str(t.get("output", ""))[:200] if t.get("output") else "",
                    "metadata": t.get("metadata", {}),
                    "latency": t.get("latency"),
                    "totalCost": t.get("totalCost"),
                    "environment": t.get("environment"),
                }
                for t in traces
            ],
            "total": meta.get("totalItems", len(traces)),
            "page": meta.get("page", page),
            "limit": limit,
        }
    except Exception as e:
        logger.warning(f"[LANGFUSE] Failed to fetch traces: {e}")
        return {"error": f"获取 LangFuse trace 列表失败: {e}", "traces": [], "total": 0}


async def fetch_langfuse_trace_detail(trace_id: str) -> dict:
    """Fetch a single trace with full detail from LangFuse.

    Uses GET /api/public/traces/{id}.
    """
    from backend import config
    if not config.LANGFUSE_ENABLED:
        return {"error": "LangFuse 未配置"}

    url = _langfuse_api_url(f"/traces/{trace_id}")
    headers = {"Authorization": _langfuse_auth_header()}

    try:
        import requests as _requests
        resp = await asyncio.to_thread(
            _requests.get, url, headers=headers, timeout=15
        )
        if resp.status_code == 404:
            return {"error": "Trace 不存在"}
        resp.raise_for_status()
        data = resp.json()

        # Parse observations (spans/generations)
        observations = data.get("observations", [])
        spans = []
        generations = []
        for obs in observations:
            if obs.get("type") == "SPAN":
                spans.append({
                    "id": obs.get("id"),
                    "name": obs.get("name"),
                    "startTime": obs.get("startTime"),
                    "endTime": obs.get("endTime"),
                    "latency": obs.get("latency"),
                    "input": str(obs.get("input", ""))[:300] if obs.get("input") else "",
                    "output": str(obs.get("output", ""))[:300] if obs.get("output") else "",
                    "metadata": obs.get("metadata", {}),
                    "level": obs.get("level"),
                })
            elif obs.get("type") == "GENERATION":
                generations.append({
                    "id": obs.get("id"),
                    "name": obs.get("name"),
                    "model": obs.get("model"),
                    "startTime": obs.get("startTime"),
                    "endTime": obs.get("endTime"),
                    "latency": obs.get("latency"),
                    "input": str(obs.get("input", ""))[:300] if obs.get("input") else "",
                    "output": str(obs.get("output", ""))[:300] if obs.get("output") else "",
                    "usage": obs.get("usage", {}),
                    "metadata": obs.get("metadata", {}),
                })

        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "userId": data.get("userId"),
            "sessionId": data.get("sessionId"),
            "timestamp": data.get("timestamp"),
            "input": str(data.get("input", ""))[:500] if data.get("input") else "",
            "output": str(data.get("output", ""))[:500] if data.get("output") else "",
            "metadata": data.get("metadata", {}),
            "latency": data.get("latency"),
            "totalCost": data.get("totalCost"),
            "environment": data.get("environment"),
            "spans": spans,
            "generations": generations,
        }
    except Exception as e:
        logger.warning(f"[LANGFUSE] Failed to fetch trace detail: {e}")
        return {"error": f"获取 LangFuse trace 详情失败: {e}"}


async def save_trace_to_db(
    session_id: str,
    user_message: str,
    model_id: str,
    total_rounds: int,
    total_time_ms: float,
    total_llm_calls: int,
    total_tool_calls: int,
    total_tokens: int,
    answer_length: int,
    status: str = "success",
    error: str = "",
):
    """Save a completed agent trace to the local SQLite database."""
    try:
        from backend.db import get_db
        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO traces (session_id, user_message, model_id, total_rounds,
                   total_time_ms, total_llm_calls, total_tool_calls, total_tokens,
                   answer_length, status, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, user_message[:500], model_id, total_rounds, total_time_ms,
                 total_llm_calls, total_tool_calls, total_tokens, answer_length, status, error)
            )
            await db.commit()
        finally:
            await db.close()
        logger.info(f"[TRACE] Saved trace for session={session_id} status={status}")
    except Exception as e:
        logger.warning(f"[TRACE] Failed to save trace to DB: {e}")
