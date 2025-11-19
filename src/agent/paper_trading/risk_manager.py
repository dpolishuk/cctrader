"""Risk management system for paper trading."""
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path

from agent.database.paper_operations import PaperTradingDatabase

@dataclass
class RiskLimits:
    """Risk limit configuration."""
    max_position_size_pct: float = 5.0  # % of portfolio
    max_total_exposure_pct: float = 80.0  # % of portfolio
    max_daily_loss_pct: float = 5.0  # % loss from daily starting equity
    max_drawdown_pct: float = 10.0  # % loss from peak equity
    max_violations_per_hour: int = 3  # Circuit breaker trigger

@dataclass
class TradeProposal:
    """Proposed trade for validation."""
    symbol: str
    side: str  # BUY, SELL
    quantity: float
    price: float
    position_type: str  # LONG, SHORT, CLOSE

class RiskManager:
    """
    Multi-layer risk management system.

    Layers:
    1. Pre-trade validation: Block trades violating limits
    2. Continuous monitoring: Alert when approaching limits
    3. Post-trade reconciliation: Log violations for analysis
    4. Circuit breakers: Auto-halt on critical violations
    """

    def __init__(self, db: PaperTradingDatabase, portfolio_id: int):
        self.db = db
        self.portfolio_id = portfolio_id
        self.limits = RiskLimits()  # Will be loaded from portfolio config

    async def initialize(self) -> None:
        """Load risk limits from portfolio configuration."""
        portfolio = await self.db.get_portfolio(self.portfolio_id)
        if portfolio:
            self.limits = RiskLimits(
                max_position_size_pct=portfolio['max_position_size_pct'],
                max_total_exposure_pct=portfolio['max_total_exposure_pct'],
                max_daily_loss_pct=portfolio['max_daily_loss_pct'],
                max_drawdown_pct=portfolio['max_drawdown_pct']
            )

    # Layer 1: Pre-Trade Validation

    async def validate_trade(
        self,
        trade: TradeProposal
    ) -> Tuple[bool, List[str]]:
        """
        Validate trade against all risk limits.

        Returns:
            (is_valid, list_of_violations)
        """
        violations = []

        # Check circuit breaker status first
        portfolio = await self.db.get_portfolio(self.portfolio_id)
        if portfolio['circuit_breaker_active']:
            violations.append(
                "CIRCUIT BREAKER ACTIVE - All trading halted pending manual reset"
            )
            await self._log_risk_event(
                "PRE_TRADE_BLOCK",
                "CRITICAL",
                "CIRCUIT_BREAKER",
                0, 1,
                trade.symbol,
                "Trade blocked by active circuit breaker"
            )
            return False, violations

        # Skip validations for closing trades
        if trade.position_type == "CLOSE":
            return True, []

        # 1. Position size limit
        position_size_valid, pos_violation = await self._check_position_size(trade)
        if not position_size_valid:
            violations.append(pos_violation)

        # 2. Total exposure limit
        exposure_valid, exp_violation = await self._check_total_exposure(trade)
        if not exposure_valid:
            violations.append(exp_violation)

        # 3. Daily loss limit
        daily_loss_valid, daily_violation = await self._check_daily_loss()
        if not daily_loss_valid:
            violations.append(daily_violation)

        # 4. Drawdown limit
        drawdown_valid, dd_violation = await self._check_drawdown()
        if not drawdown_valid:
            violations.append(dd_violation)

        # Log pre-trade blocks
        if violations:
            for violation in violations:
                await self._log_risk_event(
                    "PRE_TRADE_BLOCK",
                    "CRITICAL",
                    "MULTIPLE" if len(violations) > 1 else "POSITION_SIZE",
                    0, 0,
                    trade.symbol,
                    violation
                )

        return len(violations) == 0, violations

    async def _check_position_size(
        self,
        trade: TradeProposal
    ) -> Tuple[bool, Optional[str]]:
        """Check if position size is within limits."""
        portfolio = await self.db.get_portfolio(self.portfolio_id)
        max_position_value = portfolio['current_equity'] * (self.limits.max_position_size_pct / 100)

        proposed_position_value = trade.quantity * trade.price

        if proposed_position_value > max_position_value:
            return False, (
                f"Position size ${proposed_position_value:.2f} exceeds limit "
                f"${max_position_value:.2f} ({self.limits.max_position_size_pct}% of portfolio)"
            )

        return True, None

    async def _check_total_exposure(
        self,
        trade: TradeProposal
    ) -> Tuple[bool, Optional[str]]:
        """Check total portfolio exposure."""
        portfolio = await self.db.get_portfolio(self.portfolio_id)
        positions = await self.db.get_open_positions(self.portfolio_id)

        # Calculate current exposure
        current_exposure = sum(
            pos['quantity'] * pos['current_price']
            for pos in positions
        )

        # Add proposed trade exposure
        new_exposure = current_exposure + (trade.quantity * trade.price)
        max_exposure = portfolio['current_equity'] * (self.limits.max_total_exposure_pct / 100)

        exposure_pct = (new_exposure / portfolio['current_equity']) * 100

        if new_exposure > max_exposure:
            return False, (
                f"Total exposure {exposure_pct:.1f}% exceeds limit "
                f"{self.limits.max_total_exposure_pct}%"
            )

        return True, None

    async def _check_daily_loss(self) -> Tuple[bool, Optional[str]]:
        """Check if daily loss limit exceeded."""
        portfolio = await self.db.get_portfolio(self.portfolio_id)

        # Get equity at start of day (from performance metrics or first trade)
        # For simplicity, using starting capital as baseline
        # In production, would track daily starting equity
        starting_equity = portfolio['starting_capital']
        current_equity = portfolio['current_equity']

        daily_loss_pct = ((starting_equity - current_equity) / starting_equity) * 100

        if daily_loss_pct > self.limits.max_daily_loss_pct:
            return False, (
                f"Daily loss {daily_loss_pct:.2f}% exceeds limit "
                f"{self.limits.max_daily_loss_pct}%"
            )

        return True, None

    async def _check_drawdown(self) -> Tuple[bool, Optional[str]]:
        """Check if drawdown limit exceeded."""
        portfolio = await self.db.get_portfolio(self.portfolio_id)

        peak_equity = portfolio['peak_equity']
        current_equity = portfolio['current_equity']

        drawdown_pct = ((peak_equity - current_equity) / peak_equity) * 100

        if drawdown_pct > self.limits.max_drawdown_pct:
            return False, (
                f"Drawdown {drawdown_pct:.2f}% exceeds limit "
                f"{self.limits.max_drawdown_pct}%"
            )

        return True, None

    # Layer 2: Continuous Monitoring

    async def monitor_positions(self) -> List[Dict[str, Any]]:
        """
        Monitor all open positions and generate warnings.

        Returns list of warnings/alerts.
        """
        alerts = []
        portfolio = await self.db.get_portfolio(self.portfolio_id)
        positions = await self.db.get_open_positions(self.portfolio_id)

        # Check each position
        for pos in positions:
            # Stop loss check
            if pos['stop_loss']:
                if pos['position_type'] == 'LONG' and pos['current_price'] <= pos['stop_loss']:
                    alerts.append({
                        "type": "STOP_LOSS_HIT",
                        "severity": "WARNING",
                        "symbol": pos['symbol'],
                        "message": f"Stop loss hit for {pos['symbol']} at ${pos['current_price']}"
                    })

            # Take profit check
            if pos['take_profit']:
                if pos['position_type'] == 'LONG' and pos['current_price'] >= pos['take_profit']:
                    alerts.append({
                        "type": "TAKE_PROFIT_HIT",
                        "severity": "INFO",
                        "symbol": pos['symbol'],
                        "message": f"Take profit hit for {pos['symbol']} at ${pos['current_price']}"
                    })

        # Check portfolio-level metrics
        total_exposure = sum(p['quantity'] * p['current_price'] for p in positions)
        exposure_pct = (total_exposure / portfolio['current_equity']) * 100

        # Warning at 80% of limit
        warning_threshold = self.limits.max_total_exposure_pct * 0.8
        if exposure_pct > warning_threshold:
            alerts.append({
                "type": "EXPOSURE_WARNING",
                "severity": "WARNING",
                "message": f"Total exposure {exposure_pct:.1f}% approaching limit {self.limits.max_total_exposure_pct}%"
            })

            await self._log_risk_event(
                "LIMIT_WARNING",
                "WARNING",
                "EXPOSURE",
                self.limits.max_total_exposure_pct,
                exposure_pct,
                None,
                f"Exposure at {exposure_pct:.1f}%"
            )

        # Drawdown warning
        peak_equity = portfolio['peak_equity']
        current_equity = portfolio['current_equity']
        drawdown_pct = ((peak_equity - current_equity) / peak_equity) * 100

        dd_warning_threshold = self.limits.max_drawdown_pct * 0.8
        if drawdown_pct > dd_warning_threshold:
            alerts.append({
                "type": "DRAWDOWN_WARNING",
                "severity": "WARNING",
                "message": f"Drawdown {drawdown_pct:.2f}% approaching limit {self.limits.max_drawdown_pct}%"
            })

            await self._log_risk_event(
                "LIMIT_WARNING",
                "WARNING",
                "DRAWDOWN",
                self.limits.max_drawdown_pct,
                drawdown_pct,
                None,
                f"Drawdown at {drawdown_pct:.2f}%"
            )

        return alerts

    # Layer 3: Post-Trade Reconciliation

    async def reconcile_trade(
        self,
        trade_id: int,
        execution_result: Dict[str, Any]
    ) -> None:
        """Log trade execution quality and any violations."""
        # Log excessive slippage
        slippage = execution_result.get('slippage_pct', 0)
        if slippage > 0.5:  # > 0.5% slippage
            await self._log_risk_event(
                "POST_TRADE_VIOLATION",
                "WARNING",
                "SLIPPAGE",
                0.5,
                slippage,
                None,
                trade_id,
                f"High slippage: {slippage:.2f}%"
            )

    # Layer 4: Circuit Breakers

    async def check_circuit_breakers(self) -> Tuple[bool, Optional[str]]:
        """
        Check if circuit breaker should be triggered.

        Returns:
            (should_trigger, reason)
        """
        portfolio = await self.db.get_portfolio(self.portfolio_id)

        # 1. Check drawdown circuit breaker
        peak_equity = portfolio['peak_equity']
        current_equity = portfolio['current_equity']
        drawdown_pct = ((peak_equity - current_equity) / peak_equity) * 100

        if drawdown_pct >= self.limits.max_drawdown_pct:
            reason = f"Drawdown {drawdown_pct:.2f}% hit limit {self.limits.max_drawdown_pct}%"
            await self._trigger_circuit_breaker(reason)
            return True, reason

        # 2. Check daily loss circuit breaker
        starting_equity = portfolio['starting_capital']
        daily_loss_pct = ((starting_equity - current_equity) / starting_equity) * 100

        if daily_loss_pct >= self.limits.max_daily_loss_pct:
            reason = f"Daily loss {daily_loss_pct:.2f}% hit limit {self.limits.max_daily_loss_pct}%"
            await self._trigger_circuit_breaker(reason)
            return True, reason

        # 3. Check violation frequency
        violations = await self.db.get_risk_violations(
            self.portfolio_id,
            hours=1,
            severity="CRITICAL"
        )

        if len(violations) >= self.limits.max_violations_per_hour:
            reason = f"Too many violations: {len(violations)} in past hour"
            await self._trigger_circuit_breaker(reason)
            return True, reason

        return False, None

    async def _trigger_circuit_breaker(self, reason: str) -> None:
        """Activate circuit breaker and halt all trading."""
        await self.db.set_circuit_breaker(self.portfolio_id, True)

        await self._log_risk_event(
            "CIRCUIT_BREAKER",
            "CRITICAL",
            "AUTO_HALT",
            0, 0,
            None,
            None,
            f"Circuit breaker triggered: {reason}"
        )

    async def reset_circuit_breaker(self) -> None:
        """Manually reset circuit breaker (requires user action)."""
        await self.db.set_circuit_breaker(self.portfolio_id, False)

        await self._log_risk_event(
            "CIRCUIT_BREAKER",
            "INFO",
            "MANUAL_RESET",
            0, 0,
            None,
            None,
            "Circuit breaker manually reset"
        )

    # Helper Methods

    async def _log_risk_event(
        self,
        event_type: str,
        severity: str,
        rule_type: str,
        rule_limit: float,
        current_value: float,
        symbol: Optional[str],
        trade_id: Optional[int] = None,
        message: Optional[str] = None
    ) -> None:
        """Log risk event to audit trail."""
        await self.db.log_risk_event(
            self.portfolio_id,
            event_type,
            severity,
            rule_type,
            rule_limit,
            current_value,
            symbol,
            trade_id,
            message
        )
