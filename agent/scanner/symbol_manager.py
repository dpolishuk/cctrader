"""Futures symbol manager for market scanning."""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class FuturesSymbolManager:
    """Manages list of tradeable Bybit USDT perpetual futures."""

    def __init__(self, exchange, min_volume_usd: float = 5_000_000):
        """
        Initialize symbol manager.

        Args:
            exchange: CCXT exchange instance
            min_volume_usd: Minimum 24h volume filter
        """
        self.exchange = exchange
        self.min_volume_usd = min_volume_usd
        self.symbols: Dict[str, Any] = {}
        self.last_refresh: Optional[datetime] = None

    async def refresh_symbols(self) -> Dict[str, Any]:
        """
        Fetch and filter tradeable USDT perpetual futures.

        Returns:
            Dict of symbol -> market info
        """
        logger.info("Refreshing futures symbols list...")

        # Load all markets
        markets = await self.exchange.load_markets()

        # Filter for USDT perpetual futures
        usdt_futures = {
            symbol: market
            for symbol, market in markets.items()
            if market.get('type') == 'swap'
            and market.get('quote') == 'USDT'
            and market.get('info', {}).get('quoteCoin') == 'USDT'
        }

        logger.info(f"Found {len(usdt_futures)} USDT perpetual futures")

        # Fetch tickers for volume filtering
        symbols_list = list(usdt_futures.keys())
        tickers = await self.exchange.fetch_tickers(symbols_list)

        # Filter by volume
        self.symbols = {
            symbol: market
            for symbol, market in usdt_futures.items()
            if symbol in tickers
            and tickers[symbol].get('quoteVolume', 0) >= self.min_volume_usd
        }

        self.last_refresh = datetime.now()
        logger.info(f"Filtered to {len(self.symbols)} symbols with ≥${self.min_volume_usd:,.0f} volume")

        return self.symbols

    def get_symbols(self) -> Dict[str, Any]:
        """
        Get cached symbols without refresh.

        Returns:
            Dict of symbol -> market info
        """
        return self.symbols

    def should_refresh(self, refresh_interval_minutes: int = 60) -> bool:
        """
        Check if symbols should be refreshed.

        Args:
            refresh_interval_minutes: Refresh interval in minutes

        Returns:
            True if refresh needed
        """
        if self.last_refresh is None:
            return True

        elapsed = datetime.now() - self.last_refresh
        return elapsed > timedelta(minutes=refresh_interval_minutes)
