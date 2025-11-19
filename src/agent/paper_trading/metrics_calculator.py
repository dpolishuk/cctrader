"""Performance metrics calculation for paper trading."""
import math
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from src.agent.database.paper_operations import PaperTradingDatabase

class PerformanceMetricsCalculator:
    """Calculate trading performance metrics."""

    def __init__(self, db: PaperTradingDatabase, portfolio_id: int):
        self.db = db
        self.portfolio_id = portfolio_id

    async def calculate_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics."""
        trades = await self.db.get_trade_history(self.portfolio_id, limit=1000)
        portfolio = await self.db.get_portfolio(self.portfolio_id)
        positions = await self.db.get_open_positions(self.portfolio_id)

        # Separate winning and losing trades
        closed_trades = [t for t in trades if t['realized_pnl'] is not None]
        winning_trades = [t for t in closed_trades if t['realized_pnl'] > 0]
        losing_trades = [t for t in closed_trades if t['realized_pnl'] < 0]

        total_trades = len(closed_trades)
        win_count = len(winning_trades)
        loss_count = len(losing_trades)

        # Win rate
        win_rate = (win_count / total_trades) if total_trades > 0 else 0.0

        # P&L metrics
        realized_pnl = sum(t['realized_pnl'] for t in closed_trades)
        unrealized_pnl = sum(p['unrealized_pnl'] for p in positions)
        total_pnl = realized_pnl + unrealized_pnl

        # Average win/loss
        avg_win = sum(t['realized_pnl'] for t in winning_trades) / win_count if win_count > 0 else 0
        avg_loss = sum(t['realized_pnl'] for t in losing_trades) / loss_count if loss_count > 0 else 0

        # Largest win/loss
        largest_win = max((t['realized_pnl'] for t in winning_trades), default=0)
        largest_loss = min((t['realized_pnl'] for t in losing_trades), default=0)

        # Profit factor
        gross_profit = sum(t['realized_pnl'] for t in winning_trades)
        gross_loss = abs(sum(t['realized_pnl'] for t in losing_trades))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0

        # Drawdown
        peak_equity = portfolio['peak_equity']
        current_equity = portfolio['current_equity']
        current_drawdown_pct = ((peak_equity - current_equity) / peak_equity) * 100 if peak_equity > 0 else 0

        # Calculate max drawdown from trade history
        max_drawdown_pct = await self._calculate_max_drawdown(trades, portfolio)

        # Sharpe and Sortino ratios (simplified)
        sharpe_ratio = await self._calculate_sharpe_ratio(closed_trades, portfolio)
        sortino_ratio = await self._calculate_sortino_ratio(closed_trades, portfolio)

        # Execution quality
        avg_slippage = sum(t['slippage_pct'] for t in trades) / len(trades) if trades else 0

        # Get execution quality details
        execution_lags = []
        for trade in trades:
            # Would need to join with execution_quality table
            # Simplified here
            execution_lags.append(100)  # Placeholder

        avg_execution_lag = sum(execution_lags) / len(execution_lags) if execution_lags else 0

        metrics = {
            "total_trades": total_trades,
            "winning_trades": win_count,
            "losing_trades": loss_count,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "max_drawdown_pct": max_drawdown_pct,
            "current_drawdown_pct": current_drawdown_pct,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "profit_factor": profit_factor,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "largest_win": largest_win,
            "largest_loss": largest_loss,
            "avg_slippage_pct": avg_slippage,
            "avg_execution_lag_ms": avg_execution_lag
        }

        # Save snapshot
        await self.db.save_performance_snapshot(self.portfolio_id, metrics)

        return metrics

    async def _calculate_max_drawdown(
        self,
        trades: List[Dict],
        portfolio: Dict
    ) -> float:
        """Calculate maximum drawdown from trade history."""
        if not trades:
            return 0.0

        # Reconstruct equity curve
        starting_equity = portfolio['starting_capital']
        equity_curve = [starting_equity]

        for trade in reversed(trades):  # Oldest first
            if trade['realized_pnl']:
                equity_curve.append(equity_curve[-1] + trade['realized_pnl'])

        # Find max drawdown
        peak = equity_curve[0]
        max_dd = 0.0

        for equity in equity_curve:
            if equity > peak:
                peak = equity
            dd = ((peak - equity) / peak) * 100
            if dd > max_dd:
                max_dd = dd

        return max_dd

    async def _calculate_sharpe_ratio(
        self,
        closed_trades: List[Dict],
        portfolio: Dict,
        risk_free_rate: float = 0.02  # 2% annual
    ) -> Optional[float]:
        """Calculate Sharpe ratio."""
        if len(closed_trades) < 2:
            return None

        # Calculate returns for each trade
        returns = []
        for trade in closed_trades:
            # Return as % of portfolio at trade time
            # Simplified: using current portfolio value
            ret = (trade['realized_pnl'] / portfolio['starting_capital']) * 100
            returns.append(ret)

        # Average return
        avg_return = sum(returns) / len(returns)

        # Standard deviation of returns
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        std_dev = math.sqrt(variance)

        if std_dev == 0:
            return None

        # Annualized Sharpe ratio (simplified)
        # Assuming daily trades for simplicity
        trading_days_per_year = 252
        sharpe = ((avg_return - (risk_free_rate / trading_days_per_year)) / std_dev) * math.sqrt(trading_days_per_year)

        return sharpe

    async def _calculate_sortino_ratio(
        self,
        closed_trades: List[Dict],
        portfolio: Dict,
        risk_free_rate: float = 0.02
    ) -> Optional[float]:
        """Calculate Sortino ratio (penalizes only downside volatility)."""
        if len(closed_trades) < 2:
            return None

        # Calculate returns
        returns = []
        for trade in closed_trades:
            ret = (trade['realized_pnl'] / portfolio['starting_capital']) * 100
            returns.append(ret)

        avg_return = sum(returns) / len(returns)

        # Downside deviation (only negative returns)
        negative_returns = [r for r in returns if r < 0]
        if not negative_returns:
            return None

        downside_variance = sum(r ** 2 for r in negative_returns) / len(negative_returns)
        downside_dev = math.sqrt(downside_variance)

        if downside_dev == 0:
            return None

        # Annualized Sortino ratio
        trading_days_per_year = 252
        sortino = ((avg_return - (risk_free_rate / trading_days_per_year)) / downside_dev) * math.sqrt(trading_days_per_year)

        return sortino
