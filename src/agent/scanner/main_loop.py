"""Main scanner loop for market movers strategy."""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .config import ScannerConfig
from .risk_config import RiskConfig
from .symbol_manager import FuturesSymbolManager
from .momentum_scanner import MomentumScanner
from .confidence import ConfidenceCalculator
from .risk_validator import RiskValidator
from .prompts import PromptBuilder
from .dashboard import ScannerEvent

logger = logging.getLogger(__name__)
console = Console()

# Type alias for event callback
EventCallback = Callable[[str, Dict[str, Any]], None]

class MarketMoversScanner:
    """Main market movers scanner orchestrator."""

    def __init__(
        self,
        exchange,
        agent,
        portfolio,
        db,
        config: Optional[ScannerConfig] = None,
        risk_config: Optional[RiskConfig] = None,
        daily_mode: bool = False,
        event_callback: Optional[EventCallback] = None
    ):
        """
        Initialize market movers scanner.

        Args:
            exchange: CCXT exchange instance
            agent: Claude Agent instance (AgentWrapper)
            portfolio: Portfolio manager
            db: Database operations instance
            config: Scanner configuration (optional)
            risk_config: Risk configuration (optional)
            daily_mode: If True, maintain single session per day (optional)
            event_callback: Optional callback for dashboard events
        """
        self.exchange = exchange
        self.agent = agent
        self.portfolio = portfolio
        self.db = db
        self.daily_mode = daily_mode
        self.event_callback = event_callback

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
        self.cycle_number = 0

    def _emit_event(self, event_type: str, **kwargs) -> None:
        """
        Emit an event to the dashboard callback.

        Args:
            event_type: Type of event (from ScannerEvent).
            **kwargs: Event-specific data.
        """
        if self.event_callback:
            try:
                self.event_callback(event_type, kwargs)
            except Exception as e:
                logger.warning(f"Event callback error: {e}")

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

    async def stop(self):
        """Stop the scanning loop."""
        logger.info("Stopping scanner...")
        self.running = False

        # Clean up agent persistent client if in daily mode
        if self.daily_mode and hasattr(self.agent, 'cleanup'):
            await self.agent.cleanup()

    async def display_portfolio_status(self):
        """Display portfolio status with P&L and open positions."""
        try:
            summary = await self.portfolio.get_portfolio_summary()
            portfolio = summary["portfolio"]
            positions_data = summary["positions"]
            risk = summary["risk"]

            # Format P&L with color
            pnl = portfolio["total_pnl"]
            pnl_pct = portfolio["total_pnl_pct"]
            pnl_color = "green" if pnl >= 0 else "red"
            pnl_sign = "+" if pnl >= 0 else ""

            # Build header line
            header = (
                f"[bold]💰 Portfolio:[/bold] "
                f"[cyan]${portfolio['current_equity']:,.2f}[/cyan] "
                f"[{pnl_color}]({pnl_sign}{pnl_pct:.2f}% P&L)[/{pnl_color}] | "
                f"[yellow]{positions_data['count']} positions[/yellow] | "
                f"[magenta]{positions_data['exposure_pct']:.1f}% exposure[/magenta]"
            )

            console.print(header)

            # Show open positions if any
            if positions_data["open_positions"]:
                positions_line = "   "
                for pos in positions_data["open_positions"]:
                    symbol = pos["symbol"].replace("/", "").replace(":USDT", "")
                    direction = "LONG" if pos["position_type"] == "long" else "SHORT"
                    unrealized = pos.get("unrealized_pnl", 0)
                    entry = pos.get("entry_price", 0)
                    current = pos.get("current_price", entry)

                    # Calculate P&L percentage
                    if entry > 0:
                        if direction == "LONG":
                            pnl_pct_pos = ((current - entry) / entry) * 100
                        else:
                            pnl_pct_pos = ((entry - current) / entry) * 100
                    else:
                        pnl_pct_pos = 0

                    pos_color = "green" if pnl_pct_pos >= 0 else "red"
                    pos_sign = "+" if pnl_pct_pos >= 0 else ""

                    positions_line += f"[{pos_color}]{symbol}: {direction} {pos_sign}{pnl_pct_pos:.1f}%[/{pos_color}] | "

                # Remove trailing separator
                positions_line = positions_line.rstrip(" | ")
                console.print(positions_line)

            # Show risk warning if needed
            if risk["current_drawdown_pct"] > 5:
                console.print(f"   [red]⚠️  Drawdown: {risk['current_drawdown_pct']:.1f}%[/red]")

            console.print()  # Empty line after portfolio status

        except Exception as e:
            logger.warning(f"Could not display portfolio status: {e}")

    async def scan_cycle(self):
        """Execute one complete scan cycle."""
        cycle_start = datetime.now()
        self.cycle_number += 1
        logger.info(f"\n{'='*80}")
        logger.info(f"🔍 SCAN CYCLE #{self.cycle_number} - {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*80}")

        # Display portfolio status with P&L before scanning
        await self.display_portfolio_status()

        # Metrics tracking
        signals_generated = 0
        trades_executed = 0
        trades_rejected = 0

        # Track sentiment findings per symbol for summary
        sentiment_summary = {}

        # Step 1: Scan for movers
        symbols_list = list(self.symbol_manager.get_symbols().keys())
        movers = await self.momentum_scanner.scan_all_symbols(symbols_list)
        gainers_count = len(movers.get('gainers', []))
        losers_count = len(movers.get('losers', []))
        logger.info(f"📈 Found {gainers_count} gainers, {losers_count} losers")

        # Step 2: Pre-filter (top N by magnitude)
        top_movers = await self.pre_filter_movers(movers)
        logger.info(f"🎯 Analyzing top {len(top_movers)} movers")

        # Emit cycle start event with movers data
        movers_data = [
            {
                "symbol": m["symbol"],
                "change_pct": m.get("max_change", m.get("change_1h", 0)),
                "direction": m.get("direction", "gainer"),
            }
            for m in top_movers
        ]
        self._emit_event(
            ScannerEvent.CYCLE_START,
            cycle_number=self.cycle_number,
            movers=movers_data,
        )

        # Step 3: Deep analysis with agent for each mover
        for mover in top_movers:
            symbol = mover.get('symbol', 'UNKNOWN')
            try:
                # Emit mover start event
                self._emit_event(ScannerEvent.MOVER_START, symbol=symbol)

                signal, sentiment_findings, analysis_data = await self._analyze_mover_with_agent(mover)

                # Store sentiment findings for summary
                if sentiment_findings:
                    sentiment_summary[symbol] = sentiment_findings

                # Extract key findings for dashboard display (top 3)
                key_findings = []
                if sentiment_findings:
                    for finding in sentiment_findings:
                        if isinstance(finding, dict) and 'key_findings' in finding:
                            key_findings = finding['key_findings'][:3]
                            break
                        elif isinstance(finding, dict) and 'bullet_points' in finding:
                            key_findings = finding['bullet_points'][:3]
                            break

                if signal is None:
                    # Agent didn't generate a signal (low confidence or error)
                    self._emit_event(
                        ScannerEvent.MOVER_COMPLETE,
                        symbol=symbol,
                        result="NO_TRADE",
                        confidence=analysis_data.get('confidence'),
                        score_breakdown=analysis_data.get('score_breakdown'),
                        weak_components=analysis_data.get('weak_components'),
                        sentiment_findings=key_findings,
                    )
                    continue

                signals_generated += 1

                # Emit signal generated event
                self._emit_event(
                    ScannerEvent.SIGNAL_GENERATED,
                    symbol=symbol,
                    confidence=signal.get('confidence'),
                    entry_price=signal.get('entry_price'),
                )

                # Step 4: Risk validation
                self._emit_event(ScannerEvent.RISK_CHECK, symbol=symbol)
                validation = await self.risk_validator.validate_signal(signal)

                if validation['valid']:
                    # Step 5: Execute trade
                    self._emit_event(ScannerEvent.EXECUTION, symbol=symbol)
                    await self._execute_signal(signal)
                    trades_executed += 1
                    self._emit_event(
                        ScannerEvent.MOVER_COMPLETE,
                        symbol=symbol,
                        result="EXECUTED",
                        confidence=signal.get('confidence'),
                        entry_price=signal.get('entry_price'),
                        score_breakdown=analysis_data.get('score_breakdown'),
                        sentiment_findings=key_findings,
                    )
                else:
                    # Save rejection
                    await self._save_rejection(signal, validation['reason'])
                    trades_rejected += 1
                    self._emit_event(
                        ScannerEvent.MOVER_COMPLETE,
                        symbol=symbol,
                        result="REJECTED",
                        confidence=signal.get('confidence'),
                        score_breakdown=analysis_data.get('score_breakdown'),
                        weak_components=analysis_data.get('weak_components'),
                        sentiment_findings=key_findings,
                    )

            except Exception as e:
                logger.error(f"❌ Error analyzing {symbol}: {e}", exc_info=True)
                self._emit_event(
                    ScannerEvent.MOVER_COMPLETE,
                    symbol=symbol,
                    result="ERROR",
                )

        logger.info(f"⚡ Generated {signals_generated} signals (confidence ≥ 60)")
        logger.info(f"✅ Executed {trades_executed} trades, ❌ Rejected {trades_rejected}")

        # Display sentiment analysis summary
        if sentiment_summary:
            logger.info(f"\n{'='*80}")
            logger.info("📰 SENTIMENT ANALYSIS SUMMARY")
            logger.info(f"{'='*80}")

            for symbol, findings in sentiment_summary.items():
                logger.info(f"\n{symbol}:")

                # findings is a list, process the most recent/relevant one
                if findings and len(findings) > 0:
                    finding = findings[0]  # Use first/most relevant finding

                    if not finding.get('success') and finding.get('warnings'):
                        logger.warning(f"  ⚠️  Web search failed - sentiment score defaulted")
                    elif not finding.get('web_results') or not finding.get('bullet_points'):
                        logger.info("  • No significant news found")
                    else:
                        for point in finding.get('bullet_points', []):
                            logger.info(f"  {point}")

            logger.info(f"\n{'='*80}\n")

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

        # Emit cycle complete event
        self._emit_event(
            ScannerEvent.CYCLE_COMPLETE,
            cycle_number=self.cycle_number,
            signals_generated=signals_generated,
            trades_executed=trades_executed,
            trades_rejected=trades_rejected,
            duration_seconds=cycle_duration,
        )

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

    async def _analyze_mover_with_agent(
        self, mover: Dict[str, Any]
    ) -> tuple[Optional[Dict[str, Any]], list, Dict[str, Any]]:
        """
        Invoke Claude Agent to analyze a mover.

        Args:
            mover: Mover context (symbol, direction, changes, price, volume)

        Returns:
            Tuple of:
            - Signal dict if confidence >= 60, else None
            - sentiment_findings list (key findings from news)
            - analysis_data dict with score breakdown (always returned)
        """
        symbol = mover['symbol']
        logger.info(f"\n🤖 Analyzing {symbol} ({mover['direction']}) {mover['change_1h']:+.2f}% (1h)")

        # Emit analysis phase event
        self._emit_event(ScannerEvent.ANALYSIS_PHASE, symbol=symbol, phase="technical")

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
            # Emit sentiment phase before agent (agent will do both technical and sentiment)
            self._emit_event(ScannerEvent.ANALYSIS_PHASE, symbol=symbol, phase="sentiment")

            # Invoke agent
            response = await self.agent.run(prompt, symbol=symbol)

            # Get sentiment findings from agent
            sentiment_findings = self.agent.get_sentiment_findings() if hasattr(self.agent, 'get_sentiment_findings') else []

            # Extract confidence and scores
            confidence = response.get('confidence', 0)
            technical_score = response.get('technical_score', 0.0)
            sentiment_score = response.get('sentiment_score', 0.0)
            liquidity_score = response.get('liquidity_score', 0.0)
            correlation_score = response.get('correlation_score', 0.0)

            # Build analysis data (always returned for transparency)
            analysis_data = {
                'confidence': confidence,
                'score_breakdown': {
                    'technical': technical_score,
                    'sentiment': sentiment_score,
                    'liquidity': liquidity_score,
                    'correlation': correlation_score,
                },
                'weak_components': self._get_weak_components(
                    technical_score, sentiment_score, liquidity_score, correlation_score
                ),
            }

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
                return None, sentiment_findings, analysis_data

            # Build signal dict with price fallbacks
            # Use current_price if entry_price is 0 or missing
            entry_price = response.get('entry_price') or 0
            if entry_price <= 0:
                entry_price = mover['current_price']
                logger.info(f"Using current price as entry: ${entry_price:.2f}")

            # Calculate stop_loss/tp1 fallbacks based on direction
            # Default: 2% stop loss, 3% take profit
            is_long = mover['direction'] == 'gainer'
            stop_loss = response.get('stop_loss') or 0
            tp1 = response.get('tp1') or 0

            if stop_loss <= 0:
                if is_long:
                    stop_loss = entry_price * 0.98  # 2% below for long
                else:
                    stop_loss = entry_price * 1.02  # 2% above for short
                logger.info(f"Calculated stop_loss: ${stop_loss:.2f}")

            if tp1 <= 0:
                if is_long:
                    tp1 = entry_price * 1.03  # 3% above for long
                else:
                    tp1 = entry_price * 0.97  # 3% below for short
                logger.info(f"Calculated tp1: ${tp1:.2f}")

            signal = {
                'symbol': mover['symbol'],
                'direction': mover['direction'],
                'confidence': confidence,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'tp1': tp1,
                'technical_score': technical_score,
                'sentiment_score': sentiment_score,
                'liquidity_score': liquidity_score,
                'correlation_score': correlation_score,
                'analysis': response.get('analysis', ''),
            }

            logger.info(f"✅ Signal generated - Confidence: {confidence}/100")
            return signal, sentiment_findings, analysis_data

        except Exception as e:
            logger.error(f"❌ Agent analysis failed: {e}", exc_info=True)
            return None, [], {}

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

        # Calculate position sizing
        portfolio_value = self.portfolio.get_total_value()
        confidence_normalized = signal['confidence'] / 100.0  # Convert to 0-1 range

        # Base position size: 2-5% of portfolio based on confidence
        base_pct = 2.0 + (confidence_normalized * 3.0)  # 2% at 0 confidence, 5% at 1.0
        position_size_usd = portfolio_value * (base_pct / 100)

        # Calculate risk amount (distance from entry to stop loss)
        entry_price = signal['entry_price']
        stop_loss = signal['stop_loss']
        risk_per_unit = abs(entry_price - stop_loss)
        quantity = position_size_usd / entry_price
        risk_amount_usd = quantity * risk_per_unit

        # Save signal to database first
        signal_id = await self.db.save_mover_signal(
            symbol=signal['symbol'],
            direction=signal['direction'],
            confidence=signal['confidence'],
            entry_price=signal['entry_price'],
            stop_loss=signal['stop_loss'],
            tp1=signal['tp1'],
            position_size_usd=position_size_usd,
            risk_amount_usd=risk_amount_usd,
            technical_score=signal.get('technical_score'),
            sentiment_score=signal.get('sentiment_score'),
            liquidity_score=signal.get('liquidity_score'),
            correlation_score=signal.get('correlation_score'),
            analysis=signal.get('analysis', '')
        )

        # Execute paper trade using execute_signal method
        # Map direction (LONG/SHORT) to signal type (BUY/SELL)
        signal_type = 'STRONG_BUY' if signal['direction'] == 'LONG' else 'STRONG_SELL'

        trade_signal = {
            'symbol': signal['symbol'],
            'type': signal_type,
            'confidence': confidence_normalized,
        }

        result = await self.portfolio.execute_signal(
            signal=trade_signal,
            current_price=signal['entry_price'],
            market_data=None
        )

        if result['executed']:
            logger.info(f"✓ Position created (Signal ID: {signal_id})")
            logger.info(f"✓ Monitoring activated\n")
        else:
            logger.warning(f"⚠ Trade execution issue: {result.get('reason', 'Unknown')}")
            logger.info(f"Signal saved as ID: {signal_id}\n")

    def _get_weak_components(
        self,
        technical: float,
        sentiment: float,
        liquidity: float,
        correlation: float,
    ) -> List[str]:
        """
        Identify scoring components that are below their threshold (60% of max).

        Args:
            technical: Technical score (max depends on mode: 40 with sentiment, 55 without)
            sentiment: Sentiment score (0-30, or 0 if sentiment disabled)
            liquidity: Liquidity score (max depends on mode: 20 with sentiment, 30 without)
            correlation: Correlation score (max depends on mode: 10 with sentiment, 15 without)

        Returns:
            List of component names that are below threshold
        """
        weak = []
        if self.config.use_sentiment:
            # Full scoring mode: Tech 0-40, Sent 0-30, Liq 0-20, Corr 0-10
            if technical < 24:  # 60% of 40
                weak.append("technical")
            if sentiment < 18:  # 60% of 30
                weak.append("sentiment")
            if liquidity < 12:  # 60% of 20
                weak.append("liquidity")
            if correlation < 6:  # 60% of 10
                weak.append("correlation")
        else:
            # Technical-only mode: Tech 0-55, Liq 0-30, Corr 0-15
            if technical < 33:  # 60% of 55
                weak.append("technical")
            # sentiment is always 0 in no-sentiment mode, don't flag as weak
            if liquidity < 18:  # 60% of 30
                weak.append("liquidity")
            if correlation < 9:  # 60% of 15
                weak.append("correlation")
        return weak

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
