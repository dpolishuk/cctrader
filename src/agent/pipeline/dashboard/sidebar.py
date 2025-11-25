# src/agent/pipeline/dashboard/sidebar.py
"""Sidebar components for pipeline dashboard."""
from typing import Dict, Any, Optional
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Group

from .styles import COLORS, ICONS


class SidebarRenderer:
    """Renders sidebar panels for portfolio and stats."""

    def render_portfolio(self, state: Dict[str, Any]) -> Panel:
        """
        Render portfolio status panel.

        Args:
            state: Portfolio state dict with equity, positions, exposure, pnl

        Returns:
            Rich Panel with portfolio information
        """
        table = Table.grid(padding=(0, 1))
        table.add_column(style=COLORS["label"], justify="right")
        table.add_column(style=COLORS["value"], justify="left")

        # Equity
        equity = state.get("equity", 0)
        table.add_row("Equity:", f"${equity:,.2f}")

        # Open positions
        positions = state.get("open_positions", 0)
        table.add_row("Positions:", str(positions))

        # Exposure
        exposure = state.get("current_exposure_pct", 0)
        exp_color = COLORS["warning"] if exposure > 20 else COLORS["value"]
        table.add_row("Exposure:", Text(f"{exposure:.1f}%", style=exp_color))

        # Daily P&L
        daily = state.get("daily_pnl_pct", 0)
        daily_color = COLORS["bullish"] if daily >= 0 else COLORS["bearish"]
        table.add_row("Daily:", Text(f"{daily:+.2f}%", style=daily_color))

        # Weekly P&L
        weekly = state.get("weekly_pnl_pct", 0)
        weekly_color = COLORS["bullish"] if weekly >= 0 else COLORS["bearish"]
        table.add_row("Weekly:", Text(f"{weekly:+.2f}%", style=weekly_color))

        return Panel(
            table,
            title="[bold]PORTFOLIO[/bold]",
            border_style=COLORS["muted"],
            padding=(0, 1)
        )

    def render_agent_stats(self, stats: Dict[str, Any]) -> Panel:
        """
        Render agent statistics panel.

        Args:
            stats: Statistics dict with analyzed, approved, executed, win_rate

        Returns:
            Rich Panel with agent statistics
        """
        table = Table.grid(padding=(0, 1))
        table.add_column(style=COLORS["label"], justify="right")
        table.add_column(style=COLORS["value"], justify="left")

        # Signals analyzed
        analyzed = stats.get("analyzed", 0)
        table.add_row("Analyzed:", str(analyzed))

        # Approved (may include modified)
        approved = stats.get("approved", 0)
        modified = stats.get("modified", 0)
        if modified > 0:
            table.add_row("Approved:", f"{approved} ({modified} mod)")
        else:
            table.add_row("Approved:", str(approved))

        # Rejected
        rejected = stats.get("rejected", 0)
        rej_color = COLORS["warning"] if rejected > approved else COLORS["value"]
        table.add_row("Rejected:", Text(str(rejected), style=rej_color))

        # Executed
        executed = stats.get("executed", 0)
        table.add_row("Executed:", str(executed))

        # Aborted
        aborted = stats.get("aborted", 0)
        if aborted > 0:
            table.add_row("Aborted:", Text(str(aborted), style=COLORS["warning"]))

        # Win rate
        win_rate = stats.get("win_rate", 0)
        wr_color = COLORS["bullish"] if win_rate >= 50 else COLORS["bearish"]
        table.add_row("Win Rate:", Text(f"{win_rate:.1f}%", style=wr_color))

        return Panel(
            table,
            title="[bold]AGENT STATS[/bold]",
            border_style=COLORS["muted"],
            padding=(0, 1)
        )

    def render_combined_sidebar(
        self,
        portfolio_state: Dict[str, Any],
        agent_stats: Dict[str, Any]
    ) -> Group:
        """
        Render both panels as a combined sidebar.

        Args:
            portfolio_state: Portfolio state dict
            agent_stats: Agent statistics dict

        Returns:
            Rich Group containing both panels
        """
        portfolio_panel = self.render_portfolio(portfolio_state)
        stats_panel = self.render_agent_stats(agent_stats)
        return Group(portfolio_panel, stats_panel)


# Convenience functions
def render_portfolio_panel(state: Dict[str, Any]) -> Panel:
    """Render portfolio status panel."""
    return SidebarRenderer().render_portfolio(state)


def render_agent_stats_panel(stats: Dict[str, Any]) -> Panel:
    """Render agent statistics panel."""
    return SidebarRenderer().render_agent_stats(stats)
