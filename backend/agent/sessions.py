"""
Session management for AgenticRAG.
In-memory session store with TTL cleanup.
"""

import time
import uuid
import threading
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """A conversation session with full message history."""
    session_id: str
    created_at: float = field(default_factory=time.time)
    messages: List[Dict[str, Any]] = field(default_factory=list)

    def add_message(self, role: str, content: str = "", **kwargs):
        """Add a message to the session history."""
        msg = {"role": role, "content": content, **kwargs}
        self.messages.append(msg)

    def add_assistant_tool_calls(self, tool_calls: list, content: str = "", reasoning_content: str = ""):
        """Add an assistant message with tool_calls.
        
        Strips non-standard fields (like reasoning_content) from the stored message
        to prevent 400 errors when the message is sent back to the API.
        The reasoning_content is stored separately for display purposes.
        """
        tc_list = []
        for tc in tool_calls:
            tc_list.append({
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": tc.arguments,
                }
            })
        msg = {
            "role": "assistant",
            "content": content,
            "tool_calls": tc_list,
        }
        # Store reasoning_content separately (not sent back to API)
        if reasoning_content:
            msg["_reasoning_content"] = reasoning_content
        self.messages.append(msg)

    def add_tool_result(self, tool_call_id: str, result: Any):
        """Add a tool result message."""
        # Serialize result to string if not already
        if isinstance(result, str):
            content = result
        else:
            import json
            try:
                content = json.dumps(result, ensure_ascii=False)
            except (TypeError, ValueError):
                content = str(result)
        
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        })

    def get_context_messages(self, max_turns: int = 20) -> List[Dict]:
        """Get recent N messages as context for LLM.
        
        Strips any non-standard fields (prefixed with _) before sending to the API
        to prevent 400 errors from unsupported fields like reasoning_content.
        """
        messages = self.messages[-max_turns:]
        clean = []
        for msg in messages:
            clean_msg = {k: v for k, v in msg.items() if not k.startswith("_")}
            clean.append(clean_msg)
        return clean


class SessionManager:
    """In-memory session store with TTL-based cleanup."""

    def __init__(self, max_sessions: int = 1000, ttl_seconds: int = 3600):
        self._sessions: Dict[str, Session] = {}
        self._max_sessions = max_sessions
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._cleanup_interval = 300  # Clean up every 5 minutes
        self._last_cleanup = time.time()

    def create_session(self) -> str:
        """Create a new session and return its ID."""
        # Periodic cleanup
        self._maybe_cleanup()

        with self._lock:
            # Evict oldest if at capacity
            if len(self._sessions) >= self._max_sessions:
                oldest_id = min(self._sessions, key=lambda k: self._sessions[k].created_at)
                del self._sessions[oldest_id]
                logger.info(f"[SESSION] Evicted oldest session: {oldest_id}")

            session_id = str(uuid.uuid4())[:8]
            self._sessions[session_id] = Session(session_id=session_id)
            logger.info(f"[SESSION] Created: {session_id} (total: {len(self._sessions)})")
            return session_id

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID. Returns None if not found or expired."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                logger.warning(f"[SESSION] Not found: {session_id}")
                return None

            # Check TTL
            age = time.time() - session.created_at
            if age > self._ttl:
                del self._sessions[session_id]
                logger.warning(f"[SESSION] Expired: {session_id} (age={age:.0f}s, ttl={self._ttl}s)")
                return None

            logger.debug(f"[SESSION] Found: {session_id} (age={age:.0f}s, messages={len(session.messages)})")
            return session

    def delete_session(self, session_id: str):
        """Delete a session."""
        with self._lock:
            self._sessions.pop(session_id, None)
            logger.info(f"Deleted session: {session_id}")

    def _maybe_cleanup(self):
        """Periodically clean up expired sessions."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = now
        expired = []
        with self._lock:
            for sid, session in self._sessions.items():
                if now - session.created_at > self._ttl:
                    expired.append(sid)
            for sid in expired:
                del self._sessions[sid]

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")

    def get_active_count(self) -> int:
        """Return number of active sessions."""
        with self._lock:
            return len(self._sessions)
