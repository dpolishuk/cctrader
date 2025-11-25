# src/agent/pipeline/dashboard/mover_row.py
"""Mover row renderer for scanner dashboard."""
from dataclasses import dataclass
from typing import Optional

from rich.text import Text

from .styles import COLORS, ICONS


@dataclass
class MoverRowData:
    """Data for rendering a mover row."""
    symbol: str
    change_pct: float
    direction: str  # "gainer" or "loser"
    status: str  # "pending", "analyzing", "complete"
    stage: Optional[str] = None  # "analysis", "risk", "execution"
    stage_detail: Optional[str] = None  # "technical", "sentiment", etc.
    result: Optional[str] = None  # "NO_TRADE", "EXECUTED", "REJECTED"
    confidence: Optional[int] = None
    entry_price: Optional[float] = None


@dataclass
class MoverRowStyle:
    """Style configuration for mover row rendering."""
    show_icon: bool = True
    show_progress: bool = True
    compact: bool = False
    symbol_width: int = 10


class MoverRowRenderer:
    """Renderer for individual mover rows in the scanner dashboard."""

    # Analysis phases for progress tracking
    PHASES = ["technical", "sentiment"]

    def __init__(self, style: Optional[MoverRowStyle] = None):
        """
        Initialize the mover row renderer.

        Args:
            style: Optional style configuration.
        """
        self.style = style or MoverRowStyle()

    def _format_symbol(self, symbol: str) -> str:
        """
        Format symbol for display.

        Args:
            symbol: Raw symbol string.

        Returns:
            Formatted symbol string.
        """
        # Remove common suffixes
        result = symbol.replace("/USDT", "").replace(":USDT", "").replace("USDT", "")
        if not result:
            result = symbol
        if self.style.compact:
            return result[:6]
        return result

    def _render_direction_icon(self, direction: str) -> Text:
        """Render the direction indicator icon."""
        text = Text()
        if direction == "gainer":
            text.append(f"  {ICONS['long']} ", style=COLORS["long"])
        else:
            text.append(f"  {ICONS['short']} ", style=COLORS["short"])
        return text

    def _render_symbol_and_change(self, data: MoverRowData) -> Text:
        """Render symbol and percentage change."""
        text = Text()

        # Symbol
        symbol_display = self._format_symbol(data.symbol)
        width = self.style.symbol_width
        text.append(f"{symbol_display:<{width}}", style="bold white")

        # Change percentage
        change_style = COLORS["long"] if data.change_pct >= 0 else COLORS["short"]
        sign = "+" if data.change_pct >= 0 else ""
        text.append(f"{sign}{data.change_pct:.1f}%  ", style=change_style)

        return text

    def _render_pending_status(self) -> Text:
        """Render pending status."""
        text = Text()
        text.append(f"{ICONS['pending']} Pending", style=COLORS["pending"])
        return text

    def _render_analyzing_status(self, data: MoverRowData) -> Text:
        """Render analyzing status with phase progress."""
        text = Text()
        text.append(f"{ICONS['running']} Analysis", style=COLORS["running"])

        if self.style.show_progress and data.stage_detail:
            # Progress indicator for phase
            if data.stage_detail in self.PHASES:
                idx = self.PHASES.index(data.stage_detail)
                bar = "[green]" + ICONS["running"] * (idx + 1) + "[/green]"
                bar += "[dim]" + ICONS["pending"] * (len(self.PHASES) - idx - 1) + "[/dim]"
                text.append(f"    [{bar}] {data.stage_detail}", style="dim cyan")
            else:
                text.append(f"    {data.stage_detail}", style="dim cyan")

        return text

    def _render_complete_status(self, data: MoverRowData) -> Text:
        """Render complete status with result."""
        text = Text()

        if data.result == "EXECUTED":
            text.append(f"{ICONS['complete']} EXECUTED", style=COLORS["success"])
            if data.entry_price:
                text.append(f"    @ ${data.entry_price:,.2f}", style="dim")
        elif data.result == "NO_TRADE":
            text.append(f"{ICONS['complete']} NO_TRADE", style=COLORS["neutral"])
            if data.confidence:
                text.append(f"    ({data.confidence} conf)", style="dim")
        elif data.result == "REJECTED":
            text.append(f"{ICONS['error']} REJECTED", style=COLORS["error"])
        else:
            text.append(f"{ICONS['complete']} {data.result or 'DONE'}", style=COLORS["neutral"])

        return text

    def render(self, data: MoverRowData) -> Text:
        """
        Render a mover row.

        Args:
            data: The mover data to render.

        Returns:
            Rich Text object for the row.
        """
        text = Text()

        # Direction icon
        if self.style.show_icon:
            text.append_text(self._render_direction_icon(data.direction))

        # Symbol and change
        text.append_text(self._render_symbol_and_change(data))

        # Status-specific rendering
        if data.status == "pending":
            text.append_text(self._render_pending_status())
        elif data.status == "analyzing":
            text.append_text(self._render_analyzing_status(data))
        elif data.status == "complete":
            text.append_text(self._render_complete_status(data))

        return text

    def render_compact(self, data: MoverRowData) -> Text:
        """
        Render a compact version of the mover row.

        Args:
            data: The mover data to render.

        Returns:
            Rich Text object for the compact row.
        """
        text = Text()

        # Direction icon
        if data.direction == "gainer":
            text.append(ICONS['long'], style=COLORS["long"])
        else:
            text.append(ICONS['short'], style=COLORS["short"])

        # Symbol (short)
        symbol = self._format_symbol(data.symbol)[:4]
        text.append(f" {symbol} ", style="bold")

        # Status indicator
        if data.status == "complete":
            if data.result == "EXECUTED":
                text.append(ICONS['complete'], style="green")
            elif data.result == "REJECTED":
                text.append(ICONS['error'], style="red")
            else:
                text.append(ICONS['skipped'], style="dim")
        elif data.status == "analyzing":
            text.append(ICONS['running'], style="yellow")
        else:
            text.append(ICONS['pending'], style="dim")

        return text
