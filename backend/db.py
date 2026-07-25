"""
backend/db.py — SQLite database initialization and helpers.
"""
import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "arknights_rag.db"


async def get_db() -> aiosqlite.Connection:
    """Get a database connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    """Initialize database tables."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account TEXT UNIQUE NOT NULL,
                username TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                password_changed_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS conversations (
                session_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (session_id) REFERENCES conversations(session_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
            CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at);
            CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);

            CREATE TABLE IF NOT EXISTS traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_message TEXT NOT NULL DEFAULT '',
                model_id TEXT NOT NULL DEFAULT '',
                total_rounds INTEGER NOT NULL DEFAULT 0,
                total_time_ms REAL NOT NULL DEFAULT 0,
                total_llm_calls INTEGER NOT NULL DEFAULT 0,
                total_tool_calls INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                answer_length INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'success',
                error TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_traces_session_id ON traces(session_id);
            CREATE INDEX IF NOT EXISTS idx_traces_created_at ON traces(created_at);
        """)
        await db.commit()
