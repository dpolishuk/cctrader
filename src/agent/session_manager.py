"""Session management for Claude Agent SDK.

Manages separate sessions for different operation types to maintain
context isolation and enable session resumption.
"""
import aiosqlite
from pathlib import Path
from typing import Optional, Dict
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages Claude Agent SDK sessions by operation type."""

    # Operation types for session isolation
    SCANNER = "scanner"
    ANALYSIS = "analysis"
    MONITOR = "monitor"
    PAPER_TRADING = "paper_trading"

    def __init__(self, db_path: Path):
        """
        Initialize session manager.

        Args:
            db_path: Path to database for session storage
        """
        self.db_path = db_path

    def generate_daily_session_id(self, operation_type: str) -> str:
        """
        Generate daily session ID with format: {operation_type}-YYYY-MM-DD.

        Args:
            operation_type: Type of operation (scanner, analysis, etc.)

        Returns:
            Daily session ID string
        """
        today = datetime.now().strftime("%Y-%m-%d")
        return f"{operation_type}-{today}"

    async def init_db(self):
        """Create sessions table if it doesn't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS agent_sessions (
                    operation_type TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT NOT NULL,
                    metadata TEXT
                )
            """)
            await db.commit()

    async def get_session_id(self, operation_type: str) -> Optional[str]:
        """
        Get existing session ID for operation type.

        Args:
            operation_type: Type of operation (scanner, analysis, etc.)

        Returns:
            Session ID if exists, None otherwise
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT session_id FROM agent_sessions WHERE operation_type = ?",
                (operation_type,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    # Update last_used_at
                    await db.execute(
                        "UPDATE agent_sessions SET last_used_at = ? WHERE operation_type = ?",
                        (datetime.now(timezone.utc).isoformat(), operation_type)
                    )
                    await db.commit()
                    logger.info(f"Resuming session for {operation_type}: {row[0]}")
                    return row[0]
        return None

    async def save_session_id(
        self,
        operation_type: str,
        session_id: str,
        metadata: Optional[str] = None
    ):
        """
        Save session ID for operation type.

        Args:
            operation_type: Type of operation
            session_id: Claude Agent SDK session ID
            metadata: Optional metadata JSON string
        """
        now = datetime.now(timezone.utc).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO agent_sessions (operation_type, session_id, created_at, last_used_at, metadata)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(operation_type) DO UPDATE SET
                    session_id = excluded.session_id,
                    last_used_at = excluded.last_used_at,
                    metadata = excluded.metadata
            """, (operation_type, session_id, now, now, metadata))
            await db.commit()
            logger.info(f"Saved session for {operation_type}: {session_id}")

    async def clear_session(self, operation_type: str):
        """
        Clear session for operation type (forces new session on next use).

        Args:
            operation_type: Type of operation
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM agent_sessions WHERE operation_type = ?",
                (operation_type,)
            )
            await db.commit()
            logger.info(f"Cleared session for {operation_type}")

    async def clear_all_sessions(self):
        """Clear all sessions (useful for reset/debugging)."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM agent_sessions")
            await db.commit()
            logger.info("Cleared all sessions")

    async def list_sessions(self) -> Dict[str, Dict]:
        """
        List all active sessions.

        Returns:
            Dict mapping operation_type to session info
        """
        sessions = {}
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT operation_type, session_id, created_at, last_used_at, metadata FROM agent_sessions"
            ) as cursor:
                async for row in cursor:
                    sessions[row[0]] = {
                        'session_id': row[1],
                        'created_at': row[2],
                        'last_used_at': row[3],
                        'metadata': row[4]
                    }
        return sessions
