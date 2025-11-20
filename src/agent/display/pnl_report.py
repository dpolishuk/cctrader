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


async def display_pnl_report(
    db: 'PaperTradingDatabase',
    portfolio_name: str,
    period: str = 'all',
    min_trades: int = 1
) -> None:
    """
    Display P&L report with Rich formatting.

    Args:
        db: PaperTradingDatabase instance
        portfolio_name: Name of portfolio
        period: Time period ('all', 'daily', 'weekly', 'monthly')
        min_trades: Minimum trades to include symbol

    Raises:
        ValueError: If portfolio not found
    """
    from src.agent.database.paper_operations import PaperTradingDatabase

    console = Console()

    # Get portfolio
    portfolio = await db.get_portfolio_by_name(portfolio_name)
    if not portfolio:
        raise ValueError(f"Portfolio '{portfolio_name}' not found")

    # Calculate date range based on period
    end_date = datetime.now()
    start_date = None

    if period == 'daily':
        start_date = end_date - timedelta(days=7)
        period_label = "Last 7 Days"
    elif period == 'weekly':
        start_date = end_date - timedelta(weeks=4)
        period_label = "Last 4 Weeks"
    elif period == 'monthly':
        start_date = end_date - timedelta(days=365)
        period_label = "Last 12 Months"
    else:
        period_label = "All Time"

    # Get P&L data
    data = await db.get_symbol_pnl_summary(
        portfolio_id=portfolio['id'],
        start_date=start_date,
        end_date=end_date,
        min_trades=min_trades
    )

    # Display header
    total_pnl = sum(row['total_pnl'] for row in data) if data else 0
    pnl_pct = (total_pnl / portfolio['starting_capital'] * 100) if portfolio['starting_capital'] > 0 else 0

    header_text = f"""[bold]Portfolio:[/bold] {portfolio_name}
[bold]Period:[/bold] {period_label}
[bold]Total P&L:[/bold] {format_currency(total_pnl)} ({format_percentage(pnl_pct)})
[bold]Current Equity:[/bold] {format_currency(portfolio['current_equity'])}"""

    header = Panel(header_text, title="Portfolio P&L Report", border_style="blue")
    console.print(header)
    console.print()

    # Display table
    if not data:
        console.print("[yellow]No trading activity found for this period.[/yellow]")
    else:
        table = create_pnl_table(data)
        console.print(table)
