"""Portfolio management for paper trading."""
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from src.agent.database.paper_operations import PaperTradingDatabase
from src.agent.paper_trading.execution_engine import ExecutionEngine
from src.agent.paper_trading.risk_manager import RiskManager, TradeProposal

class PaperPortfolioManager:
    """Manages paper trading portfolio operations."""

    def __init__(
        self,
        db_path: Path,
        portfolio_name: str
    ):
        self.db = PaperTradingDatabase(db_path)
        self.portfolio_name = portfolio_name
        self.portfolio_id: Optional[int] = None
        self.portfolio: Optional[Dict] = None
        self.execution_engine: Optional[ExecutionEngine] = None
        self.risk_manager: Optional[RiskManager] = None

    async def initialize(self) -> None:
        """Initialize or load portfolio."""
        # Try to load existing portfolio
        self.portfolio = await self.db.get_portfolio_by_name(self.portfolio_name)

        if not self.portfolio:
            # Create new portfolio
            self.portfolio_id = await self.db.create_portfolio(
                name=self.portfolio_name,
                starting_capital=100000.0,  # Default $100k
                execution_mode="realistic"
            )
            self.portfolio = await self.db.get_portfolio(self.portfolio_id)
        else:
            self.portfolio_id = self.portfolio['id']

        # Initialize execution engine with portfolio's mode
        self.execution_engine = ExecutionEngine(
            mode=self.portfolio['execution_mode']
        )

        # Initialize risk manager
        self.risk_manager = RiskManager(self.db, self.portfolio_id)
        await self.risk_manager.initialize()

    async def execute_signal(
        self,
        signal: Dict[str, Any],
        current_price: float,
        market_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Execute a trading signal in paper trading mode.

        Args:
            signal: Trading signal with type, confidence, etc.
            current_price: Current market price
            market_data: Optional market data for realistic execution

        Returns:
            Execution result dictionary
        """
        signal_type = signal.get('type', signal.get('signal_type', 'HOLD'))
        symbol = signal.get('symbol', 'BTC/USDT')
        confidence = signal.get('confidence', 0.5)

        # Check for existing position
        existing_position = await self.db.get_position_by_symbol(
            self.portfolio_id,
            symbol
        )

        result = {
            "executed": False,
            "action": "NONE",
            "reason": "",
            "execution_details": None
        }

        # Determine action based on signal and existing position
        if signal_type in ['STRONG_BUY', 'BUY'] and not existing_position:
            # Open long position
            result = await self._open_position(
                symbol, "LONG", current_price, confidence, market_data
            )
        elif signal_type in ['STRONG_SELL', 'SELL'] and existing_position:
            # Close existing long position
            result = await self._close_position(
                existing_position, current_price, market_data
            )
        elif signal_type == 'HOLD':
            result['reason'] = "HOLD signal - no action taken"
        else:
            result['reason'] = f"No action: signal={signal_type}, has_position={bool(existing_position)}"

        return result

    async def _open_position(
        self,
        symbol: str,
        position_type: str,
        current_price: float,
        confidence: float,
        market_data: Optional[Dict]
    ) -> Dict[str, Any]:
        """Open a new position."""
        # Calculate position size based on confidence and risk limits
        portfolio = await self.db.get_portfolio(self.portfolio_id)

        # Base position size: 2-5% of portfolio based on confidence
        base_pct = 2.0 + (confidence * 3.0)  # 2% at 0 confidence, 5% at 1.0
        position_value = portfolio['current_equity'] * (base_pct / 100)
        quantity = position_value / current_price

        # Create trade proposal
        trade = TradeProposal(
            symbol=symbol,
            side="BUY" if position_type == "LONG" else "SELL",
            quantity=quantity,
            price=current_price,
            position_type=position_type
        )

        # Pre-trade risk validation
        is_valid, violations = await self.risk_manager.validate_trade(trade)

        if not is_valid:
            return {
                "executed": False,
                "action": f"OPEN_{position_type}",
                "reason": f"Risk check failed: {'; '.join(violations)}",
                "violations": violations
            }

        # Execute trade
        signal_time = datetime.now()
        execution_result = await self.execution_engine.execute_trade(
            symbol=symbol,
            order_type="MARKET",
            side=trade.side,
            quantity=quantity,
            signal_price=current_price,
            current_market_data=market_data
        )

        filled_price = execution_result['filled_price']
        filled_quantity = execution_result['filled_quantity']

        # Calculate stop loss and take profit (2% stop, 4% target)
        if position_type == "LONG":
            stop_loss = filled_price * 0.98
            take_profit = filled_price * 1.04
        else:  # SHORT
            stop_loss = filled_price * 1.02
            take_profit = filled_price * 0.96

        # Record trade in database
        trade_id = await self.db.record_trade(
            portfolio_id=self.portfolio_id,
            symbol=symbol,
            trade_type=f"OPEN_{position_type}",
            price=current_price,
            quantity=filled_quantity,
            execution_mode=self.portfolio['execution_mode'],
            slippage_pct=execution_result['slippage_pct'],
            actual_fill_price=filled_price,
            signal_price=current_price,
            notes=f"Opened {position_type} position with {confidence:.1%} confidence"
        )

        # Open position in database
        position_id = await self.db.open_position(
            portfolio_id=self.portfolio_id,
            symbol=symbol,
            position_type=position_type,
            entry_price=filled_price,
            quantity=filled_quantity,
            stop_loss=stop_loss,
            take_profit=take_profit
        )

        # Record execution quality
        await self.db.record_execution_quality(
            trade_id=trade_id,
            signal_generated_at=signal_time,
            execution_started_at=execution_result['execution_started_at'],
            execution_completed_at=execution_result['execution_completed_at'],
            signal_price=current_price,
            executed_price=filled_price,
            slippage_pct=execution_result['slippage_pct'],
            execution_lag_ms=execution_result['execution_time_ms'],
            partial_fill=execution_result['partial_fill'],
            fill_percentage=execution_result['fill_percentage']
        )

        # Post-trade reconciliation
        await self.risk_manager.reconcile_trade(trade_id, execution_result)

        # Check circuit breakers after trade
        await self.risk_manager.check_circuit_breakers()

        return {
            "executed": True,
            "action": f"OPEN_{position_type}",
            "reason": f"Opened {position_type} position",
            "execution_details": {
                "symbol": symbol,
                "position_id": position_id,
                "trade_id": trade_id,
                "entry_price": filled_price,
                "quantity": filled_quantity,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "slippage_pct": execution_result['slippage_pct'],
                "execution_time_ms": execution_result['execution_time_ms']
            }
        }

    async def _close_position(
        self,
        position: Dict,
        current_price: float,
        market_data: Optional[Dict]
    ) -> Dict[str, Any]:
        """Close an existing position."""
        symbol = position['symbol']
        position_type = position['position_type']
        entry_price = position['entry_price']
        quantity = position['quantity']

        # Execute closing trade
        signal_time = datetime.now()
        execution_result = await self.execution_engine.execute_trade(
            symbol=symbol,
            order_type="MARKET",
            side="SELL" if position_type == "LONG" else "BUY",
            quantity=quantity,
            signal_price=current_price,
            current_market_data=market_data
        )

        filled_price = execution_result['filled_price']

        # Calculate realized P&L
        if position_type == "LONG":
            realized_pnl = (filled_price - entry_price) * quantity
        else:  # SHORT
            realized_pnl = (entry_price - filled_price) * quantity

        pnl_pct = (realized_pnl / (entry_price * quantity)) * 100

        # Record closing trade
        trade_id = await self.db.record_trade(
            portfolio_id=self.portfolio_id,
            symbol=symbol,
            trade_type="CLOSE",
            price=current_price,
            quantity=quantity,
            execution_mode=self.portfolio['execution_mode'],
            slippage_pct=execution_result['slippage_pct'],
            actual_fill_price=filled_price,
            signal_price=current_price,
            realized_pnl=realized_pnl,
            notes=f"Closed {position_type} position: {realized_pnl:+.2f} ({pnl_pct:+.2f}%)"
        )

        # Close position in database
        await self.db.close_position(position['id'])

        # Update portfolio equity
        portfolio = await self.db.get_portfolio(self.portfolio_id)
        new_equity = portfolio['current_equity'] + realized_pnl
        await self.db.update_portfolio_equity(self.portfolio_id, new_equity)

        # Record execution quality
        await self.db.record_execution_quality(
            trade_id=trade_id,
            signal_generated_at=signal_time,
            execution_started_at=execution_result['execution_started_at'],
            execution_completed_at=execution_result['execution_completed_at'],
            signal_price=current_price,
            executed_price=filled_price,
            slippage_pct=execution_result['slippage_pct'],
            execution_lag_ms=execution_result['execution_time_ms'],
            partial_fill=execution_result['partial_fill'],
            fill_percentage=execution_result['fill_percentage']
        )

        return {
            "executed": True,
            "action": "CLOSE",
            "reason": f"Closed {position_type} position",
            "execution_details": {
                "symbol": symbol,
                "trade_id": trade_id,
                "exit_price": filled_price,
                "entry_price": entry_price,
                "quantity": quantity,
                "realized_pnl": realized_pnl,
                "pnl_pct": pnl_pct,
                "slippage_pct": execution_result['slippage_pct']
            }
        }

    async def update_positions(self, current_prices: Dict[str, float]) -> None:
        """Update all open positions with current prices."""
        positions = await self.db.get_open_positions(self.portfolio_id)

        for position in positions:
            symbol = position['symbol']
            if symbol in current_prices:
                current_price = current_prices[symbol]
                entry_price = position['entry_price']
                quantity = position['quantity']
                position_type = position['position_type']

                # Calculate unrealized P&L
                if position_type == "LONG":
                    unrealized_pnl = (current_price - entry_price) * quantity
                else:  # SHORT
                    unrealized_pnl = (entry_price - current_price) * quantity

                # Update position
                await self.db.update_position_price(
                    position['id'],
                    current_price,
                    unrealized_pnl
                )

        # Update portfolio equity (including unrealized P&L)
        await self._update_portfolio_equity()

        # Run continuous monitoring
        alerts = await self.risk_manager.monitor_positions()

        # Check circuit breakers
        await self.risk_manager.check_circuit_breakers()

    async def _update_portfolio_equity(self) -> None:
        """Calculate and update total portfolio equity."""
        portfolio = await self.db.get_portfolio(self.portfolio_id)
        positions = await self.db.get_open_positions(self.portfolio_id)

        # Calculate total unrealized P&L
        total_unrealized_pnl = sum(
            pos['unrealized_pnl'] for pos in positions
        )

        # Total equity = starting capital + all P&L
        # (Simplified - in production would track realized separately)
        new_equity = portfolio['starting_capital'] + total_unrealized_pnl

        await self.db.update_portfolio_equity(self.portfolio_id, new_equity)

    def get_total_value(self) -> float:
        """
        Get current total portfolio value.

        Returns:
            Current equity value
        """
        if not self.portfolio:
            return 0.0
        return self.portfolio.get('current_equity', 0.0)

    async def count_open_positions(self) -> int:
        """
        Count number of open positions.

        Returns:
            Number of open positions
        """
        positions = await self.db.get_open_positions(self.portfolio_id)
        return len(positions)

    async def calculate_exposure_pct(self) -> float:
        """
        Calculate current portfolio exposure percentage.

        Returns:
            Exposure as percentage of equity
        """
        positions = await self.db.get_open_positions(self.portfolio_id)

        total_exposure = sum(
            pos['quantity'] * pos['current_price']
            for pos in positions
        )

        current_equity = self.get_total_value()
        if current_equity <= 0:
            return 0.0

        return (total_exposure / current_equity) * 100

    async def calculate_daily_pnl_pct(self) -> float:
        """
        Calculate daily P&L percentage (realized + unrealized).

        Returns:
            Daily P&L as percentage of starting equity
        """
        portfolio = await self.db.get_portfolio(self.portfolio_id)
        starting_capital = portfolio['starting_capital']

        # Get trades from today (realized P&L)
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        trades = await self.db.get_trade_history(self.portfolio_id, limit=1000)

        daily_realized_pnl = sum(
            trade.get('realized_pnl', 0) or 0
            for trade in trades
            if trade.get('executed_at') and
               datetime.fromisoformat(trade['executed_at'].replace('Z', '+00:00')) >= today_start
        )

        # Get unrealized P&L from open positions
        positions = await self.db.get_open_positions(self.portfolio_id)
        daily_unrealized_pnl = sum(pos.get('unrealized_pnl', 0) or 0 for pos in positions)

        # Calculate total daily P&L percentage
        total_daily_pnl = daily_realized_pnl + daily_unrealized_pnl

        if starting_capital <= 0:
            return 0.0

        return (total_daily_pnl / starting_capital) * 100

    async def calculate_weekly_pnl_pct(self) -> float:
        """
        Calculate weekly P&L percentage (last 7 days).

        Returns:
            Weekly P&L as percentage of starting equity
        """
        portfolio = await self.db.get_portfolio(self.portfolio_id)
        starting_capital = portfolio['starting_capital']

        # Get trades from last 7 days
        week_start = datetime.now() - timedelta(days=7)
        trades = await self.db.get_trade_history(self.portfolio_id, limit=1000)

        weekly_realized_pnl = sum(
            trade.get('realized_pnl', 0) or 0
            for trade in trades
            if trade.get('executed_at') and
               datetime.fromisoformat(trade['executed_at'].replace('Z', '+00:00')) >= week_start
        )

        # Get unrealized P&L from open positions
        positions = await self.db.get_open_positions(self.portfolio_id)
        weekly_unrealized_pnl = sum(pos.get('unrealized_pnl', 0) or 0 for pos in positions)

        # Calculate total weekly P&L percentage
        total_weekly_pnl = weekly_realized_pnl + weekly_unrealized_pnl

        if starting_capital <= 0:
            return 0.0

        return (total_weekly_pnl / starting_capital) * 100

    async def get_open_positions(self) -> List[Dict[str, Any]]:
        """
        Get all open positions.

        Returns:
            List of open position dictionaries
        """
        return await self.db.get_open_positions(self.portfolio_id)

    async def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get comprehensive portfolio summary."""
        portfolio = await self.db.get_portfolio(self.portfolio_id)
        positions = await self.db.get_open_positions(self.portfolio_id)
        trades = await self.db.get_trade_history(self.portfolio_id, limit=100)
        metrics = await self.db.get_latest_metrics(self.portfolio_id)

        # Calculate current metrics
        total_unrealized = sum(pos['unrealized_pnl'] for pos in positions)
        total_exposure = sum(pos['quantity'] * pos['current_price'] for pos in positions)
        exposure_pct = (total_exposure / portfolio['current_equity']) * 100 if portfolio['current_equity'] > 0 else 0

        # Calculate drawdown
        peak = portfolio['peak_equity']
        current = portfolio['current_equity']
        drawdown_pct = ((peak - current) / peak) * 100 if peak > 0 else 0

        return {
            "portfolio": {
                "name": portfolio['name'],
                "starting_capital": portfolio['starting_capital'],
                "current_equity": portfolio['current_equity'],
                "peak_equity": portfolio['peak_equity'],
                "total_pnl": portfolio['current_equity'] - portfolio['starting_capital'],
                "total_pnl_pct": ((portfolio['current_equity'] - portfolio['starting_capital']) / portfolio['starting_capital']) * 100,
                "execution_mode": portfolio['execution_mode'],
                "circuit_breaker_active": bool(portfolio['circuit_breaker_active'])
            },
            "positions": {
                "count": len(positions),
                "open_positions": positions,
                "total_unrealized_pnl": total_unrealized,
                "total_exposure": total_exposure,
                "exposure_pct": exposure_pct
            },
            "risk": {
                "current_drawdown_pct": drawdown_pct,
                "max_drawdown_limit": portfolio['max_drawdown_pct'],
                "exposure_pct": exposure_pct,
                "max_exposure_limit": portfolio['max_total_exposure_pct']
            },
            "metrics": metrics,
            "recent_trades": trades[:10]
        }
