"""
Database layer for Arknights RAG.
SQLite-based persistence for users, sessions, and messages.
"""

from backend.database.db import Database, get_db

__all__ = ["Database", "get_db"]
