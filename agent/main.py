"""CLI interface for the trading agent."""
import asyncio
import click
from rich.console import Console
from rich.table import Table
from dotenv import load_dotenv
import os
import logging

from .trading_agent import TradingAgent
from .database.operations import TradingDatabase
from pathlib import Path

load_dotenv()
console = Console()
logger = logging.getLogger(__name__)

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

@cli.command()
@click.option('--interval', default=300, help='Scan interval in seconds')
@click.option('--portfolio', default='Market Movers', help='Paper trading portfolio name')
def scan_movers(interval, portfolio):
    """Run market movers scanner - detects and analyzes 5%+ movers."""
    async def run_scanner():
        from agent.tools.market_data import get_exchange
        from agent.paper_trading.portfolio_manager import PaperPortfolioManager
        from agent.database.paper_operations import PaperTradingDatabase
        from agent.database.paper_schema import init_paper_trading_db
        from agent.database.movers_schema import create_movers_tables
        from agent.scanner.main_loop import MarketMoversScanner
        from agent.config import config
        import aiosqlite

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        console.print("[bold green]🚀 Starting Market Movers Scanner[/bold green]")
        console.print(f"Scan interval: {interval}s")
        console.print(f"Portfolio: {portfolio}")

        # Initialize database
        db_path = Path(config.DB_PATH)
        await init_paper_trading_db(db_path)

        # Create movers tables
        async with aiosqlite.connect(db_path) as conn:
            await create_movers_tables(conn)
            await conn.commit()

        db = PaperTradingDatabase(db_path)

        # Get or create portfolio
        portfolio_data = await db.get_portfolio_by_name(portfolio)

        if not portfolio_data:
            console.print(f"[yellow]Creating new portfolio '{portfolio}'...[/yellow]")
            portfolio_id = await db.create_portfolio(
                name=portfolio,
                starting_capital=10000.0,
                execution_mode='realistic'
            )
            console.print(f"[green]✅ Portfolio created (ID: {portfolio_id})[/green]")
        else:
            portfolio_id = portfolio_data['id']
            console.print(f"[green]✅ Using existing portfolio (ID: {portfolio_id})[/green]")

        # Initialize portfolio manager
        manager = PaperPortfolioManager(db_path, portfolio)
        await manager.initialize()

        # Initialize exchange
        exchange = get_exchange()

        # Create agent wrapper
        from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
        from agent.scanner.agent_wrapper import AgentWrapper

        agent_options = ClaudeAgentOptions(
            max_turns=20,
            max_budget_usd=1.0
        )
        claude_client = ClaudeSDKClient(options=agent_options)
        agent = AgentWrapper(claude_client)

        # Create and start scanner
        scanner = MarketMoversScanner(
            exchange=exchange,
            agent=agent,
            portfolio=manager,
            db=db
        )

        scanner.config.scan_interval_seconds = interval

        console.print("[bold cyan]Scanner initialized. Press Ctrl+C to stop.[/bold cyan]")

        try:
            await scanner.start()
        except KeyboardInterrupt:
            scanner.stop()
            console.print("\n[yellow]Scanner stopped by user[/yellow]")

    try:
        asyncio.run(run_scanner())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.error(f"Scanner error: {e}", exc_info=True)

if __name__ == '__main__':
    cli()
