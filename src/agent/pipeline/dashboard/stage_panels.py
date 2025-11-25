"""Stage panel renderers for pipeline dashboard."""
from typing import Dict, Any, Optional
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, BarColumn, TextColumn
from rich.console import Group

from .styles import COLORS, ICONS, BORDERS, get_status_style, get_direction_icon, get_border_style
from .events import StageStatus


STAGE_NAMES = {
    "analysis": ("Analysis Agent", 1),
    "risk_auditor": ("Risk Auditor", 2),
    "execution": ("Execution Agent", 3),
    "pnl_auditor": ("P&L Auditor", 4),
}


class StagePanelRenderer:
    """Renders Rich panels for each pipeline stage."""

    def render_analysis(
        self,
        status: StageStatus,
        elapsed_ms: int,
        output: Optional[Dict[str, Any]] = None
    ) -> Panel:
        """Render analysis agent panel."""
        if status == StageStatus.RUNNING:
            return self.render_running("Analysis Agent", 1, elapsed_ms)
        if status == StageStatus.PENDING:
            return self.render_pending("Analysis Agent", 1)

        # Complete state
        elapsed_sec = elapsed_ms / 1000
        signal = output.get("proposed_signal") if output else None
        report = output.get("analysis_report", {}) if output else {}

        if signal is None:
            # No trade
            content = Text()
            content.append("NO TRADE\n", style=COLORS["muted"])
            content.append("Confidence too low or no clear setup", style=COLORS["muted"])
            border_style = BORDERS["no_trade"]
            status_text = f"NO_TRADE ({elapsed_sec:.1f}s)"
        else:
            content = self._build_analysis_content(signal, report)
            border_style = BORDERS["complete"]
            status_text = f"{ICONS['complete']} COMPLETE ({elapsed_sec:.1f}s)"

        return Panel(
            content,
            title=f"[bold]Stage 1: Analysis Agent[/bold] ━ [{get_status_style('complete')}]{status_text}[/]",
            border_style=border_style,
            padding=(0, 1)
        )

    def _build_analysis_content(self, signal: Dict, report: Dict) -> Group:
        """Build content for analysis panel with signal."""
        parts = []

        # Signal summary
        direction = signal.get("direction", "LONG")
        icon = get_direction_icon(direction)
        color = COLORS["long"] if direction == "LONG" else COLORS["short"]
        entry = signal.get("entry_price", 0)
        sl = signal.get("stop_loss", 0)
        tp = signal.get("take_profit", 0)
        conf = signal.get("confidence", 0)
        size = signal.get("position_size_pct", 0)

        # Calculate percentages
        sl_pct = ((sl - entry) / entry * 100) if entry else 0
        tp_pct = ((tp - entry) / entry * 100) if entry else 0

        signal_text = Text()
        signal_text.append("PROPOSED SIGNAL\n", style="bold")
        signal_text.append(f"  {icon} ", style=color)
        signal_text.append(f"{direction}", style=color)
        signal_text.append(f" @ ${entry:,.2f}\n", style=COLORS["price"])
        signal_text.append(f"  Stop Loss: ${sl:,.2f} ({sl_pct:+.1f}%)  ", style=COLORS["bearish"])
        signal_text.append(f"Take Profit: ${tp:,.2f} ({tp_pct:+.1f}%)\n", style=COLORS["bullish"])
        signal_text.append(f"  Position Size: {size:.1f}% of portfolio\n")
        parts.append(signal_text)

        # Scoring breakdown
        tech = report.get("technical", {})
        sent = report.get("sentiment", {})
        liq = report.get("liquidity", {})

        tech_score = int(tech.get("trend_score", 0) * 40) if tech.get("trend_score") else 0
        sent_score = sent.get("score", 0) if isinstance(sent.get("score"), int) else 0
        liq_score = 15 if liq.get("assessment") == "good" else 10

        score_text = Text()
        score_text.append("\nSCORING\n", style="bold")
        score_text.append(f"  Technical: {self._bar(tech_score, 40)} {tech_score}/40  ")
        score_text.append(f"Sentiment: {self._bar(sent_score, 30)} {sent_score}/30\n")
        score_text.append(f"  Liquidity: {self._bar(liq_score, 20)} {liq_score}/20  ")
        score_text.append(f"Confidence: {conf}/100\n")
        parts.append(score_text)

        # Reasoning
        reasoning = signal.get("reasoning", "")
        if reasoning:
            reason_text = Text()
            reason_text.append("\nREASONING\n", style="bold")
            reason_text.append(f"  {reasoning[:200]}", style=COLORS["muted"])
            parts.append(reason_text)

        return Group(*parts)

    def _bar(self, value: int, max_val: int, width: int = 10) -> str:
        """Create a simple text progress bar."""
        filled = int((value / max_val) * width) if max_val > 0 else 0
        return "█" * filled + "░" * (width - filled)

    def render_risk(
        self,
        status: StageStatus,
        elapsed_ms: int,
        output: Optional[Dict[str, Any]] = None,
        previous_signal: Optional[Dict[str, Any]] = None
    ) -> Panel:
        """Render risk auditor panel."""
        if status == StageStatus.RUNNING:
            return self.render_running("Risk Auditor", 2, elapsed_ms)
        if status == StageStatus.PENDING:
            return self.render_pending("Risk Auditor", 2)
        if status == StageStatus.SKIPPED:
            return self._render_skipped("Risk Auditor", 2)

        elapsed_sec = elapsed_ms / 1000
        decision = output.get("risk_decision", {}) if output else {}
        action = decision.get("action", "REJECT")

        if action == "REJECT":
            content = self._build_risk_reject_content(decision)
            border_style = BORDERS["rejected"]
            status_text = f"REJECT ({elapsed_sec:.1f}s)"
            status_color = COLORS["warning"]
        else:
            content = self._build_risk_modify_content(decision, previous_signal)
            border_style = BORDERS["complete"]
            if action == "MODIFY":
                status_text = f"MODIFY ({elapsed_sec:.1f}s)"
                status_color = COLORS["warning"]
            else:
                status_text = f"{ICONS['complete']} APPROVE ({elapsed_sec:.1f}s)"
                status_color = COLORS["success"]

        return Panel(
            content,
            title=f"[bold]Stage 2: Risk Auditor[/bold] ━ [{status_color}]{status_text}[/]",
            border_style=border_style,
            padding=(0, 1)
        )

    def _build_risk_reject_content(self, decision: Dict) -> Text:
        """Build content for rejected signal."""
        content = Text()
        content.append("DECISION: ", style="bold")
        content.append("REJECT\n\n", style=COLORS["error"])
        content.append("REASON\n", style="bold")
        content.append(f"  {decision.get('reason', 'Risk limits exceeded')}\n\n", style=COLORS["warning"])
        content.append(f"RISK SCORE: {decision.get('risk_score', 0)}/100", style=COLORS["muted"])
        return content

    def _build_risk_modify_content(self, decision: Dict, prev: Optional[Dict]) -> Group:
        """Build content for approved/modified signal."""
        parts = []

        action = decision.get("action", "APPROVE")
        content = Text()
        content.append("DECISION: ", style="bold")
        if action == "MODIFY":
            content.append("MODIFY\n", style=COLORS["warning"])
        else:
            content.append("APPROVE\n", style=COLORS["success"])
        parts.append(content)

        # Show changes if modified
        mods = decision.get("modifications", [])
        if mods:
            changes = Text()
            changes.append("\nCHANGES\n", style="bold")
            orig_conf = decision.get("original_confidence", 0)
            new_conf = decision.get("audited_confidence", orig_conf)
            if orig_conf != new_conf:
                changes.append(f"  Confidence: {orig_conf} → ", style=COLORS["muted"])
                changes.append(f"{new_conf}", style=COLORS["warning"])
                changes.append(f" ({new_conf - orig_conf:+d})\n")
            for mod in mods:
                changes.append(f"  • {mod}\n", style=COLORS["muted"])
            parts.append(changes)

        # Warnings
        warnings = decision.get("warnings", [])
        if warnings:
            warn_text = Text()
            warn_text.append("\nWARNINGS\n", style="bold")
            for w in warnings:
                warn_text.append(f"  {ICONS['warning']} {w}\n", style=COLORS["warning"])
            parts.append(warn_text)

        # Risk score
        score_text = Text()
        score_text.append(f"\nRISK SCORE: {decision.get('risk_score', 0)}/100", style=COLORS["muted"])
        parts.append(score_text)

        return Group(*parts)

    def render_execution(
        self,
        status: StageStatus,
        elapsed_ms: int,
        output: Optional[Dict[str, Any]] = None
    ) -> Panel:
        """Render execution agent panel."""
        if status == StageStatus.RUNNING:
            return self.render_running("Execution Agent", 3, elapsed_ms)
        if status == StageStatus.PENDING:
            return self.render_pending("Execution Agent", 3)
        if status == StageStatus.SKIPPED:
            return self._render_skipped("Execution Agent", 3)

        elapsed_sec = elapsed_ms / 1000
        report = output.get("execution_report", {}) if output else {}
        exec_status = report.get("status", "ABORTED")

        if exec_status == "ABORTED":
            content = self._build_execution_abort_content(report)
            border_style = BORDERS["aborted"]
            status_text = f"ABORTED ({elapsed_sec:.1f}s)"
            status_color = COLORS["warning"]
        else:
            content = self._build_execution_filled_content(report, output.get("position_opened", {}))
            border_style = BORDERS["complete"]
            status_text = f"{ICONS['complete']} FILLED ({elapsed_sec:.1f}s)"
            status_color = COLORS["success"]

        return Panel(
            content,
            title=f"[bold]Stage 3: Execution Agent[/bold] ━ [{status_color}]{status_text}[/]",
            border_style=border_style,
            padding=(0, 1)
        )

    def _build_execution_abort_content(self, report: Dict) -> Text:
        """Build content for aborted execution."""
        content = Text()
        content.append("ORDER ABORTED\n\n", style=COLORS["warning"])
        content.append("REASON\n", style="bold")
        content.append(f"  {report.get('reason', 'Market conditions unfavorable')}\n\n", style=COLORS["muted"])

        req = report.get("requested_entry", 0)
        cur = report.get("current_price", 0)
        dev = report.get("price_deviation_pct", 0)

        if req and cur:
            content.append("PRICE MOVEMENT\n", style="bold")
            content.append(f"  Requested: ${req:,.2f}  Current: ${cur:,.2f}\n")
            content.append(f"  Deviation: {dev:+.2f}%", style=COLORS["error"] if abs(dev) > 2 else COLORS["warning"])

        return content

    def _build_execution_filled_content(self, report: Dict, position: Dict) -> Group:
        """Build content for filled execution."""
        parts = []

        # Order details
        order_text = Text()
        order_text.append("ORDER EXECUTED\n", style="bold")
        order_text.append(f"  Type: {report.get('order_type', 'MARKET')}\n")

        req = report.get("requested_entry", 0)
        actual = report.get("actual_entry", req)
        slip = report.get("slippage_pct", 0)

        order_text.append(f"  Requested: ${req:,.2f}  Filled: ${actual:,.2f}\n")

        slip_color = COLORS["bullish"] if slip <= 0 else COLORS["bearish"]
        slip_note = " (better than expected)" if slip < 0 else ""
        order_text.append(f"  Slippage: ", style=COLORS["muted"])
        order_text.append(f"{slip:+.3f}%{slip_note}\n", style=slip_color)
        parts.append(order_text)

        # Position details
        if position:
            pos_text = Text()
            pos_text.append("\nPOSITION OPENED\n", style="bold")
            size = position.get("size", report.get("position_size", 0))
            value = report.get("position_value_usd", 0)
            pos_text.append(f"  Size: {size:.6f} (${value:,.2f})\n")
            pos_text.append(f"  Entry: ${position.get('entry_price', actual):,.2f}\n")
            pos_text.append(f"  Stop Loss: ${position.get('stop_loss', 0):,.2f}  ")
            pos_text.append(f"Take Profit: ${position.get('take_profit', 0):,.2f}\n")
            parts.append(pos_text)

        return Group(*parts)

    def render_running(
        self,
        stage_name: str,
        stage_number: int,
        elapsed_ms: int,
        message: Optional[str] = None
    ) -> Panel:
        """Render a running stage panel."""
        elapsed_sec = elapsed_ms / 1000

        content = Text()
        content.append("\n")
        content.append(f"  {'░' * 40} {elapsed_sec:.1f}s elapsed\n\n", style=COLORS["running"])
        content.append(f"  {message or 'Processing...'}\n", style=COLORS["muted"])

        return Panel(
            content,
            title=f"[bold]Stage {stage_number}: {stage_name}[/bold] ━ [{COLORS['running']}]{ICONS['running']} RUNNING[/]",
            border_style=BORDERS["running"],
            padding=(0, 1)
        )

    def render_pending(self, stage_name: str, stage_number: int) -> Panel:
        """Render a pending stage panel."""
        content = Text()
        content.append(f"\n  {ICONS['pending']} Waiting for previous stage...\n", style=COLORS["pending"])

        return Panel(
            content,
            title=f"[bold dim]Stage {stage_number}: {stage_name}[/bold dim] ━ [{COLORS['pending']}]PENDING[/]",
            border_style=BORDERS["pending"],
            padding=(0, 1)
        )

    def _render_skipped(self, stage_name: str, stage_number: int) -> Panel:
        """Render a skipped stage panel."""
        content = Text()
        content.append(f"\n  Skipped (previous stage ended pipeline)\n", style=COLORS["muted"])

        return Panel(
            content,
            title=f"[bold dim]Stage {stage_number}: {stage_name}[/bold dim] ━ [dim]SKIPPED[/dim]",
            border_style=BORDERS["pending"],
            padding=(0, 1)
        )


# Convenience functions
def render_analysis_panel(status: StageStatus, elapsed_ms: int, output: Optional[Dict] = None) -> Panel:
    """Render analysis panel."""
    return StagePanelRenderer().render_analysis(status, elapsed_ms, output)


def render_risk_panel(status: StageStatus, elapsed_ms: int, output: Optional[Dict] = None, prev: Optional[Dict] = None) -> Panel:
    """Render risk panel."""
    return StagePanelRenderer().render_risk(status, elapsed_ms, output, prev)


def render_execution_panel(status: StageStatus, elapsed_ms: int, output: Optional[Dict] = None) -> Panel:
    """Render execution panel."""
    return StagePanelRenderer().render_execution(status, elapsed_ms, output)


def render_running_panel(stage_name: str, stage_number: int, elapsed_ms: int, message: str = None) -> Panel:
    """Render running panel."""
    return StagePanelRenderer().render_running(stage_name, stage_number, elapsed_ms, message)


def render_pending_panel(stage_name: str, stage_number: int) -> Panel:
    """Render pending panel."""
    return StagePanelRenderer().render_pending(stage_name, stage_number)
