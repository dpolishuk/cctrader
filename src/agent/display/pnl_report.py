"""P&L Report Display Functionality."""
from rich.table import Table
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


def format_currency(value: float) -> str:
    """Format a float value as currency with commas and 2 decimal places."""
    if value < 0:
        return f"-${abs(value):,.2f}"
    return f"${value:,.2f}"


def format_percentage(value: float) -> str:
    """Format a float value as percentage with 1 decimal place."""
    return f"{value:.1f}%"


def create_pnl_table(data: List[Dict[str, Any]]) -> Table:
    """
    Create a Rich table for P&L data.

    Args:
        data: List of symbol P&L dicts

    Returns:
        Rich Table object
    """
    table = Table(title="P&L by Symbol", show_header=True, header_style="bold")

    # Add columns
    table.add_column("Symbol", style="cyan", no_wrap=True)
    table.add_column("Total P&L", justify="right")
    table.add_column("Realized", justify="right")
    table.add_column("Unrealized", justify="right")
    table.add_column("Trades", justify="right")
    table.add_column("Win Rate", justify="right")
    table.add_column("Avg P&L", justify="right")

    if not data:
        return table

    # Calculate totals
    total_pnl = sum(row['total_pnl'] for row in data)
    total_realized = sum(row['realized_pnl'] for row in data)
    total_unrealized = sum(row['unrealized_pnl'] for row in data)
    total_trades = sum(row['trade_count'] for row in data)

    # Calculate overall win rate and avg P&L
    total_wins = sum(
        row['trade_count'] * row['win_rate'] / 100
        for row in data
        if row['trade_count'] > 0
    )
    overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
    overall_avg_pnl = (total_realized / total_trades) if total_trades > 0 else 0

    # Add data rows
    for row in data:
        # Color code based on P&L
        total_style = "green" if row['total_pnl'] >= 0 else "red"
        realized_style = "green" if row['realized_pnl'] >= 0 else "red"
        unrealized_style = "green" if row['unrealized_pnl'] >= 0 else "red"
        avg_style = "green" if row['avg_pnl'] >= 0 else "red"

        # Yellow warning for low win rate
        win_rate_style = "yellow" if row['win_rate'] < 50 and row['trade_count'] > 0 else "white"

        table.add_row(
            row['symbol'],
            Text(format_currency(row['total_pnl']), style=total_style),
            Text(format_currency(row['realized_pnl']), style=realized_style),
            Text(format_currency(row['unrealized_pnl']), style=unrealized_style),
            str(row['trade_count']),
            Text(format_percentage(row['win_rate']), style=win_rate_style),
            Text(format_currency(row['avg_pnl']), style=avg_style)
        )

    # Add total row
    total_style = "bold green" if total_pnl >= 0 else "bold red"
    table.add_section()
    table.add_row(
        Text("TOTAL", style="bold"),
        Text(format_currency(total_pnl), style=total_style),
        Text(format_currency(total_realized), style="bold"),
        Text(format_currency(total_unrealized), style="bold"),
        Text(str(total_trades), style="bold"),
        Text(format_percentage(overall_win_rate), style="bold"),
        Text(format_currency(overall_avg_pnl), style="bold")
    )

    return table
