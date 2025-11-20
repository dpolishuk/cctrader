"""Risk validation for trading signals."""
from typing import Dict, Any
import logging
from .risk_config import RiskConfig

logger = logging.getLogger(__name__)

class RiskValidator:
    """Validates trading signals against portfolio risk limits."""

    def __init__(self, config: RiskConfig, portfolio):
        """
        Initialize risk validator.

        Args:
            config: Risk configuration
            portfolio: Portfolio manager instance
        """
        self.config = config
        self.portfolio = portfolio

    async def validate_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate signal against all risk checks.

        Args:
            signal: Trading signal to validate

        Returns:
            Dict with 'valid' (bool) and 'reason' (str or None)
        """
        # Check 1: Confidence threshold
        confidence = signal.get('confidence', 0)
        if confidence < self.config.min_confidence:
            return {
                'valid': False,
                'reason': f'Confidence {confidence} below threshold {self.config.min_confidence}'
            }

        # Check 2: Position limit
        open_positions = await self.portfolio.count_open_positions()
        if open_positions >= self.config.max_concurrent_positions:
            return {
                'valid': False,
                'reason': f'At maximum {self.config.max_concurrent_positions} positions'
            }

        # Check 3: Exposure limit
        current_exposure = await self.portfolio.calculate_exposure_pct()
        position_size_pct = signal.get('position_size_pct', 0)
        position_size_usd = signal.get('position_size_usd', 0)

        if position_size_usd > 0 and hasattr(self.portfolio, 'total_value'):
            new_exposure_pct = (position_size_usd / self.portfolio.total_value) * 100
        else:
            new_exposure_pct = position_size_pct

        total_exposure = current_exposure + new_exposure_pct

        if total_exposure > self.config.max_total_exposure_pct:
            return {
                'valid': False,
                'reason': f'Exposure would be {total_exposure:.1f}% (max {self.config.max_total_exposure_pct}%)'
            }

        # Check 4: Daily loss limit
        daily_pnl = await self.portfolio.calculate_daily_pnl_pct()
        if daily_pnl <= self.config.daily_loss_limit_pct:
            return {
                'valid': False,
                'reason': f'Daily loss limit hit: {daily_pnl:.2f}%'
            }

        # Check 5: Weekly loss limit
        weekly_pnl = await self.portfolio.calculate_weekly_pnl_pct()
        if weekly_pnl <= self.config.weekly_loss_limit_pct:
            return {
                'valid': False,
                'reason': f'Weekly loss limit hit: {weekly_pnl:.2f}%'
            }

        # Check 6: Correlation limit
        correlation_check = await self._check_correlation_limit(signal)
        if not correlation_check['valid']:
            return correlation_check

        # All checks passed
        return {'valid': True, 'reason': None}

    async def _check_correlation_limit(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Check correlation group limits."""
        symbol = signal.get('symbol', '')

        # Find correlation group for new signal
        new_group = None
        for group, symbols in self.config.correlation_groups.items():
            if any(sym in symbol for sym in symbols):
                new_group = group
                break

        if new_group is None:
            # Uncategorized symbol, allow
            return {'valid': True, 'reason': None}

        # Count existing positions in same group
        open_positions = await self.portfolio.get_open_positions()
        count_in_group = 0

        for position in open_positions:
            pos_symbol = position.get('symbol', '')
            for group, symbols in self.config.correlation_groups.items():
                if group == new_group and any(sym in pos_symbol for sym in symbols):
                    count_in_group += 1
                    break

        if count_in_group >= self.config.max_correlated_positions:
            return {
                'valid': False,
                'reason': f'Already have {count_in_group} positions in {new_group} group (max {self.config.max_correlated_positions})'
            }

        return {'valid': True, 'reason': None}
