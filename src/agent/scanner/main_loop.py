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

        # Metrics tracking
        signals_generated = 0
        trades_executed = 0
        trades_rejected = 0

        # Step 1: Scan for movers
        symbols_list = list(self.symbol_manager.get_symbols().keys())
        movers = await self.momentum_scanner.scan_all_symbols(symbols_list)
        gainers_count = len(movers.get('gainers', []))
        losers_count = len(movers.get('losers', []))
        logger.info(f"📈 Found {gainers_count} gainers, {losers_count} losers")

        # Step 2: Pre-filter (top N by magnitude)
        top_movers = await self.pre_filter_movers(movers)
        logger.info(f"🎯 Analyzing top {len(top_movers)} movers")

        # Step 3: Deep analysis with agent for each mover
        for mover in top_movers:
            try:
                signal = await self._analyze_mover_with_agent(mover)

                if signal is None:
                    # Agent didn't generate a signal (low confidence or error)
                    continue

                signals_generated += 1

                # Step 4: Risk validation
                validation = await self.risk_validator.validate_signal(signal)

                if validation['valid']:
                    # Step 5: Execute trade
                    await self._execute_signal(signal)
                    trades_executed += 1
                else:
                    # Save rejection
                    await self._save_rejection(signal, validation['reason'])
                    trades_rejected += 1

            except Exception as e:
                logger.error(f"❌ Error analyzing {mover.get('symbol')}: {e}", exc_info=True)

        logger.info(f"⚡ Generated {signals_generated} signals (confidence ≥ 60)")
        logger.info(f"✅ Executed {trades_executed} trades, ❌ Rejected {trades_rejected}")

        # Step 6: Save cycle metrics
        await self._save_cycle_metrics(
            cycle_start=cycle_start,
            movers_found=gainers_count + losers_count,
            movers_analyzed=len(top_movers),
            signals_generated=signals_generated,
            trades_executed=trades_executed,
            trades_rejected=trades_rejected
        )

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

    async def _analyze_mover_with_agent(self, mover: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Invoke Claude Agent to analyze a mover.

        Args:
            mover: Mover context (symbol, direction, changes, price, volume)

        Returns:
            Signal dict if confidence >= 60, None otherwise
        """
        logger.info(f"\n🤖 Analyzing {mover['symbol']} ({mover['direction']}) {mover['change_1h']:+.2f}% (1h)")

        # Build portfolio context (await all async calls)
        total_value = self.portfolio.get_total_value()
        if hasattr(total_value, '__await__'):
            total_value = await total_value

        open_positions = self.portfolio.count_open_positions()
        if hasattr(open_positions, '__await__'):
            open_positions = await open_positions

        exposure_pct = self.portfolio.calculate_exposure_pct()
        if hasattr(exposure_pct, '__await__'):
            exposure_pct = await exposure_pct

        portfolio_context = {
            'total_value': total_value,
            'open_positions': open_positions,
            'exposure_pct': exposure_pct
        }

        # Build agent prompt
        prompt = self.prompt_builder.build_analysis_prompt(mover, portfolio_context)

        try:
            # Invoke agent
            response = await self.agent.run(prompt)

            # Extract confidence
            confidence = response.get('confidence', 0)

            if confidence < self.config.min_confidence:
                logger.info(f"❌ Rejected - Confidence: {confidence}/100 (below threshold)")
                # Save low confidence rejection
                await self.db.save_mover_rejection(
                    symbol=mover['symbol'],
                    direction=mover['direction'],
                    confidence=confidence,
                    reason='CONFIDENCE_BELOW_THRESHOLD',
                    details=f"Confidence {confidence} < {self.config.min_confidence}"
                )
                return None

            # Build signal dict
            signal = {
                'symbol': mover['symbol'],
                'direction': mover['direction'],
                'confidence': confidence,
                'entry_price': response.get('entry_price', mover['current_price']),
                'stop_loss': response.get('stop_loss'),
                'tp1': response.get('tp1'),
                'technical_score': response.get('technical_score', 0.0),
                'sentiment_score': response.get('sentiment_score', 0.0),
                'liquidity_score': response.get('liquidity_score', 0.0),
                'correlation_score': response.get('correlation_score', 0.0),
                'analysis': response.get('analysis', ''),
            }

            logger.info(f"✅ Signal generated - Confidence: {confidence}/100")
            return signal

        except Exception as e:
            logger.error(f"❌ Agent analysis failed: {e}", exc_info=True)
            return None

    async def _execute_signal(self, signal: Dict[str, Any]):
        """
        Execute paper trade for approved signal.

        Args:
            signal: Signal dictionary
        """
        logger.info(f"\n🎯 EXECUTING PAPER TRADE")
        logger.info(f"{'─'*80}")
        logger.info(f"Symbol:     {signal['symbol']}")
        logger.info(f"Direction:  {signal['direction']}")
        logger.info(f"Confidence: {signal['confidence']}/100")
        logger.info(f"Entry:      ${signal['entry_price']:.2f}")
        logger.info(f"Stop Loss:  ${signal['stop_loss']:.2f}")
        logger.info(f"TP1:        ${signal['tp1']:.2f}")
        logger.info(f"{'─'*80}\n")

        # Save signal to database first
        signal_id = await self.db.save_mover_signal(
            symbol=signal['symbol'],
            direction=signal['direction'],
            confidence=signal['confidence'],
            entry_price=signal['entry_price'],
            stop_loss=signal['stop_loss'],
            tp1=signal['tp1'],
            technical_score=signal.get('technical_score'),
            sentiment_score=signal.get('sentiment_score'),
            liquidity_score=signal.get('liquidity_score'),
            correlation_score=signal.get('correlation_score'),
            analysis=signal.get('analysis', '')
        )

        # Execute paper trade
        await self.portfolio.execute_paper_trade(
            symbol=signal['symbol'],
            side=signal['direction'],
            entry_price=signal['entry_price'],
            stop_loss=signal['stop_loss'],
            take_profit=signal['tp1'],
            confidence=signal['confidence'],
            signal_id=signal_id
        )

        logger.info(f"✓ Position created (Signal ID: {signal_id})")
        logger.info(f"✓ Monitoring activated\n")

    async def _save_rejection(self, signal: Dict[str, Any], reason: str):
        """
        Save rejected signal to database.

        Args:
            signal: Signal dictionary
            reason: Rejection reason
        """
        logger.info(f"❌ Rejected {signal['symbol']} - {reason}")

        await self.db.save_mover_rejection(
            symbol=signal['symbol'],
            direction=signal['direction'],
            confidence=signal['confidence'],
            reason=reason,
            details=f"Signal failed risk check: {reason}"
        )

    async def _save_cycle_metrics(
        self,
        cycle_start: datetime,
        movers_found: int,
        movers_analyzed: int,
        signals_generated: int,
        trades_executed: int,
        trades_rejected: int
    ):
        """
        Save scan cycle metrics to database.

        Args:
            cycle_start: Cycle start timestamp
            movers_found: Total movers detected
            movers_analyzed: Movers passed to agent
            signals_generated: Signals with confidence >= 60
            trades_executed: Trades that passed risk checks
            trades_rejected: Trades that failed risk checks
        """
        cycle_duration = (datetime.now() - cycle_start).total_seconds()

        # Get portfolio values (handle both sync and async)
        portfolio_value = self.portfolio.get_total_value()
        if hasattr(portfolio_value, '__await__'):
            portfolio_value = await portfolio_value

        open_positions = self.portfolio.count_open_positions()
        if hasattr(open_positions, '__await__'):
            open_positions = await open_positions

        exposure_pct = self.portfolio.calculate_exposure_pct()
        if hasattr(exposure_pct, '__await__'):
            exposure_pct = await exposure_pct

        # Build metrics dict
        metrics = {
            'cycle_duration_seconds': cycle_duration,
            'movers_found': movers_found,
            'signals_generated': signals_generated,
            'signals_executed': trades_executed,
            'signals_rejected': trades_rejected,
            'open_positions': open_positions,
            'total_exposure_pct': exposure_pct,
            'portfolio_value': portfolio_value,
            # These would come from portfolio risk metrics:
            'daily_pnl_pct': 0.0,  # TODO: Get from portfolio
            'weekly_pnl_pct': 0.0,  # TODO: Get from portfolio
            'risk_level': 'LOW'  # TODO: Calculate based on exposure/pnl
        }

        await self.db.save_movers_metrics(metrics)
