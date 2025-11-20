"""Display utilities for token interval summaries."""
from typing import List, Dict, Any
from rich.console import Console
from rich.table import Table


def display_interval_summary(intervals: List[Dict[str, Any]], current_interval: Dict[str, Any] = None,
                             current_duration: float = 0) -> None:
    """
    Display summary table of token intervals.

    Args:
        intervals: List of completed interval data dicts
        current_interval: Optional current partial interval
        current_duration: Duration of current interval in seconds
    """
    if not intervals and not current_interval:
        return

    console = Console()
    table = Table(title="Token Usage by 5-Minute Intervals", show_header=True, header_style="bold cyan")

    table.add_column("Interval", style="cyan", justify="center")
    table.add_column("Duration", style="blue", justify="center")
    table.add_column("Tokens (in)", justify="right", style="green")
    table.add_column("Tokens (out)", justify="right", style="green")
    table.add_column("Total", justify="right", style="bold green")
    table.add_column("Cost", justify="right", style="yellow")

    total_tokens_in = 0
    total_tokens_out = 0
    total_cost = 0.0
    total_duration = 0.0

    # Add completed intervals
    for interval in intervals:
        duration_str = _format_duration(interval['duration_seconds'])
        table.add_row(
            str(interval['interval_number']),
            duration_str,
            f"{interval['tokens_input']:,}",
            f"{interval['tokens_output']:,}",
            f"{interval['tokens_total']:,}",
            f"${interval['cost']:.4f}"
        )
        total_tokens_in += interval['tokens_input']
        total_tokens_out += interval['tokens_output']
        total_cost += interval['cost']
        total_duration += interval['duration_seconds']

    # Add current partial interval if provided
    if current_interval and current_interval.get('requests', 0) > 0:
        tokens_total = current_interval['tokens_input'] + current_interval['tokens_output']
        interval_num = intervals[-1]['interval_number'] + 1 if intervals else 1
        duration_str = _format_duration(current_duration)
        table.add_row(
            str(interval_num),
            duration_str,
            f"{current_interval['tokens_input']:,}",
            f"{current_interval['tokens_output']:,}",
            f"{tokens_total:,}",
            f"${current_interval['cost']:.4f}"
        )
        total_tokens_in += current_interval['tokens_input']
        total_tokens_out += current_interval['tokens_output']
        total_cost += current_interval['cost']
        total_duration += current_duration

    # Add totals row
    if intervals or (current_interval and current_interval.get('requests', 0) > 0):
        table.add_section()
        total_tokens = total_tokens_in + total_tokens_out
        table.add_row(
            "[bold]TOTAL[/bold]",
            f"[bold]{_format_duration(total_duration)}[/bold]",
            f"[bold]{total_tokens_in:,}[/bold]",
            f"[bold]{total_tokens_out:,}[/bold]",
            f"[bold]{total_tokens:,}[/bold]",
            f"[bold]${total_cost:.4f}[/bold]"
        )

    console.print("\n")
    console.print(table)
    console.print("\n")


def _format_duration(seconds: float) -> str:
    """Format duration in seconds to MM:SS format."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"
