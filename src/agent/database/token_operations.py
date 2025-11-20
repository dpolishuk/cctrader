"""Database operations for token tracking."""
import aiosqlite
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List


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

    async def get_recent_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent token tracking sessions.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session data dicts
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT
                    session_id,
                    start_time,
                    end_time,
                    operation_mode,
                    total_requests,
                    total_tokens_input,
                    total_tokens_output,
                    total_cost_usd
                FROM token_sessions
                WHERE end_time IS NOT NULL
                ORDER BY start_time DESC
                LIMIT ?
                """,
                (limit,)
            ) as cursor:
                rows = await cursor.fetchall()

                sessions = []
                for row in rows:
                    # Calculate duration
                    start = datetime.fromisoformat(row[1])
                    end = datetime.fromisoformat(row[2]) if row[2] else datetime.now()
                    duration = (end - start).total_seconds()

                    sessions.append({
                        'session_id': row[0],
                        'start_time': row[1],
                        'end_time': row[2],
                        'operation_mode': row[3],
                        'duration_seconds': duration,
                        'total_requests': row[4],
                        'total_tokens_input': row[5],
                        'total_tokens_output': row[6],
                        'total_tokens': row[5] + row[6],
                        'total_cost_usd': row[7]
                    })

                return sessions

    async def get_session_intervals(self, session_id: str, interval_minutes: int = 5) -> List[Dict[str, Any]]:
        """
        Get token usage broken down by intervals for a session.

        Args:
            session_id: Session ID to query
            interval_minutes: Interval duration in minutes

        Returns:
            List of interval data dicts
        """
        interval_seconds = interval_minutes * 60

        async with aiosqlite.connect(self.db_path) as db:
            # Get session start time
            async with db.execute(
                "SELECT start_time FROM token_sessions WHERE session_id = ?",
                (session_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return []
                start_time = row[0]

            # Query intervals
            async with db.execute(
                """
                SELECT
                    CAST((strftime('%s', timestamp) - strftime('%s', ?)) / ? AS INTEGER) as interval_num,
                    SUM(tokens_input) as tokens_input,
                    SUM(tokens_output) as tokens_output,
                    SUM(cost_usd) as cost,
                    COUNT(*) as requests,
                    MIN(timestamp) as interval_start,
                    MAX(timestamp) as interval_end
                FROM token_usage
                WHERE session_id = ?
                GROUP BY interval_num
                ORDER BY interval_num
                """,
                (start_time, interval_seconds, session_id)
            ) as cursor:
                rows = await cursor.fetchall()

                intervals = []
                for row in rows:
                    interval_start = datetime.fromisoformat(row[5])
                    interval_end = datetime.fromisoformat(row[6])
                    duration = (interval_end - interval_start).total_seconds()

                    intervals.append({
                        'interval_number': row[0] + 1,  # 1-indexed
                        'duration_seconds': duration,
                        'tokens_input': row[1],
                        'tokens_output': row[2],
                        'tokens_total': row[1] + row[2],
                        'cost': row[3],
                        'requests': row[4]
                    })

                return intervals
