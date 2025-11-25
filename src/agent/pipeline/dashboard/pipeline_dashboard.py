"""Main dashboard controller for pipeline visualization."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from contextlib import asynccontextmanager
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.live import Live

from .styles import COLORS, ICONS, get_border_style
from .events import StageEvent, StageStatus, PipelineState
from .stage_panels import StagePanelRenderer
from .sidebar import SidebarRenderer
from .history_feed import HistoryFeed, PipelineHistoryEntry


@dataclass
class DashboardConfig:
    """Configuration for pipeline dashboard."""
    show_sidebar: bool = True
    show_history: bool = True
    max_history: int = 10
    refresh_rate: int = 4  # Hz


class PipelineDashboard:
    """
    Main dashboard controller for multi-agent pipeline visualization.

    Coordinates all visual components and manages live updates.
    """

    def __init__(self, config: Optional[DashboardConfig] = None):
        """
        Initialize dashboard.

        Args:
            config: Dashboard configuration options
        """
        self.config = config or DashboardConfig()
        self.console = Console()

        # Renderers
        self.stage_renderer = StagePanelRenderer()
        self.sidebar_renderer = SidebarRenderer()

        # State
        self.state: Optional[PipelineState] = None
        self.portfolio_state: Dict[str, Any] = {}
        self.agent_stats: Dict[str, Any] = {}
        self.history = HistoryFeed(max_entries=self.config.max_history)

        # Live display
        self._live: Optional[Live] = None

    def start_pipeline(self, symbol: str, session_id: str) -> None:
        """
        Start tracking a new pipeline run.

        Args:
            symbol: Trading symbol being analyzed
            session_id: Session identifier
        """
        self.state = PipelineState(symbol=symbol, session_id=session_id)

    def handle_event(self, event: StageEvent) -> None:
        """
        Handle a stage event from the orchestrator.

        Args:
            event: Stage event with status update
        """
        if self.state:
            self.state.update(event)
            if self._live:
                self._live.update(self.build_layout())

    def update_portfolio(self, state: Dict[str, Any]) -> None:
        """
        Update portfolio state.

        Args:
            state: Portfolio state dictionary
        """
        self.portfolio_state = state

    def update_stats(self, stats: Dict[str, Any]) -> None:
        """
        Update agent statistics.

        Args:
            stats: Agent statistics dictionary
        """
        self.agent_stats = stats

    def finalize_pipeline(self, outcome: str, detail: Optional[str] = None) -> None:
        """
        Finalize pipeline run and add to history.

        Args:
            outcome: Final outcome (EXECUTED, REJECTED, etc.)
            detail: Optional detail text
        """
        if self.state:
            self.state.final_outcome = outcome
            entry = PipelineHistoryEntry(
                symbol=self.state.symbol,
                outcome=outcome,
                timestamp=datetime.now(),
                detail=detail
            )
            self.history.add(entry)

    def build_layout(self) -> Layout:
        """
        Build the complete dashboard layout.

        Returns:
            Rich Layout with all components
        """
        layout = Layout()

        # Header
        header = self._build_header()

        # Main content area
        if self.config.show_sidebar:
            # Split layout: main (pipeline) | sidebar
            layout.split_column(
                Layout(header, name="header", size=3),
                Layout(name="body"),
                Layout(name="footer", size=3) if self.config.show_history else Layout(size=0)
            )

            layout["body"].split_row(
                Layout(name="main", ratio=3),
                Layout(name="sidebar", ratio=1, minimum_size=25)
            )

            # Build main pipeline area
            layout["main"].update(self._build_pipeline_panels())

            # Build sidebar
            layout["sidebar"].split_column(
                Layout(self.sidebar_renderer.render_portfolio(self.portfolio_state), name="portfolio"),
                Layout(self.sidebar_renderer.render_agent_stats(self.agent_stats), name="stats")
            )
        else:
            layout.split_column(
                Layout(header, name="header", size=3),
                Layout(self._build_pipeline_panels(), name="main"),
                Layout(name="footer", size=3) if self.config.show_history else Layout(size=0)
            )

        # History footer
        if self.config.show_history:
            layout["footer"].update(Panel(
                self.history.render_inline(),
                border_style=COLORS["muted"]
            ))

        return layout

    def _build_header(self) -> Panel:
        """Build the header panel."""
        now = datetime.now()

        text = Text()
        text.append("CCTRADER PIPELINE", style="bold cyan")
        text.append(" │ ", style=COLORS["muted"])

        if self.state:
            text.append(self.state.symbol, style="bold white")
            text.append(" │ ", style=COLORS["muted"])

        text.append(now.strftime("%H:%M:%S"), style=COLORS["muted"])

        if self.state:
            text.append(" │ Session: ", style=COLORS["muted"])
            session_short = self.state.session_id[:20] + "..." if len(self.state.session_id) > 20 else self.state.session_id
            text.append(session_short, style=COLORS["muted"])

        return Panel(text, border_style=COLORS["header"])

    def _build_pipeline_panels(self) -> Layout:
        """Build the pipeline stage panels with connectors."""
        layout = Layout()

        if not self.state:
            # No active pipeline
            layout.update(Panel(
                Text("No pipeline active. Waiting for analysis...", style=COLORS["muted"]),
                title="[bold]Pipeline[/bold]",
                border_style=COLORS["muted"]
            ))
            return layout

        # Get stage data
        stages = self.state.stages

        # Build panels for each stage
        analysis_data = stages.get("analysis", {})
        risk_data = stages.get("risk_auditor", {})
        execution_data = stages.get("execution", {})

        analysis_panel = self._render_stage_panel("analysis", analysis_data)
        risk_panel = self._render_stage_panel("risk_auditor", risk_data, analysis_data.get("output"))
        execution_panel = self._render_stage_panel("execution", execution_data)

        # Create connector arrows
        connector1 = self._build_connector(analysis_data, "proposed_signal")
        connector2 = self._build_connector(risk_data, "audited_signal")

        # Stack panels vertically with connectors
        layout.split_column(
            Layout(analysis_panel, name="analysis", size=8),
            Layout(connector1, name="conn1", size=2),
            Layout(risk_panel, name="risk", size=8),
            Layout(connector2, name="conn2", size=2),
            Layout(execution_panel, name="execution", size=8),
        )

        return layout

    def _render_stage_panel(
        self,
        stage_name: str,
        stage_data: Dict[str, Any],
        previous_output: Optional[Dict[str, Any]] = None
    ) -> Panel:
        """Render a single stage panel based on its state."""
        status = stage_data.get("status", StageStatus.PENDING)
        elapsed_ms = stage_data.get("elapsed_ms", 0)
        output = stage_data.get("output")
        message = stage_data.get("message")

        if stage_name == "analysis":
            return self.stage_renderer.render_analysis(status, elapsed_ms, output)
        elif stage_name == "risk_auditor":
            prev_signal = previous_output.get("proposed_signal") if previous_output else None
            return self.stage_renderer.render_risk(status, elapsed_ms, output, prev_signal)
        elif stage_name == "execution":
            return self.stage_renderer.render_execution(status, elapsed_ms, output)
        else:
            return self.stage_renderer.render_pending(stage_name, 4)

    def _build_connector(self, stage_data: Dict[str, Any], signal_name: str) -> Text:
        """Build connector arrow between stages."""
        status = stage_data.get("status", StageStatus.PENDING)

        text = Text()
        text.append("          │\n", style=COLORS["muted"])

        if status == StageStatus.COMPLETE:
            output = stage_data.get("output", {})
            if signal_name in str(output) or output:
                text.append(f"          ▼ {signal_name}", style=COLORS["value"])
            else:
                text.append("          ▼", style=COLORS["muted"])
        else:
            text.append("          │", style=COLORS["pending"])

        return text

    @asynccontextmanager
    async def live_display(self):
        """
        Context manager for live updating display.

        Usage:
            async with dashboard.live_display():
                # Run pipeline, events will update display
        """
        self._live = Live(
            self.build_layout(),
            console=self.console,
            refresh_per_second=self.config.refresh_rate,
            screen=True
        )
        try:
            self._live.start()
            yield self._live
        finally:
            self._live.stop()
            self._live = None

    def render_once(self) -> None:
        """Render dashboard once without live updates."""
        self.console.print(self.build_layout())
