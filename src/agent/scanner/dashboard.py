# src/agent/scanner/dashboard.py
"""Scanner dashboard for visualizing market movers analysis cycles."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live

from src.agent.pipeline.dashboard.styles import COLORS, ICONS, get_status_style, get_border_style
from .log_handler import SplitScreenManager


class ScannerEvent:
    """Scanner event type constants."""
    CYCLE_START = "cycle_start"
    MOVER_START = "mover_start"
    ANALYSIS_PHASE = "analysis_phase"
    SIGNAL_GENERATED = "signal_generated"
    RISK_CHECK = "risk_check"
    EXECUTION = "execution"
    MOVER_COMPLETE = "mover_complete"
    CYCLE_COMPLETE = "cycle_complete"


@dataclass
class MoverStatus:
    """Status tracking for individual market movers."""
    symbol: str
    change_pct: float
    direction: str  # "gainer" or "loser"
    status: str  # "pending", "analyzing", "complete"
    stage: Optional[str] = None  # "analysis", "risk", "execution"
    stage_detail: Optional[str] = None  # "technical", "sentiment", etc.
    result: Optional[str] = None  # "NO_TRADE", "EXECUTED", "REJECTED"
    confidence: Optional[int] = None
    entry_price: Optional[float] = None
    # Analysis details for NO_TRADE transparency
    score_breakdown: Optional[Dict[str, float]] = None  # technical, sentiment, liquidity, correlation
    weak_components: Optional[List[str]] = None  # Components below threshold
    sentiment_findings: Optional[List[str]] = None  # Top 3 key findings from news


# Component score thresholds (60% of max for each)
SCORE_THRESHOLDS = {
    "technical": {"max": 40, "threshold": 24},
    "sentiment": {"max": 30, "threshold": 18},
    "liquidity": {"max": 20, "threshold": 12},
    "correlation": {"max": 10, "threshold": 6},
}

# Thresholds when sentiment analysis is disabled (redistributed scoring)
NO_SENTIMENT_THRESHOLDS = {
    "technical": {"max": 55, "threshold": 33},
    "liquidity": {"max": 30, "threshold": 18},
    "correlation": {"max": 15, "threshold": 9},
}


@dataclass
class CycleState:
    """State tracking for a scan cycle."""
    cycle_number: int
    started_at: datetime
    movers: List[MoverStatus] = field(default_factory=list)
    signals_generated: int = 0
    trades_executed: int = 0
    trades_rejected: int = 0


class ScannerDashboard:
    """Dashboard for visualizing scanner cycles and mover analysis."""

    def __init__(
        self,
        max_history: int = 5,
        enable_log_capture: bool = True,
        console: Optional[Console] = None,
        use_sentiment: bool = True,
    ):
        """
        Initialize scanner dashboard.

        Args:
            max_history: Maximum number of cycles to keep in history.
            enable_log_capture: Whether to capture logs for split-screen display.
            console: Rich Console instance to use. If None, creates a new one.
            use_sentiment: Whether sentiment scoring is enabled.
        """
        self.current_cycle: Optional[CycleState] = None
        self.history: List[CycleState] = []
        self.max_history = max_history
        self.use_sentiment = use_sentiment
        # Select appropriate thresholds based on sentiment mode
        self._thresholds = SCORE_THRESHOLDS if use_sentiment else NO_SENTIMENT_THRESHOLDS
        self.portfolio: Dict[str, Any] = {}
        self.stats: Dict[str, Any] = {}
        self._live: Optional[Live] = None
        self.session_id: Optional[str] = None
        self.console = console or Console()

        # Throttling: limit updates to 4/sec to prevent flickering
        self._last_update_time: float = 0.0
        self._min_update_interval: float = 0.25  # 250ms

        # Split screen manager for log capture
        self.enable_log_capture = enable_log_capture
        self.split_screen: Optional[SplitScreenManager] = None
        if enable_log_capture:
            self.split_screen = SplitScreenManager(log_display_lines=8)

    def _throttled_refresh(self, force: bool = False) -> None:
        """
        Update the live display with throttling to prevent flickering.

        Args:
            force: If True, bypass throttling and update immediately.
        """
        import time
        if not self._live:
            return

        now = time.time()
        if force or (now - self._last_update_time >= self._min_update_interval):
            self._live.update(self.render())
            self._last_update_time = now

    def start_cycle(self, cycle_number: int, movers: List[Dict[str, Any]]) -> None:
        """
        Start a new scan cycle.

        Args:
            cycle_number: The cycle number.
            movers: List of mover data dicts with symbol, change_pct, direction.
        """
        mover_statuses = [
            MoverStatus(
                symbol=m["symbol"],
                change_pct=m["change_pct"],
                direction=m["direction"],
                status="pending",
            )
            for m in movers
        ]
        self.current_cycle = CycleState(
            cycle_number=cycle_number,
            started_at=datetime.now(),
            movers=mover_statuses,
        )

    def update_mover(
        self,
        symbol: str,
        status: Optional[str] = None,
        stage: Optional[str] = None,
        stage_detail: Optional[str] = None,
    ) -> None:
        """
        Update a mover's status.

        Args:
            symbol: The mover symbol.
            status: New status value.
            stage: Current stage.
            stage_detail: Stage detail (e.g., "technical", "sentiment").
        """
        if not self.current_cycle:
            return

        for mover in self.current_cycle.movers:
            if mover.symbol == symbol:
                if status:
                    mover.status = status
                if stage:
                    mover.stage = stage
                if stage_detail:
                    mover.stage_detail = stage_detail
                break

    def complete_mover(
        self,
        symbol: str,
        result: str,
        confidence: Optional[int] = None,
        entry_price: Optional[float] = None,
        score_breakdown: Optional[Dict[str, float]] = None,
        weak_components: Optional[List[str]] = None,
        sentiment_findings: Optional[List[str]] = None,
    ) -> None:
        """
        Mark a mover as complete.

        Args:
            symbol: The mover symbol.
            result: Result string (NO_TRADE, EXECUTED, REJECTED).
            confidence: Final confidence score.
            entry_price: Entry price if executed.
            score_breakdown: Dict with technical, sentiment, liquidity, correlation scores.
            weak_components: List of component names that were below threshold.
            sentiment_findings: Top 3 key findings from sentiment analysis.
        """
        if not self.current_cycle:
            return

        for mover in self.current_cycle.movers:
            if mover.symbol == symbol:
                mover.status = "complete"
                mover.result = result
                if confidence is not None:
                    mover.confidence = confidence
                if entry_price is not None:
                    mover.entry_price = entry_price
                if score_breakdown is not None:
                    mover.score_breakdown = score_breakdown
                if weak_components is not None:
                    mover.weak_components = weak_components
                if sentiment_findings is not None:
                    mover.sentiment_findings = sentiment_findings
                break

    def complete_cycle(
        self,
        signals_generated: int = 0,
        trades_executed: int = 0,
        trades_rejected: int = 0,
    ) -> None:
        """
        Complete the current cycle and add to history.

        Args:
            signals_generated: Number of signals generated.
            trades_executed: Number of trades executed.
            trades_rejected: Number of trades rejected.
        """
        if not self.current_cycle:
            return

        self.current_cycle.signals_generated = signals_generated
        self.current_cycle.trades_executed = trades_executed
        self.current_cycle.trades_rejected = trades_rejected

        # Add to history
        self.history.insert(0, self.current_cycle)
        if len(self.history) > self.max_history:
            self.history.pop()

    def get_cycle_progress(self) -> Dict[str, int]:
        """
        Get the progress of the current cycle.

        Returns:
            Dict with total, completed, and pending counts.
        """
        if not self.current_cycle:
            return {"total": 0, "completed": 0, "pending": 0}

        total = len(self.current_cycle.movers)
        completed = sum(1 for m in self.current_cycle.movers if m.status == "complete")
        return {
            "total": total,
            "completed": completed,
            "pending": total - completed,
        }

    def handle_event(self, event_type: str, **kwargs) -> None:
        """
        Handle a scanner event.

        Args:
            event_type: Type of event (from ScannerEvent).
            **kwargs: Event-specific data.
        """
        if event_type == ScannerEvent.CYCLE_START:
            self.start_cycle(
                cycle_number=kwargs.get("cycle_number", 1),
                movers=kwargs.get("movers", []),
            )

        elif event_type == ScannerEvent.MOVER_START:
            self.update_mover(
                symbol=kwargs["symbol"],
                status="analyzing",
            )

        elif event_type == ScannerEvent.ANALYSIS_PHASE:
            self.update_mover(
                symbol=kwargs["symbol"],
                stage="analysis",
                stage_detail=kwargs.get("phase"),
            )

        elif event_type == ScannerEvent.SIGNAL_GENERATED:
            if self.current_cycle:
                for mover in self.current_cycle.movers:
                    if mover.symbol == kwargs["symbol"]:
                        mover.confidence = kwargs.get("confidence")
                        mover.entry_price = kwargs.get("entry_price")
                        break

        elif event_type == ScannerEvent.RISK_CHECK:
            self.update_mover(
                symbol=kwargs["symbol"],
                stage="risk",
            )

        elif event_type == ScannerEvent.EXECUTION:
            self.update_mover(
                symbol=kwargs["symbol"],
                stage="execution",
            )

        elif event_type == ScannerEvent.MOVER_COMPLETE:
            self.complete_mover(
                symbol=kwargs["symbol"],
                result=kwargs.get("result", "NO_TRADE"),
                confidence=kwargs.get("confidence"),
                entry_price=kwargs.get("entry_price"),
                score_breakdown=kwargs.get("score_breakdown"),
                weak_components=kwargs.get("weak_components"),
                sentiment_findings=kwargs.get("sentiment_findings"),
            )

        elif event_type == ScannerEvent.CYCLE_COMPLETE:
            self.complete_cycle(
                signals_generated=kwargs.get("signals_generated", 0),
                trades_executed=kwargs.get("trades_executed", 0),
                trades_rejected=kwargs.get("trades_rejected", 0),
            )

        # Update display with throttled refresh
        self._throttled_refresh()

    def update_portfolio(self, data: Dict[str, Any]) -> None:
        """Update portfolio display data."""
        self.portfolio = data
        self._throttled_refresh()

    def update_stats(self, data: Dict[str, Any]) -> None:
        """Update stats display data."""
        self.stats = data
        self._throttled_refresh()

    def _render_header(self) -> Panel:
        """Render the dashboard header."""
        now = datetime.now()
        cycle_num = self.current_cycle.cycle_number if self.current_cycle else 0
        session = self.session_id or "scanner"

        header_text = Text()
        header_text.append("MARKET MOVERS SCANNER", style="bold bright_cyan")
        header_text.append("  |  ", style="dim")
        header_text.append(f"Cycle #{cycle_num}", style="yellow")
        header_text.append("  |  ", style="dim")
        header_text.append(now.strftime("%H:%M:%S"), style="bright_white")
        header_text.append("  |  ", style="dim")
        header_text.append(f"Session: {session}", style="dim cyan")

        return Panel(
            header_text,
            style="cyan",
            border_style="bright_cyan",
        )

    def _render_progress(self) -> Text:
        """Render the cycle progress bar."""
        progress = self.get_cycle_progress()
        total = progress["total"] or 1
        completed = progress["completed"]

        # Build progress bar
        bar_width = 20
        filled = int((completed / total) * bar_width)

        text = Text()
        text.append("CYCLE PROGRESS ", style="bold white")
        text.append("[", style="white")
        text.append(ICONS["running"] * filled, style="green")
        text.append(ICONS["pending"] * (bar_width - filled), style="dim")
        text.append(f"] {completed}/{total}", style="white")
        return text

    def _render_mover_row(self, mover: MoverStatus) -> Text:
        """Render a single mover row with expanded details for completed analysis."""
        text = Text()

        # Direction icon
        if mover.direction == "gainer":
            text.append(f"  {ICONS['long']} ", style=COLORS["long"])
        else:
            text.append(f"  {ICONS['short']} ", style=COLORS["short"])

        # Symbol and change
        symbol_display = mover.symbol.replace("/", "").replace(":USDT", "")
        text.append(f"{symbol_display:<10}", style="bold white")

        change_style = COLORS["long"] if mover.change_pct >= 0 else COLORS["short"]
        text.append(f"{mover.change_pct:+.1f}%  ", style=change_style)

        # Status
        if mover.status == "complete":
            if mover.result == "EXECUTED":
                text.append(f"{ICONS['complete']} EXECUTED", style=COLORS["success"])
                if mover.confidence:
                    text.append(f" ({mover.confidence}/100)", style="dim")
                if mover.entry_price:
                    text.append(f" @ ${mover.entry_price:,.2f}", style="dim")
            elif mover.result == "NO_TRADE":
                text.append(f"{ICONS['complete']} NO_TRADE", style=COLORS["neutral"])
                if mover.confidence:
                    text.append(f" ({mover.confidence}/100)", style="dim")
            elif mover.result == "REJECTED":
                text.append(f"{ICONS['error']} REJECTED", style=COLORS["error"])
                if mover.confidence:
                    text.append(f" ({mover.confidence}/100)", style="dim")
            else:
                text.append(f"{ICONS['complete']} {mover.result or 'DONE'}", style=COLORS["neutral"])

            # Add expanded details for completed movers with analysis data
            if mover.score_breakdown:
                text.append("\n")
                text.append("      Scores: ", style="dim")
                scores = mover.score_breakdown
                thresholds = self._thresholds
                tech_max = thresholds.get("technical", {}).get("max", 40)
                text.append(f"Tech {scores.get('technical', 0):.0f}/{tech_max}", style="cyan")
                if self.use_sentiment:
                    text.append(" │ ", style="dim")
                    text.append(f"Sent {scores.get('sentiment', 0):.0f}/30", style="cyan")
                text.append(" │ ", style="dim")
                liq_max = thresholds.get("liquidity", {}).get("max", 20)
                text.append(f"Liq {scores.get('liquidity', 0):.0f}/{liq_max}", style="cyan")
                text.append(" │ ", style="dim")
                corr_max = thresholds.get("correlation", {}).get("max", 10)
                text.append(f"Corr {scores.get('correlation', 0):.0f}/{corr_max}", style="cyan")

            # Show weak components if any (filter out sentiment if disabled)
            weak_comps = mover.weak_components or []
            if not self.use_sentiment:
                weak_comps = [c for c in weak_comps if c != "sentiment"]
            if weak_comps:
                text.append("\n")
                text.append("      Weak:   ", style="dim")
                weak_parts = []
                for comp in weak_comps:
                    threshold = self._thresholds.get(comp, {}).get("threshold", 0)
                    weak_parts.append(f"{comp.title()} (<{threshold})")
                text.append(", ".join(weak_parts), style="yellow")

            # Show sentiment findings if available (only when sentiment enabled)
            if self.use_sentiment and mover.sentiment_findings:
                text.append("\n")
                text.append("      News:", style="dim")
                for i, finding in enumerate(mover.sentiment_findings[:3]):
                    text.append("\n")
                    text.append(f"        • {finding}", style="dim white")

        elif mover.status == "analyzing":
            text.append(f"{ICONS['running']} Analysis", style=COLORS["running"])
            if mover.stage_detail:
                # Progress indicator for phase (conditional phases based on sentiment mode)
                phases = ["technical", "sentiment"] if self.use_sentiment else ["technical"]
                if mover.stage_detail in phases:
                    idx = phases.index(mover.stage_detail)
                    text.append("    [", style="dim cyan")
                    text.append(ICONS["running"] * (idx + 1), style="green")
                    text.append(ICONS["pending"] * (len(phases) - idx - 1), style="dim")
                    text.append(f"] {mover.stage_detail}", style="dim cyan")
        else:
            text.append(f"{ICONS['pending']} Pending", style=COLORS["pending"])

        return text

    def _render_movers_panel(self) -> Panel:
        """Render the movers list panel."""
        if not self.current_cycle or not self.current_cycle.movers:
            return Panel(
                Text("No movers in current cycle", style="dim"),
                title="[bold]MOVERS[/bold]",
                border_style="blue",
            )

        content = Text()
        content.append_text(self._render_progress())
        content.append("\n\n")

        for mover in self.current_cycle.movers:
            content.append_text(self._render_mover_row(mover))
            content.append("\n")

        return Panel(
            content,
            title="[bold]MOVERS[/bold]",
            border_style="blue",
        )

    def _render_portfolio_panel(self) -> Panel:
        """Render the portfolio sidebar panel."""
        content = Text()

        equity = self.portfolio.get("equity", 0)
        pnl_pct = self.portfolio.get("pnl_pct", 0)
        positions = self.portfolio.get("positions", 0)
        exposure = self.portfolio.get("exposure_pct", 0)

        pnl_style = COLORS["long"] if pnl_pct >= 0 else COLORS["short"]
        pnl_sign = "+" if pnl_pct >= 0 else ""

        content.append(f"${equity:,.0f}", style="bold bright_white")
        content.append(f" ({pnl_sign}{pnl_pct:.1f}%)\n", style=pnl_style)
        content.append(f"{positions} positions\n", style="dim")
        content.append(f"{exposure:.0f}% exposure", style="dim yellow")

        return Panel(
            content,
            title="[bold]PORTFOLIO[/bold]",
            border_style="green",
        )

    def _render_stats_panel(self) -> Panel:
        """Render the cycle stats sidebar panel."""
        content = Text()

        if self.current_cycle:
            signals = self.current_cycle.signals_generated
            executed = self.current_cycle.trades_executed
            rejected = self.current_cycle.trades_rejected
        else:
            signals = self.stats.get("total_signals", 0)
            executed = self.stats.get("total_executed", 0)
            rejected = self.stats.get("total_rejected", 0)

        win_rate = self.stats.get("win_rate", 0)

        content.append(f"Signals: {signals}\n", style="white")
        content.append(f"Executed: {executed}\n", style="green")
        content.append(f"Rejected: {rejected}\n", style="red")
        if win_rate:
            content.append(f"Win Rate: {win_rate:.0f}%", style="yellow")

        return Panel(
            content,
            title="[bold]CYCLE STATS[/bold]",
            border_style="yellow",
        )

    def _render_history_panel(self) -> Panel:
        """Render the history feed panel."""
        if not self.history:
            return Panel(
                Text("No history yet", style="dim"),
                title="[bold]HISTORY[/bold]",
                border_style="dim",
            )

        content = Text()
        for cycle in self.history[:3]:
            content.append(f"Cycle#{cycle.cycle_number}: ", style="cyan")
            content.append(f"{cycle.trades_executed} exec", style="green")
            content.append(" | ", style="dim")
            content.append(f"{len(cycle.movers)} movers", style="white")
            content.append("  |  ", style="dim")

        return Panel(
            content,
            title="[bold]HISTORY[/bold]",
            border_style="dim blue",
        )

    def render(self) -> Layout:
        """
        Render the full dashboard layout.

        Returns:
            Rich Layout object.
        """
        layout = Layout()

        # Main structure with optional log panel
        if self.split_screen:
            layout.split_column(
                Layout(name="header", size=3),
                Layout(name="body"),
                Layout(name="history", size=3),
                Layout(name="logs", size=10),
            )
        else:
            layout.split_column(
                Layout(name="header", size=3),
                Layout(name="body"),
                Layout(name="history", size=3),
            )

        # Body split into main and sidebar
        layout["body"].split_row(
            Layout(name="main", ratio=3),
            Layout(name="sidebar", ratio=1),
        )

        # Sidebar split into portfolio and stats
        layout["sidebar"].split_column(
            Layout(name="portfolio"),
            Layout(name="stats"),
        )

        # Fill in content
        layout["header"].update(self._render_header())
        layout["main"].update(self._render_movers_panel())
        layout["portfolio"].update(self._render_portfolio_panel())
        layout["stats"].update(self._render_stats_panel())
        layout["history"].update(self._render_history_panel())

        # Add log panel if enabled
        if self.split_screen:
            layout["logs"].update(self.split_screen.render_log_panel(height=8))

        return layout

    def render_once(self) -> None:
        """Render the dashboard once to console."""
        self.console.print(self.render())

    def get_log_handler(self):
        """
        Get the log handler for capturing logs.

        Returns:
            DashboardLogHandler if log capture is enabled, None otherwise.
        """
        if self.split_screen:
            return self.split_screen.get_log_handler()
        return None

    def install_log_handler(self, logger_name: Optional[str] = None) -> None:
        """
        Install log handler on a logger.

        Args:
            logger_name: Name of logger (None for root).
        """
        if self.split_screen:
            self.split_screen.install_handler(logger_name)

    def remove_log_handler(self, logger_name: Optional[str] = None) -> None:
        """
        Remove log handler from a logger.

        Args:
            logger_name: Name of logger (None for root).
        """
        if self.split_screen:
            self.split_screen.remove_handler(logger_name)

    async def live_display(self) -> "ScannerDashboardContext":
        """
        Create a live display context manager.

        Returns:
            Context manager for live display.
        """
        return ScannerDashboardContext(self)


class ScannerDashboardContext:
    """Context manager for live scanner dashboard display."""

    def __init__(self, dashboard: ScannerDashboard):
        self.dashboard = dashboard
        self._live: Optional[Live] = None

    async def __aenter__(self) -> "ScannerDashboardContext":
        """Start live display and install log handler."""
        self._live = Live(
            self.dashboard.render(),
            refresh_per_second=4,
            console=self.dashboard.console,
            screen=True,  # Use alternate screen buffer (htop-style)
        )
        self.dashboard._live = self._live

        # Set up throttled log callback using dashboard's throttled refresh
        if self.dashboard.split_screen:
            self.dashboard.split_screen.set_on_log_callback(
                self.dashboard._throttled_refresh
            )

        # Install log handler to capture logs
        self.dashboard.install_log_handler()

        self._live.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop live display and remove log handler."""
        if self._live:
            self._live.stop()
            self.dashboard._live = None

        # Remove log handler
        self.dashboard.remove_log_handler()
