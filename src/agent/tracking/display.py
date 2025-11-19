"""Rich console display components for token tracking."""
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from typing import Dict, Any


class TokenDisplay:
    """Display token usage metrics in console."""

    def __init__(self, console: Console = None):
        """
        Initialize display.

        Args:
            console: Rich console instance (creates new if None)
        """
        self.console = console or Console()

    def display_usage_panel(
        self,
        current_request: Dict[str, Any],
        session_total: Dict[str, Any],
        rate_limits: Dict[str, Any]
    ):
        """
        Display token usage panel.

        Args:
            current_request: Current request metrics
            session_total: Session totals
            rate_limits: Rate limit status
        """
        # Format current request
        current_text = f"{current_request['tokens_input']:,} in / {current_request['tokens_output']:,} out (${current_request['cost']:.3f})"

        # Format session total
        session_text = f"{session_total['total_tokens_input']:,} in / {session_total['total_tokens_output']:,} out (${session_total['total_cost_usd']:.2f})"

        # Format hourly usage with color coding
        hourly_pct = rate_limits['hourly']['percentage']
        hourly_color = self._get_status_color(hourly_pct)
        hourly_text = f"[{hourly_color}]{rate_limits['hourly']['request_count']:,} requests ({hourly_pct:.0f}% of limit)[/{hourly_color}]"

        # Format daily usage
        daily_pct = rate_limits['daily']['percentage']
        daily_color = self._get_status_color(daily_pct)
        daily_text = f"[{daily_color}]{rate_limits['daily']['request_count']:,} requests ({daily_pct:.0f}% of limit)[/{daily_color}]"

        # Estimate hourly cost
        if session_total['total_requests'] > 0:
            avg_cost = session_total['total_cost_usd'] / session_total['total_requests']
            est_hourly = avg_cost * rate_limits['hourly']['request_count']
        else:
            est_hourly = 0.0

        # Build panel content
        content = f"""Current Request: {current_text}
Session Total:   {session_text}
Hourly Usage:    {hourly_text}
Daily Usage:     {daily_text}
Est. Cost/Hour:  ${est_hourly:.2f}"""

        panel = Panel(
            content,
            title="[bold]Token Usage[/bold]",
            border_style="cyan"
        )

        self.console.print(panel)

    def display_stats_table(self, stats: Dict[str, Any]):
        """
        Display token statistics in table format.

        Args:
            stats: Statistics data
        """
        table = Table(title="Token Usage Statistics")

        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Requests", f"{stats.get('total_requests', 0):,}")
        table.add_row("Input Tokens", f"{stats.get('total_tokens_input', 0):,}")
        table.add_row("Output Tokens", f"{stats.get('total_tokens_output', 0):,}")
        table.add_row("Total Tokens", f"{stats.get('total_tokens', 0):,}")
        table.add_row("Total Cost", f"${stats.get('total_cost_usd', 0):.2f}")

        if stats.get('avg_tokens_per_request'):
            table.add_row("Avg Tokens/Request", f"{stats['avg_tokens_per_request']:,.0f}")

        self.console.print(table)

    def _get_status_color(self, percentage: float) -> str:
        """
        Get color based on percentage threshold.

        Args:
            percentage: Usage percentage

        Returns:
            Color name for Rich markup
        """
        if percentage >= 80:
            return "red"
        elif percentage >= 50:
            return "yellow"
        else:
            return "green"
