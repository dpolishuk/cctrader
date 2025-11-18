"""Momentum scanner for detecting market movers."""
from typing import Dict, List, Optional, Any
import asyncio
import logging

logger = logging.getLogger(__name__)

class MomentumScanner:
    """Scans symbols for momentum exceeding threshold."""

    def __init__(self, exchange, threshold_pct: float = 5.0, batch_size: int = 10):
        """
        Initialize momentum scanner.

        Args:
            exchange: CCXT exchange instance
            threshold_pct: Minimum % change to qualify as mover
            batch_size: Number of symbols to fetch in parallel
        """
        self.exchange = exchange
        self.threshold_pct = threshold_pct
        self.batch_size = batch_size

    async def scan_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Scan single symbol for momentum.

        Args:
            symbol: Trading pair symbol

        Returns:
            Mover data if exceeds threshold, None otherwise
        """
        try:
            # Fetch 1h and 4h data (last 2 candles)
            ohlcv_1h = await self.exchange.fetch_ohlcv(symbol, '1h', limit=2)
            ohlcv_4h = await self.exchange.fetch_ohlcv(symbol, '4h', limit=2)

            # Calculate % changes
            change_1h = ((ohlcv_1h[-1][4] - ohlcv_1h[-2][4]) / ohlcv_1h[-2][4]) * 100
            change_4h = ((ohlcv_4h[-1][4] - ohlcv_4h[-2][4]) / ohlcv_4h[-2][4]) * 100

            # Get max absolute change
            max_change = max(abs(change_1h), abs(change_4h))

            # Check threshold
            if max_change >= self.threshold_pct:
                return {
                    'symbol': symbol,
                    'change_1h': change_1h,
                    'change_4h': change_4h,
                    'max_change': max_change,
                    'direction': 'LONG' if change_1h > 0 else 'SHORT',
                    'current_price': ohlcv_1h[-1][4],
                }

            return None

        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")
            return None

    async def scan_all_symbols(self, symbols: List[str]) -> Dict[str, List[Dict]]:
        """
        Scan all symbols for movers.

        Args:
            symbols: List of symbols to scan

        Returns:
            Dict with 'gainers' and 'losers' lists
        """
        movers = {'gainers': [], 'losers': []}

        # Process in batches
        for i in range(0, len(symbols), self.batch_size):
            batch = symbols[i:i+self.batch_size]

            # Scan batch in parallel
            tasks = [self.scan_symbol(symbol) for symbol in batch]
            results = await asyncio.gather(*tasks)

            # Categorize movers
            for result in results:
                if result is not None:
                    if result['direction'] == 'LONG':
                        movers['gainers'].append(result)
                    else:
                        movers['losers'].append(result)

        # Sort by magnitude
        movers['gainers'].sort(key=lambda x: x['max_change'], reverse=True)
        movers['losers'].sort(key=lambda x: x['max_change'], reverse=True)

        logger.info(f"Found {len(movers['gainers'])} gainers, {len(movers['losers'])} losers")

        return movers
