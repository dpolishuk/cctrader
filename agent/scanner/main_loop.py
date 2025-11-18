"""Main scanner loop for market movers strategy."""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from .config import ScannerConfig
from .risk_config import RiskConfig
from .symbol_manager import FuturesSymbolManager
from .momentum_scanner import MomentumScanner
from .confidence import ConfidenceCalculator
from .risk_validator import RiskValidator
from .prompts import PromptBuilder

logger = logging.getLogger(__name__)

class MarketMoversScanner:
    """Main market movers scanner orchestrator."""

    def __init__(
        self,
        exchange,
        agent,
        portfolio,
        db,
        config: Optional[ScannerConfig] = None,
        risk_config: Optional[RiskConfig] = None
    ):
        """
        Initialize market movers scanner.

        Args:
            exchange: CCXT exchange instance
            agent: Claude Agent instance
            portfolio: Portfolio manager
            db: Database operations instance
            config: Scanner configuration (optional)
            risk_config: Risk configuration (optional)
        """
        self.exchange = exchange
        self.agent = agent
        self.portfolio = portfolio
        self.db = db

        self.config = config or ScannerConfig()
        self.risk_config = risk_config or RiskConfig()

        # Initialize components
        self.symbol_manager = FuturesSymbolManager(
            exchange,
            min_volume_usd=self.config.min_volume_usd
        )
        self.momentum_scanner = MomentumScanner(
            exchange,
            threshold_pct=self.config.mover_threshold_pct
        )
        self.confidence_calculator = ConfidenceCalculator()
        self.risk_validator = RiskValidator(self.risk_config, portfolio)
        self.prompt_builder = PromptBuilder()

        self.running = False

    async def start(self):
        """Start the scanning loop."""
        logger.info("🚀 Market Movers Scanner starting...")

        # Initialize symbol list
        await self.symbol_manager.refresh_symbols()
        logger.info(f"📊 Monitoring {len(self.symbol_manager.get_symbols())} futures pairs")

        self.running = True

        while self.running:
            try:
                await self.scan_cycle()
            except Exception as e:
                logger.error(f"❌ Error in scan cycle: {e}", exc_info=True)
                await asyncio.sleep(30)

            # Wait until next scan
            await asyncio.sleep(self.config.scan_interval_seconds)

    def stop(self):
        """Stop the scanning loop."""
        logger.info("Stopping scanner...")
        self.running = False

    async def scan_cycle(self):
        """Execute one complete scan cycle."""
        cycle_start = datetime.now()
        logger.info(f"\n{'='*80}")
        logger.info(f"🔍 SCAN CYCLE - {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*80}\n")

        # TODO: Implement full scan cycle
        # This is a placeholder
        await asyncio.sleep(1)

        cycle_duration = (datetime.now() - cycle_start).total_seconds()
        logger.info(f"\n⏱️  Cycle completed in {cycle_duration:.1f}s")
        logger.info(f"{'='*80}\n")

    async def pre_filter_movers(self, movers: Dict[str, List]) -> List[Dict]:
        """
        Pre-filter movers by volume before deep analysis.

        Args:
            movers: Dict with 'gainers' and 'losers' lists

        Returns:
            List of filtered movers
        """
        all_movers = movers['gainers'] + movers['losers']

        # Filter by volume
        filtered = []
        for mover in all_movers:
            ticker = await self.exchange.fetch_ticker(mover['symbol'])
            volume_24h = ticker.get('quoteVolume', 0)

            if volume_24h >= self.config.min_volume_usd:
                mover['volume_24h'] = volume_24h
                filtered.append(mover)

        # Sort by % change and take top N
        filtered.sort(key=lambda x: x['max_change'], reverse=True)
        return filtered[:self.config.max_movers_per_scan]
