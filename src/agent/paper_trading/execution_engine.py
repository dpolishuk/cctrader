"""Trade execution simulator for paper trading."""
import asyncio
import random
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from enum import Enum

class ExecutionMode(Enum):
    INSTANT = "instant"
    REALISTIC = "realistic"
    HISTORICAL = "historical"

class ExecutionEngine:
    """Simulates trade execution with configurable realism."""

    def __init__(self, mode: str = "realistic"):
        self.mode = ExecutionMode(mode)

    async def execute_trade(
        self,
        symbol: str,
        order_type: str,  # MARKET, LIMIT
        side: str,  # BUY, SELL
        quantity: float,
        signal_price: float,
        current_market_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Execute a simulated trade.

        Returns:
            Dict containing:
            - filled_price: Actual fill price
            - filled_quantity: Actual quantity filled
            - slippage_pct: Slippage percentage
            - execution_time_ms: Simulated execution time
            - partial_fill: Whether partially filled
            - fill_percentage: Percentage of order filled
        """
        signal_time = datetime.now()

        if self.mode == ExecutionMode.INSTANT:
            return await self._instant_execution(
                signal_price, quantity, signal_time
            )
        elif self.mode == ExecutionMode.REALISTIC:
            return await self._realistic_execution(
                symbol, side, signal_price, quantity,
                current_market_data, signal_time
            )
        else:  # HISTORICAL
            return await self._historical_execution(
                symbol, side, signal_price, quantity,
                current_market_data, signal_time
            )

    async def _instant_execution(
        self,
        signal_price: float,
        quantity: float,
        signal_time: datetime
    ) -> Dict[str, Any]:
        """Instant fill at signal price with no slippage."""
        execution_time = datetime.now()
        lag_ms = int((execution_time - signal_time).total_seconds() * 1000)

        return {
            "filled_price": signal_price,
            "filled_quantity": quantity,
            "slippage_pct": 0.0,
            "execution_time_ms": lag_ms,
            "partial_fill": False,
            "fill_percentage": 100.0,
            "execution_started_at": signal_time,
            "execution_completed_at": execution_time
        }

    async def _realistic_execution(
        self,
        symbol: str,
        side: str,
        signal_price: float,
        quantity: float,
        market_data: Optional[Dict],
        signal_time: datetime
    ) -> Dict[str, Any]:
        """
        Realistic execution with:
        - Bid-ask spread simulation
        - Market impact slippage
        - Variable execution time
        - Potential partial fills
        """
        # Simulate processing delay (50-200ms)
        execution_delay_ms = random.randint(50, 200)
        await asyncio.sleep(execution_delay_ms / 1000.0)

        execution_started = datetime.now()

        # Simulate bid-ask spread (0.02-0.05% for crypto)
        spread_pct = random.uniform(0.02, 0.05) / 100

        # Base slippage from spread
        base_slippage = spread_pct / 2  # Half spread

        # Market impact based on order size (simplified)
        # Larger orders have more impact
        # Assume typical market depth, scale slippage with quantity
        market_impact = min((quantity / 100) * 0.001, 0.002)  # Cap at 0.2%

        # Volatility factor from market data
        volatility_factor = 0.0
        if market_data and 'volatility' in market_data:
            # Higher volatility = more slippage
            volatility_factor = market_data['volatility'] * 0.0005

        # Total slippage
        total_slippage_pct = (base_slippage + market_impact + volatility_factor) * 100

        # Determine fill price based on side
        if side == "BUY":
            # Buying = pay ask (higher price)
            slippage_multiplier = 1 + (total_slippage_pct / 100)
        else:  # SELL
            # Selling = receive bid (lower price)
            slippage_multiplier = 1 - (total_slippage_pct / 100)

        filled_price = signal_price * slippage_multiplier

        # Simulate partial fills (5% chance for large orders)
        partial_fill = False
        fill_percentage = 100.0
        filled_quantity = quantity

        if quantity > 10 and random.random() < 0.05:
            partial_fill = True
            fill_percentage = random.uniform(80, 95)
            filled_quantity = quantity * (fill_percentage / 100)

        execution_completed = datetime.now()
        total_lag_ms = int((execution_completed - signal_time).total_seconds() * 1000)

        return {
            "filled_price": round(filled_price, 2),
            "filled_quantity": round(filled_quantity, 8),
            "slippage_pct": round(total_slippage_pct, 4),
            "execution_time_ms": total_lag_ms,
            "partial_fill": partial_fill,
            "fill_percentage": round(fill_percentage, 2),
            "execution_started_at": execution_started,
            "execution_completed_at": execution_completed,
            "spread_pct": round(spread_pct * 100, 4),
            "market_impact_pct": round(market_impact * 100, 4),
            "volatility_impact_pct": round(volatility_factor * 100, 4)
        }

    async def _historical_execution(
        self,
        symbol: str,
        side: str,
        signal_price: float,
        quantity: float,
        market_data: Optional[Dict],
        signal_time: datetime
    ) -> Dict[str, Any]:
        """
        Historical execution using actual OHLCV data.

        Uses high/low of the candle following signal to determine
        realistic fill price based on order type.
        """
        # Simulate delay
        execution_delay_ms = random.randint(100, 500)
        await asyncio.sleep(execution_delay_ms / 1000.0)

        execution_started = datetime.now()

        if not market_data or 'high' not in market_data or 'low' not in market_data:
            # Fallback to realistic mode if no market data
            return await self._realistic_execution(
                symbol, side, signal_price, quantity, market_data, signal_time
            )

        # Use actual high/low from next candle
        high = market_data['high']
        low = market_data['low']
        close = market_data.get('close', signal_price)

        # Determine fill price based on order side and market movement
        if side == "BUY":
            # For buy orders, likely filled somewhere between signal and high
            # Use weighted average favoring worse fills (more realistic)
            fill_range = high - signal_price
            fill_price = signal_price + (fill_range * random.uniform(0.3, 0.7))
            fill_price = min(fill_price, high)  # Cap at high
        else:  # SELL
            # For sell orders, likely filled between signal and low
            fill_range = signal_price - low
            fill_price = signal_price - (fill_range * random.uniform(0.3, 0.7))
            fill_price = max(fill_price, low)  # Floor at low

        # Calculate slippage
        slippage_pct = abs((fill_price - signal_price) / signal_price) * 100

        # Partial fills rare in historical mode
        partial_fill = False
        fill_percentage = 100.0
        filled_quantity = quantity

        execution_completed = datetime.now()
        total_lag_ms = int((execution_completed - signal_time).total_seconds() * 1000)

        return {
            "filled_price": round(fill_price, 2),
            "filled_quantity": round(filled_quantity, 8),
            "slippage_pct": round(slippage_pct, 4),
            "execution_time_ms": total_lag_ms,
            "partial_fill": partial_fill,
            "fill_percentage": round(fill_percentage, 2),
            "execution_started_at": execution_started,
            "execution_completed_at": execution_completed,
            "candle_high": high,
            "candle_low": low,
            "candle_close": close
        }

    def calculate_slippage(
        self,
        signal_price: float,
        filled_price: float
    ) -> float:
        """Calculate slippage percentage."""
        return abs((filled_price - signal_price) / signal_price) * 100
