"""CLI interface for the trading agent."""
import asyncio
import click
from rich.console import Console
from rich.table import Table
from dotenv import load_dotenv
import os

from trading_agent import TradingAgent
from database.operations import TradingDatabase
from pathlib import Path

load_dotenv()
console = Console()

@click.group()
def cli():
    """Bybit Trading Analysis Agent powered by Claude Agent SDK."""
    pass

@cli.command()
@click.option('--symbol', default='BTC/USDT', help='Trading pair symbol')
@click.option('--interval', default=300, help='Analysis interval in seconds')
def monitor(symbol, interval):
    """Start continuous market monitoring."""
    async def run():
        agent = TradingAgent(symbol=symbol)
        await agent.initialize()
        await agent.continuous_monitor(interval_seconds=interval)

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitoring stopped by user[/yellow]")

@cli.command()
@click.option('--symbol', default='BTC/USDT', help='Trading pair symbol')
@click.argument('query', required=False)
def analyze(symbol, query):
    """Run a single market analysis."""
    async def run():
        agent = TradingAgent(symbol=symbol)
        await agent.initialize()
        await agent.analyze_market(query=query)

    asyncio.run(run())

@cli.command()
@click.option('--symbol', default=None, help='Filter by symbol')
@click.option('--limit', default=10, help='Number of signals to show')
def signals(symbol, limit):
    """View recent trading signals from database."""
    async def run():
        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))
        db = TradingDatabase(db_path)

        if symbol:
            signals_data = await db.get_recent_signals(symbol, limit)
        else:
            # Default to BTC/USDT if no symbol specified
            signals_data = await db.get_recent_signals("BTC/USDT", limit)

        if not signals_data:
            console.print("[yellow]No signals found[/yellow]")
            return

        table = Table(title=f"Recent Trading Signals{f' for {symbol}' if symbol else ''}")
        table.add_column("Time", style="cyan")
        table.add_column("Symbol", style="magenta")
        table.add_column("Signal", style="green")
        table.add_column("Confidence", style="yellow")
        table.add_column("Price", style="blue")
        table.add_column("Timeframe")

        for sig in signals_data:
            table.add_row(
                str(sig['timestamp']),
                sig['symbol'],
                sig['signal_type'],
                f"{sig['confidence']:.1%}",
                f"${sig['price']:.2f}",
                sig['timeframe']
            )

        console.print(table)

    asyncio.run(run())

@cli.command()
@click.option('--symbol', default='BTC/USDT', help='Trading pair symbol')
def status(symbol):
    """Show current portfolio status."""
    async def run():
        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))
        db = TradingDatabase(db_path)

        position = await db.get_portfolio_position(symbol)

        if not position:
            console.print(f"[yellow]No position found for {symbol}[/yellow]")
            return

        table = Table(title=f"Portfolio Status for {symbol}")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Position Type", str(position.get('position_type', 'N/A')))
        table.add_row("Entry Price", f"${position.get('entry_price', 0):.2f}")
        table.add_row("Current Price", f"${position.get('current_price', 0):.2f}")
        table.add_row("Quantity", str(position.get('quantity', 0)))
        table.add_row("Unrealized P&L", f"${position.get('unrealized_pnl', 0):.2f}")
        table.add_row("Stop Loss", f"${position.get('stop_loss', 0):.2f}")
        table.add_row("Take Profit", f"${position.get('take_profit', 0):.2f}")

        console.print(table)

    asyncio.run(run())

if __name__ == '__main__':
    cli()
