"""CLI interface for the trading agent."""
import asyncio
import click
from rich.console import Console
from rich.table import Table
from dotenv import load_dotenv
import os

from .trading_agent import TradingAgent
from .database.operations import TradingDatabase
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

@cli.command()
@click.option('--name', required=True, help='Portfolio name')
@click.option('--capital', default=100000.0, help='Starting capital')
@click.option('--mode', default='realistic', type=click.Choice(['instant', 'realistic', 'historical']))
def create_portfolio(name, capital, mode):
    """Create a new paper trading portfolio."""
    async def run():
        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))

        from agent.database.paper_schema import init_paper_trading_db
        from agent.database.paper_operations import PaperTradingDatabase

        await init_paper_trading_db(db_path)

        db = PaperTradingDatabase(db_path)
        portfolio_id = await db.create_portfolio(
            name=name,
            starting_capital=capital,
            execution_mode=mode
        )

        console.print(f"[green]✅ Created paper portfolio '{name}' (ID: {portfolio_id})[/green]")
        console.print(f"Starting capital: ${capital:,.2f}")
        console.print(f"Execution mode: {mode}")

    asyncio.run(run())

@cli.command()
@click.option('--name', required=True, help='Portfolio name')
def paper_status(name):
    """Show paper trading portfolio status."""
    async def run():
        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))

        from agent.paper_trading.portfolio_manager import PaperPortfolioManager
        from agent.paper_trading.audit_dashboard import AuditDashboard
        from agent.database.paper_operations import PaperTradingDatabase

        manager = PaperPortfolioManager(db_path, name)
        await manager.initialize()

        db = PaperTradingDatabase(db_path)
        dashboard = AuditDashboard(db, manager.portfolio_id)
        await dashboard.display_dashboard()

    asyncio.run(run())

@cli.command()
@click.option('--symbol', default='BTC/USDT', help='Trading pair symbol')
@click.option('--portfolio', default='default', help='Paper trading portfolio name')
@click.option('--interval', default=300, help='Analysis interval in seconds')
def paper_monitor(symbol, portfolio, interval):
    """Start continuous monitoring in paper trading mode."""
    async def run():
        agent = TradingAgent(
            symbol=symbol,
            paper_trading=True,
            paper_portfolio=portfolio
        )
        await agent.initialize()
        await agent.continuous_monitor(interval_seconds=interval)

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Paper trading monitoring stopped[/yellow]")

@cli.command()
@click.option('--portfolio', required=True, help='Portfolio name')
def reset_breaker(portfolio):
    """Reset circuit breaker for a portfolio."""
    async def run():
        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))

        from agent.paper_trading.portfolio_manager import PaperPortfolioManager

        manager = PaperPortfolioManager(db_path, portfolio)
        await manager.initialize()

        await manager.risk_manager.reset_circuit_breaker()

        console.print(f"[green]✅ Circuit breaker reset for portfolio '{portfolio}'[/green]")

    asyncio.run(run())

if __name__ == '__main__':
    cli()
