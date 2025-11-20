"""Database operations for paper trading."""
import aiosqlite
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

class PaperTradingDatabase:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    # Portfolio Management

    async def create_portfolio(
        self,
        name: str,
        starting_capital: float = 100000.0,
        execution_mode: str = "realistic",
        max_position_size_pct: float = 5.0,
        max_total_exposure_pct: float = 80.0,
        max_daily_loss_pct: float = 5.0,
        max_drawdown_pct: float = 10.0
    ) -> int:
        """Create a new paper trading portfolio."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO paper_portfolios
                (name, starting_capital, current_equity, execution_mode,
                 max_position_size_pct, max_total_exposure_pct,
                 max_daily_loss_pct, max_drawdown_pct, peak_equity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, starting_capital, starting_capital, execution_mode,
                 max_position_size_pct, max_total_exposure_pct,
                 max_daily_loss_pct, max_drawdown_pct, starting_capital)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_portfolio(self, portfolio_id: int) -> Optional[Dict]:
        """Get portfolio by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM paper_portfolios WHERE id = ?",
                (portfolio_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_portfolio_by_name(self, name: str) -> Optional[Dict]:
        """Get portfolio by name."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM paper_portfolios WHERE name = ?",
                (name,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_portfolio_equity(
        self,
        portfolio_id: int,
        current_equity: float
    ) -> None:
        """Update portfolio equity and peak equity tracking."""
        async with aiosqlite.connect(self.db_path) as db:
            # Get current peak
            async with db.execute(
                "SELECT peak_equity FROM paper_portfolios WHERE id = ?",
                (portfolio_id,)
            ) as cursor:
                row = await cursor.fetchone()
                peak_equity = row[0] if row else current_equity

            # Update peak if current equity is higher
            new_peak = max(peak_equity, current_equity)

            await db.execute(
                """
                UPDATE paper_portfolios
                SET current_equity = ?,
                    peak_equity = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (current_equity, new_peak, portfolio_id)
            )
            await db.commit()

    async def set_circuit_breaker(
        self,
        portfolio_id: int,
        active: bool
    ) -> None:
        """Activate or deactivate circuit breaker."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE paper_portfolios
                SET circuit_breaker_active = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (1 if active else 0, portfolio_id)
            )
            await db.commit()

    # Position Management

    async def open_position(
        self,
        portfolio_id: int,
        symbol: str,
        position_type: str,
        entry_price: float,
        quantity: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> int:
        """Open a new position."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO paper_positions
                (portfolio_id, symbol, position_type, entry_price, current_price,
                 quantity, stop_loss, take_profit, is_open)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (portfolio_id, symbol, position_type, entry_price, entry_price,
                 quantity, stop_loss, take_profit)
            )
            await db.commit()
            return cursor.lastrowid

    async def update_position_price(
        self,
        position_id: int,
        current_price: float,
        unrealized_pnl: float
    ) -> None:
        """Update position current price and unrealized P&L."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE paper_positions
                SET current_price = ?,
                    unrealized_pnl = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (current_price, unrealized_pnl, position_id)
            )
            await db.commit()

    async def close_position(self, position_id: int) -> None:
        """Close a position."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE paper_positions
                SET is_open = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (position_id,)
            )
            await db.commit()

    async def get_open_positions(
        self,
        portfolio_id: int
    ) -> List[Dict]:
        """Get all open positions for a portfolio."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM paper_positions
                WHERE portfolio_id = ? AND is_open = 1
                ORDER BY opened_at DESC
                """,
                (portfolio_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_position_by_symbol(
        self,
        portfolio_id: int,
        symbol: str
    ) -> Optional[Dict]:
        """Get open position for a specific symbol."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM paper_positions
                WHERE portfolio_id = ? AND symbol = ? AND is_open = 1
                LIMIT 1
                """,
                (portfolio_id, symbol)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    # Trade History

    async def record_trade(
        self,
        portfolio_id: int,
        symbol: str,
        trade_type: str,
        price: float,
        quantity: float,
        execution_mode: str,
        slippage_pct: float,
        actual_fill_price: float,
        signal_price: Optional[float] = None,
        signal_id: Optional[int] = None,
        realized_pnl: Optional[float] = None,
        commission: float = 0.0,
        notes: Optional[str] = None
    ) -> int:
        """Record a trade in history."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO paper_trades
                (portfolio_id, symbol, trade_type, price, quantity, execution_mode,
                 slippage_pct, actual_fill_price, signal_price, signal_id,
                 realized_pnl, commission, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (portfolio_id, symbol, trade_type, price, quantity, execution_mode,
                 slippage_pct, actual_fill_price, signal_price, signal_id,
                 realized_pnl, commission, notes)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_trade_history(
        self,
        portfolio_id: int,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get trade history for portfolio."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if symbol:
                query = """
                    SELECT * FROM paper_trades
                    WHERE portfolio_id = ? AND symbol = ?
                    ORDER BY executed_at DESC
                    LIMIT ?
                """
                params = (portfolio_id, symbol, limit)
            else:
                query = """
                    SELECT * FROM paper_trades
                    WHERE portfolio_id = ?
                    ORDER BY executed_at DESC
                    LIMIT ?
                """
                params = (portfolio_id, limit)

            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    # Risk Audit

    async def log_risk_event(
        self,
        portfolio_id: int,
        event_type: str,
        severity: str,
        rule_type: str,
        rule_limit: float,
        current_value: float,
        symbol: Optional[str] = None,
        trade_id: Optional[int] = None,
        message: Optional[str] = None
    ) -> int:
        """Log a risk compliance event."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO paper_risk_audit
                (portfolio_id, event_type, severity, rule_type, rule_limit,
                 current_value, symbol, trade_id, message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (portfolio_id, event_type, severity, rule_type, rule_limit,
                 current_value, symbol, trade_id, message)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_risk_violations(
        self,
        portfolio_id: int,
        hours: int = 24,
        severity: Optional[str] = None
    ) -> List[Dict]:
        """Get recent risk violations."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cutoff = datetime.now() - timedelta(hours=hours)

            if severity:
                query = """
                    SELECT * FROM paper_risk_audit
                    WHERE portfolio_id = ?
                    AND severity = ?
                    AND triggered_at >= ?
                    ORDER BY triggered_at DESC
                """
                params = (portfolio_id, severity, cutoff)
            else:
                query = """
                    SELECT * FROM paper_risk_audit
                    WHERE portfolio_id = ?
                    AND triggered_at >= ?
                    ORDER BY triggered_at DESC
                """
                params = (portfolio_id, cutoff)

            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    # Performance Metrics

    async def save_performance_snapshot(
        self,
        portfolio_id: int,
        metrics: Dict[str, Any]
    ) -> int:
        """Save performance metrics snapshot."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO paper_performance_metrics
                (portfolio_id, total_trades, winning_trades, losing_trades,
                 win_rate, total_pnl, realized_pnl, unrealized_pnl,
                 max_drawdown_pct, current_drawdown_pct, sharpe_ratio,
                 sortino_ratio, profit_factor, avg_win, avg_loss,
                 largest_win, largest_loss, avg_slippage_pct, avg_execution_lag_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    portfolio_id,
                    metrics.get('total_trades', 0),
                    metrics.get('winning_trades', 0),
                    metrics.get('losing_trades', 0),
                    metrics.get('win_rate', 0.0),
                    metrics.get('total_pnl', 0.0),
                    metrics.get('realized_pnl', 0.0),
                    metrics.get('unrealized_pnl', 0.0),
                    metrics.get('max_drawdown_pct', 0.0),
                    metrics.get('current_drawdown_pct', 0.0),
                    metrics.get('sharpe_ratio'),
                    metrics.get('sortino_ratio'),
                    metrics.get('profit_factor'),
                    metrics.get('avg_win'),
                    metrics.get('avg_loss'),
                    metrics.get('largest_win'),
                    metrics.get('largest_loss'),
                    metrics.get('avg_slippage_pct'),
                    metrics.get('avg_execution_lag_ms')
                )
            )
            await db.commit()
            return cursor.lastrowid

    async def get_latest_metrics(
        self,
        portfolio_id: int
    ) -> Optional[Dict]:
        """Get latest performance metrics."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM paper_performance_metrics
                WHERE portfolio_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (portfolio_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_symbol_pnl_summary(
        self,
        portfolio_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        min_trades: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get P&L summary aggregated by symbol.

        Args:
            portfolio_id: Portfolio ID
            start_date: Filter trades after this date (optional)
            end_date: Filter trades before this date (optional)
            min_trades: Minimum trade count to include symbol (default: 0)

        Returns:
            List of dicts with:
            - symbol: str
            - total_pnl: float (realized + unrealized)
            - realized_pnl: float
            - unrealized_pnl: float
            - trade_count: int
            - win_rate: float (0-100)
            - avg_pnl: float
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Build date filter
            date_filter = ""
            params = [portfolio_id, portfolio_id]
            if start_date:
                date_filter += " AND t.executed_at >= ?"
                params.insert(1, start_date.isoformat())
            if end_date:
                date_filter += " AND t.executed_at <= ?"
                params.insert(2 if start_date else 1, end_date.isoformat())

            params.append(min_trades)

            query = f"""
            WITH realized AS (
                SELECT
                    symbol,
                    SUM(realized_pnl) as realized_pnl,
                    COUNT(*) as trade_count,
                    SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as winning_trades
                FROM paper_trades t
                WHERE portfolio_id = ?
                  AND realized_pnl IS NOT NULL
                  {date_filter}
                GROUP BY symbol
            ),
            unrealized AS (
                SELECT
                    symbol,
                    SUM(unrealized_pnl) as unrealized_pnl
                FROM paper_positions
                WHERE portfolio_id = ?
                  AND is_open = 1
                GROUP BY symbol
            ),
            combined AS (
                SELECT
                    COALESCE(r.symbol, u.symbol) as symbol,
                    COALESCE(r.realized_pnl, 0) as realized_pnl,
                    COALESCE(u.unrealized_pnl, 0) as unrealized_pnl,
                    COALESCE(r.realized_pnl, 0) + COALESCE(u.unrealized_pnl, 0) as total_pnl,
                    COALESCE(r.trade_count, 0) as trade_count,
                    CASE
                        WHEN r.trade_count > 0
                        THEN CAST(r.winning_trades AS REAL) / r.trade_count * 100
                        ELSE 0
                    END as win_rate,
                    CASE
                        WHEN r.trade_count > 0
                        THEN r.realized_pnl / r.trade_count
                        ELSE 0
                    END as avg_pnl
                FROM realized r
                LEFT JOIN unrealized u ON r.symbol = u.symbol
                UNION
                SELECT
                    u.symbol,
                    0 as realized_pnl,
                    u.unrealized_pnl,
                    u.unrealized_pnl as total_pnl,
                    0 as trade_count,
                    0 as win_rate,
                    0 as avg_pnl
                FROM unrealized u
                LEFT JOIN realized r ON u.symbol = r.symbol
                WHERE r.symbol IS NULL
            )
            SELECT * FROM combined
            WHERE trade_count >= ?
            ORDER BY total_pnl DESC
            """

            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    # Execution Quality

    async def record_execution_quality(
        self,
        trade_id: int,
        signal_generated_at: datetime,
        execution_started_at: datetime,
        execution_completed_at: datetime,
        signal_price: float,
        executed_price: float,
        slippage_pct: float,
        execution_lag_ms: int,
        market_volatility: Optional[float] = None,
        partial_fill: bool = False,
        fill_percentage: float = 100.0
    ) -> int:
        """Record execution quality metrics."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO paper_execution_quality
                (trade_id, signal_generated_at, execution_started_at,
                 execution_completed_at, signal_price, executed_price,
                 slippage_pct, execution_lag_ms, market_volatility,
                 partial_fill, fill_percentage)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (trade_id, signal_generated_at, execution_started_at,
                 execution_completed_at, signal_price, executed_price,
                 slippage_pct, execution_lag_ms, market_volatility,
                 1 if partial_fill else 0, fill_percentage)
            )
            await db.commit()
            return cursor.lastrowid

    # Market Movers Strategy

    async def save_mover_signal(
        self,
        symbol: str,
        direction: str,
        confidence: int,
        entry_price: float,
        stop_loss: float,
        tp1: float,
        position_size_usd: float,
        risk_amount_usd: float,
        technical_score: float = None,
        sentiment_score: float = None,
        liquidity_score: float = None,
        correlation_score: float = None,
        analysis: Dict = None
    ) -> int:
        """Save a mover signal to database."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO movers_signals
                (symbol, direction, confidence, entry_price, stop_loss, tp1,
                 position_size_usd, risk_amount_usd, technical_score, sentiment_score,
                 liquidity_score, correlation_score, analysis)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (symbol, direction, confidence, entry_price, stop_loss, tp1,
                 position_size_usd, risk_amount_usd, technical_score, sentiment_score,
                 liquidity_score, correlation_score, json.dumps(analysis) if analysis else None)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_mover_signal(self, signal_id: int) -> Optional[Dict]:
        """Get mover signal by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM movers_signals WHERE id = ?",
                (signal_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    result = dict(row)
                    if result.get('analysis'):
                        result['analysis'] = json.loads(result['analysis'])
                    return result
                return None

    async def save_mover_rejection(
        self,
        symbol: str,
        direction: str,
        confidence: int,
        reason: str,
        details: Dict = None
    ) -> int:
        """Save a mover rejection to database."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO movers_rejections
                (symbol, direction, confidence, reason, details)
                VALUES (?, ?, ?, ?, ?)
                """,
                (symbol, direction, confidence, reason, json.dumps(details) if details else None)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_recent_rejections(self, limit: int = 10) -> List[Dict]:
        """Get recent rejections."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM movers_rejections ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
                results = []
                for row in rows:
                    result = dict(row)
                    if result.get('details'):
                        result['details'] = json.loads(result['details'])
                    results.append(result)
                return results

    async def save_movers_metrics(self, metrics: Dict) -> int:
        """Save movers scan cycle metrics."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO movers_metrics
                (cycle_duration_seconds, movers_found, signals_generated,
                 signals_executed, signals_rejected, open_positions,
                 total_exposure_pct, daily_pnl_pct, weekly_pnl_pct, risk_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (metrics.get('cycle_duration_seconds'),
                 metrics.get('movers_found'),
                 metrics.get('signals_generated'),
                 metrics.get('signals_executed'),
                 metrics.get('signals_rejected'),
                 metrics.get('open_positions'),
                 metrics.get('total_exposure_pct'),
                 metrics.get('daily_pnl_pct'),
                 metrics.get('weekly_pnl_pct'),
                 metrics.get('risk_level'))
            )
            await db.commit()
            return cursor.lastrowid
