"""
SQLite database for Arknights RAG.
Provides persistence for users, sessions, and chat messages.
"""

import json
import time
import sqlite3
import logging
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "arknights_rag.db"


class Database:
    """Thread-safe SQLite database wrapper."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(DEFAULT_DB_PATH)
        self.db_path = db_path
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER,
                title TEXT DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT DEFAULT '',
                extra_json TEXT DEFAULT '{}',
                created_at REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
        """)
        conn.commit()
        logger.info(f"[DB] Initialized database at {self.db_path}")

    # ===== User CRUD =====

    def create_user(self, username: str, password_hash: str) -> Optional[int]:
        """Create a new user. Returns user_id or None if username exists."""
        conn = self._get_conn()
        try:
            now = time.time()
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (username, password_hash, now, now),
            )
            conn.commit()
            user_id = cursor.lastrowid
            logger.info(f"[DB] Created user: {username} (id={user_id})")
            return user_id
        except sqlite3.IntegrityError:
            logger.warning(f"[DB] Username already exists: {username}")
            return None

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT id, username, password_hash, created_at, updated_at FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if row:
            return dict(row)
        return None

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by ID."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT id, username, password_hash, created_at, updated_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row:
            return dict(row)
        return None

    def update_password(self, user_id: int, new_password_hash: str) -> bool:
        """Update user password."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (new_password_hash, time.time(), user_id),
        )
        conn.commit()
        logger.info(f"[DB] Updated password for user_id={user_id}")
        return True

    # ===== Session CRUD =====

    def create_session(self, session_id: str, user_id: Optional[int] = None, title: str = "") -> str:
        """Create a new session record."""
        conn = self._get_conn()
        now = time.time()
        conn.execute(
            "INSERT OR REPLACE INTO sessions (id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, user_id, title, now, now),
        )
        conn.commit()
        logger.info(f"[DB] Created session: {session_id} (user_id={user_id})")
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session by ID."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT id, user_id, title, created_at, updated_at FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if row:
            return dict(row)
        return None

    def get_user_sessions(self, user_id: int) -> List[Dict]:
        """Get all sessions for a user, ordered by updated_at desc."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, user_id, title, created_at, updated_at FROM sessions WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def update_session_title(self, session_id: str, title: str):
        """Update session title."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title, time.time(), session_id),
        )
        conn.commit()

    def update_session_timestamp(self, session_id: str):
        """Touch session updated_at."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (time.time(), session_id),
        )
        conn.commit()

    def delete_session(self, session_id: str):
        """Delete a session and all its messages (CASCADE)."""
        conn = self._get_conn()
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        logger.info(f"[DB] Deleted session: {session_id}")

    def delete_user_sessions(self, user_id: int):
        """Delete all sessions for a user."""
        conn = self._get_conn()
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.commit()

    # ===== Message CRUD =====

    def add_message(self, session_id: str, role: str, content: str = "", extra: Dict = None):
        """Add a message to a session."""
        conn = self._get_conn()
        now = time.time()
        extra_json = json.dumps(extra or {}, ensure_ascii=False)
        conn.execute(
            "INSERT INTO messages (session_id, role, content, extra_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, extra_json, now),
        )
        conn.commit()

    def add_messages_batch(self, session_id: str, messages: List[Dict]):
        """Add multiple messages in a batch. Used for loading session history."""
        conn = self._get_conn()
        now = time.time()
        rows = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            # Extract extra fields (everything except role, content)
            extra = {k: v for k, v in msg.items() if k not in ("role", "content")}
            extra_json = json.dumps(extra, ensure_ascii=False)
            rows.append((session_id, role, content, extra_json, now))
        conn.executemany(
            "INSERT INTO messages (session_id, role, content, extra_json, created_at) VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()

    def get_session_messages(self, session_id: str, limit: int = 1000) -> List[Dict]:
        """Get messages for a session, ordered by created_at."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, session_id, role, content, extra_json, created_at FROM messages WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        result = []
        for row in rows:
            msg = {
                "role": row["role"],
                "content": row["content"],
            }
            try:
                extra = json.loads(row["extra_json"])
                msg.update(extra)
            except (json.JSONDecodeError, TypeError):
                pass
            result.append(msg)
        return result

    def get_session_message_count(self, session_id: str) -> int:
        """Count messages in a session."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return row["cnt"] if row else 0

    def clear_session_messages(self, session_id: str):
        """Delete all messages in a session."""
        conn = self._get_conn()
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.commit()


# ===== Singleton =====

_db_instance: Optional[Database] = None
_db_lock = threading.Lock()


def get_db(db_path: str = None) -> Database:
    """Get or create the singleton Database instance."""
    global _db_instance
    if _db_instance is None:
        with _db_lock:
            if _db_instance is None:
                _db_instance = Database(db_path)
    return _db_instance
