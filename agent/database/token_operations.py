"""Database operations for token tracking."""
import aiosqlite
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional


class TokenDatabase:
    """Handles all token tracking database operations."""

    def __init__(self, db_path: Path):
        """
        Initialize token database.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path

    async def create_session(
        self,
        operation_mode: str
    ) -> str:
        """
        Create a new tracking session.

        Args:
            operation_mode: Operation type (monitor, analyze, scan_movers)

        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO token_sessions
                (session_id, start_time, operation_mode, is_active)
                VALUES (?, ?, ?, 1)
            """, (session_id, datetime.now().isoformat(), operation_mode))
            await db.commit()

        return session_id

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session information.

        Args:
            session_id: Session ID

        Returns:
            Session data or None
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM token_sessions WHERE session_id = ?",
                (session_id,)
            )
            row = await cursor.fetchone()

            if row:
                return dict(row)
            return None

    async def record_token_usage(
        self,
        session_id: str,
        operation_type: str,
        model: str,
        tokens_input: int,
        tokens_output: int,
        cost_usd: float,
        duration_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Record token usage for a request.

        Args:
            session_id: Session ID
            operation_type: Type of operation
            model: Model name
            tokens_input: Input tokens
            tokens_output: Output tokens
            cost_usd: Cost in USD
            duration_seconds: Request duration
            metadata: Additional context

        Returns:
            Usage record ID
        """
        tokens_total = tokens_input + tokens_output
        metadata_json = json.dumps(metadata) if metadata else None

        async with aiosqlite.connect(self.db_path) as db:
            # Insert usage record
            cursor = await db.execute("""
                INSERT INTO token_usage
                (session_id, operation_type, model, tokens_input, tokens_output,
                 tokens_total, cost_usd, duration_seconds, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, operation_type, model, tokens_input, tokens_output,
                tokens_total, cost_usd, duration_seconds, metadata_json
            ))

            usage_id = cursor.lastrowid

            # Update session totals
            await db.execute("""
                UPDATE token_sessions
                SET total_requests = total_requests + 1,
                    total_tokens_input = total_tokens_input + ?,
                    total_tokens_output = total_tokens_output + ?,
                    total_cost_usd = total_cost_usd + ?
                WHERE session_id = ?
            """, (tokens_input, tokens_output, cost_usd, session_id))

            await db.commit()

        return usage_id

    async def get_hourly_usage(self) -> Dict[str, Any]:
        """
        Get token usage for the last hour.

        Returns:
            Usage statistics
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT
                    COUNT(*) as request_count,
                    SUM(tokens_total) as total_tokens,
                    SUM(cost_usd) as total_cost_usd
                FROM token_usage
                WHERE timestamp >= datetime('now', '-1 hour')
            """)

            row = await cursor.fetchone()

            return {
                'request_count': row[0] or 0,
                'total_tokens': row[1] or 0,
                'total_cost_usd': row[2] or 0.0
            }

    async def get_daily_usage(self) -> Dict[str, Any]:
        """
        Get token usage for the last 24 hours.

        Returns:
            Usage statistics
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT
                    COUNT(*) as request_count,
                    SUM(tokens_total) as total_tokens,
                    SUM(cost_usd) as total_cost_usd
                FROM token_usage
                WHERE timestamp >= datetime('now', '-1 day')
            """)

            row = await cursor.fetchone()

            return {
                'request_count': row[0] or 0,
                'total_tokens': row[1] or 0,
                'total_cost_usd': row[2] or 0.0
            }

    async def end_session(self, session_id: str):
        """
        End a tracking session.

        Args:
            session_id: Session ID
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE token_sessions
                SET is_active = 0,
                    end_time = ?
                WHERE session_id = ?
            """, (datetime.now().isoformat(), session_id))
            await db.commit()
