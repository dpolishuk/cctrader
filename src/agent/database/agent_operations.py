"""Database operations for multi-agent pipeline."""
import aiosqlite
from pathlib import Path
from datetime import date
from typing import Optional, List, Dict, Any


class AgentOperations:
    """CRUD operations for agent pipeline outputs."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    async def save_agent_output(
        self,
        session_id: str,
        symbol: str,
        agent_type: str,
        input_json: str,
        output_json: str,
        tokens_used: int,
        duration_ms: int
    ) -> int:
        """Save agent output and return ID."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO agent_outputs
                (session_id, symbol, agent_type, input_json, output_json, tokens_used, duration_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, symbol, agent_type, input_json, output_json, tokens_used, duration_ms)
            )
            await db.commit()
            return cursor.lastrowid

    async def save_risk_decision(
        self,
        session_id: str,
        symbol: str,
        action: str,
        original_confidence: int,
        audited_confidence: int,
        modifications: str,
        warnings: str,
        risk_score: int,
        portfolio_snapshot: str
    ) -> int:
        """Save risk decision and return ID."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO risk_decisions
                (session_id, symbol, action, original_confidence, audited_confidence,
                 modifications, warnings, risk_score, portfolio_snapshot)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, symbol, action, original_confidence, audited_confidence,
                 modifications, warnings, risk_score, portfolio_snapshot)
            )
            await db.commit()
            return cursor.lastrowid

    async def save_execution_report(
        self,
        session_id: str,
        symbol: str,
        status: str,
        order_type: Optional[str],
        requested_entry: float,
        actual_entry: Optional[float],
        slippage_pct: Optional[float],
        position_size: Optional[float],
        execution_time_ms: Optional[int],
        abort_reason: Optional[str]
    ) -> int:
        """Save execution report and return ID."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO execution_reports
                (session_id, symbol, status, order_type, requested_entry, actual_entry,
                 slippage_pct, position_size, execution_time_ms, abort_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, symbol, status, order_type, requested_entry, actual_entry,
                 slippage_pct, position_size, execution_time_ms, abort_reason)
            )
            await db.commit()
            return cursor.lastrowid

    async def save_trade_review(
        self,
        trade_id: str,
        symbol: str,
        pnl_pct: float,
        pnl_usd: float,
        result: str,
        what_worked: str,
        what_didnt_work: str,
        recommendation: str
    ) -> int:
        """Save trade review and return ID."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO trade_reviews
                (trade_id, symbol, pnl_pct, pnl_usd, result, what_worked,
                 what_didnt_work, recommendation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (trade_id, symbol, pnl_pct, pnl_usd, result, what_worked,
                 what_didnt_work, recommendation)
            )
            await db.commit()
            return cursor.lastrowid

    async def save_daily_report(
        self,
        report_date: date,
        total_trades: int,
        wins: int,
        losses: int,
        win_rate: float,
        total_pnl_pct: float,
        total_pnl_usd: float,
        patterns_json: str,
        recommendations_json: str,
        agent_performance_json: str
    ) -> int:
        """Save daily report and return ID."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT OR REPLACE INTO daily_reports
                (report_date, total_trades, wins, losses, win_rate, total_pnl_pct,
                 total_pnl_usd, patterns_json, recommendations_json, agent_performance_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (report_date.isoformat(), total_trades, wins, losses, win_rate,
                 total_pnl_pct, total_pnl_usd, patterns_json, recommendations_json,
                 agent_performance_json)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_agent_outputs_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all agent outputs for a session."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM agent_outputs
                WHERE session_id = ?
                ORDER BY created_at ASC
                """,
                (session_id,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_risk_decisions_by_date(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Get risk decisions in date range."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM risk_decisions
                WHERE date(created_at) BETWEEN ? AND ?
                ORDER BY created_at DESC
                """,
                (start_date.isoformat(), end_date.isoformat())
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_daily_report(self, report_date: date) -> Optional[Dict[str, Any]]:
        """Get daily report for a specific date."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM daily_reports WHERE report_date = ?",
                (report_date.isoformat(),)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
