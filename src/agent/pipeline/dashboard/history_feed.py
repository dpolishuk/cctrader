# src/agent/pipeline/dashboard/history_feed.py
"""History feed component for pipeline dashboard."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .styles import COLORS, ICONS


@dataclass
class PipelineHistoryEntry:
    """Single entry in pipeline history."""
    symbol: str
    outcome: str  # EXECUTED, NO_TRADE, REJECTED, ABORTED, ERROR
    timestamp: datetime
    detail: Optional[str] = None


# Outcome styling
OUTCOME_STYLES = {
    "EXECUTED": {"color": COLORS["success"], "icon": ICONS["complete"]},
    "NO_TRADE": {"color": COLORS["muted"], "icon": ICONS["pending"]},
    "REJECTED": {"color": COLORS["warning"], "icon": ICONS["warning"]},
    "ABORTED": {"color": COLORS["warning"], "icon": ICONS["warning"]},
    "ERROR": {"color": COLORS["error"], "icon": ICONS["error"]},
}


class HistoryFeed:
    """Manages and renders pipeline history."""

    def __init__(self, max_entries: int = 10):
        """
        Initialize history feed.

        Args:
            max_entries: Maximum number of entries to keep
        """
        self.max_entries = max_entries
        self.entries: List[PipelineHistoryEntry] = []

    def add(self, entry: PipelineHistoryEntry) -> None:
        """
        Add entry to history.

        Args:
            entry: Pipeline history entry
        """
        self.entries.insert(0, entry)  # Add to front (most recent first)
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[:self.max_entries]

    def clear(self) -> None:
        """Clear all entries."""
        self.entries.clear()

    def render(self) -> Panel:
        """
        Render history as a panel with table.

        Returns:
            Rich Panel containing history table
        """
        if not self.entries:
            content = Text("No recent pipeline runs", style=COLORS["muted"])
            return Panel(
                content,
                title="[bold]HISTORY[/bold]",
                border_style=COLORS["muted"],
                padding=(0, 1)
            )

        table = Table.grid(padding=(0, 2))
        table.add_column(style=COLORS["muted"], justify="right")  # Time
        table.add_column(justify="left")  # Symbol
        table.add_column(justify="left")  # Outcome
        table.add_column(style=COLORS["muted"], justify="left")  # Detail

        for entry in self.entries[:5]:  # Show max 5 in table view
            time_str = entry.timestamp.strftime("%H:%M")

            style_info = OUTCOME_STYLES.get(
                entry.outcome,
                {"color": COLORS["muted"], "icon": ICONS["bullet"]}
            )

            outcome_text = Text()
            outcome_text.append(f"{style_info['icon']} ", style=style_info["color"])
            outcome_text.append(entry.outcome, style=style_info["color"])

            detail = entry.detail or ""
            if entry.outcome == "EXECUTED" and entry.detail:
                # Color P&L appropriately
                if entry.detail.startswith("+"):
                    detail_text = Text(detail, style=COLORS["bullish"])
                elif entry.detail.startswith("-"):
                    detail_text = Text(detail, style=COLORS["bearish"])
                else:
                    detail_text = Text(detail, style=COLORS["muted"])
            else:
                detail_text = Text(detail, style=COLORS["muted"])

            table.add_row(
                time_str,
                Text(entry.symbol, style=COLORS["value"]),
                outcome_text,
                detail_text
            )

        return Panel(
            table,
            title="[bold]HISTORY[/bold]",
            border_style=COLORS["muted"],
            padding=(0, 1)
        )

    def render_inline(self, max_items: int = 5, separator: str = " │ ") -> Text:
        """
        Render history as single inline text.

        Args:
            max_items: Maximum items to show
            separator: Separator between entries

        Returns:
            Rich Text with inline history
        """
        if not self.entries:
            return Text("No recent runs", style=COLORS["muted"])

        text = Text()
        text.append("HISTORY: ", style="bold")

        for i, entry in enumerate(self.entries[:max_items]):
            if i > 0:
                text.append(separator, style=COLORS["muted"])

            style_info = OUTCOME_STYLES.get(
                entry.outcome,
                {"color": COLORS["muted"], "icon": ""}
            )

            text.append(entry.symbol, style=COLORS["value"])
            text.append(ICONS["arrow_right"], style=COLORS["muted"])
            text.append(entry.outcome, style=style_info["color"])

            if entry.detail:
                text.append(f" ({entry.detail})", style=COLORS["muted"])

        return text


# Convenience function
def render_history_feed(
    entries: List[PipelineHistoryEntry],
    max_entries: int = 10
) -> Panel:
    """
    Render history feed from list of entries.

    Args:
        entries: List of history entries (sorted by timestamp, most recent first)
        max_entries: Maximum entries to display

    Returns:
        Rich Panel with history
    """
    feed = HistoryFeed(max_entries=max_entries)
    # Add entries in reverse order since feed.add() inserts at position 0
    # This ensures entries with later timestamps end up at position 0
    for entry in reversed(entries):
        feed.add(entry)
    return feed.render()
