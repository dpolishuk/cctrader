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
        try:
            await agent.continuous_monitor(interval_seconds=interval)
        finally:
            await agent.cleanup()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitoring stopped by user[/yellow]")

@cli.command()
@click.option('--symbol', default='BTC/USDT', help='Trading pair symbol')
@click.option('--show-tokens', is_flag=True, help='Display token usage metrics')
@click.argument('query', required=False)
def analyze(symbol, show_tokens, query):
    """Run a single market analysis."""
    async def run():
        agent = TradingAgent(symbol=symbol)
        await agent.initialize()
        try:
            await agent.analyze_market(query=query)

            # Display token usage if requested
            if show_tokens and agent.token_tracker:
                from src.agent.tracking.display import TokenDisplay

                display = TokenDisplay()
                session_stats = await agent.token_tracker.get_session_stats()
                rate_limits = await agent.token_tracker.get_rate_limit_status()

                # Get last usage record for current request
                # Use session stats to display aggregate info
                current_request = {
                    'tokens_input': session_stats.get('total_tokens_input', 0),
                    'tokens_output': session_stats.get('total_tokens_output', 0),
                    'cost': session_stats.get('total_cost_usd', 0.0)
                }

                display.display_usage_panel(current_request, session_stats, rate_limits)
        finally:
            await agent.cleanup()

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

        from src.agent.database.paper_schema import init_paper_trading_db
        from src.agent.database.paper_operations import PaperTradingDatabase

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

        from src.agent.paper_trading.portfolio_manager import PaperPortfolioManager
        from src.agent.paper_trading.audit_dashboard import AuditDashboard
        from src.agent.database.paper_operations import PaperTradingDatabase

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

        from src.agent.paper_trading.portfolio_manager import PaperPortfolioManager

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
        from src.agent.tools.market_data import get_exchange
        from src.agent.paper_trading.portfolio_manager import PaperPortfolioManager
        from src.agent.database.paper_operations import PaperTradingDatabase
        from src.agent.database.paper_schema import init_paper_trading_db
        from src.agent.database.movers_schema import create_movers_tables
        from src.agent.scanner.main_loop import MarketMoversScanner
        from src.agent.config import config
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
        from claude_agent_sdk import ClaudeAgentOptions, create_sdk_mcp_server
        from src.agent.scanner.agent_wrapper import AgentWrapper
        from src.agent.tools.market_data import fetch_market_data, get_current_price
        from src.agent.tools.technical_analysis import (
            analyze_technicals,
            multi_timeframe_analysis,
            analyze_trend,
            analyze_momentum,
            analyze_volatility,
            analyze_patterns
        )
        from src.agent.tools.sentiment import analyze_market_sentiment, detect_market_events
        from src.agent.scanner.tools import submit_trading_signal, fetch_technical_snapshot, fetch_sentiment_data
        from src.agent.tracking.token_tracker import TokenTracker
        from src.agent.database.token_schema import create_token_tracking_tables
        import aiosqlite

        # Create MCP server with ONLY bundled tools for scanner agent
        # Individual tools removed to prevent timeout issues from sequential calls
        trading_tools_server = create_sdk_mcp_server(
            name="trading_tools",
            version="1.0.0",
            tools=[
                # Scanner bundled tools only
                fetch_technical_snapshot,
                fetch_sentiment_data,
                submit_trading_signal,
                # New technical analysis tools
                analyze_trend,
                analyze_momentum,
                analyze_volatility,
                analyze_patterns,
            ]
        )

        agent_options = ClaudeAgentOptions(
            # MCP servers
            mcp_servers={
                "trading": trading_tools_server,
                # OpenWebSearch MCP is available via environment
            },

            # Allowed tools - scanner uses only bundled tools
            allowed_tools=[
                "mcp__trading__fetch_technical_snapshot",
                "mcp__trading__fetch_sentiment_data",
                "mcp__trading__submit_trading_signal",
                "mcp__trading__analyze_trend",
                "mcp__trading__analyze_momentum",
                "mcp__trading__analyze_volatility",
                "mcp__trading__analyze_patterns",
                "mcp__web-search__search",  # Used internally by fetch_sentiment_data
            ],

            # ORIGINAL PROMPT (backup before optimization)
            # Removed 2025-11-19 due to timeout issues (sequential execution)
            # If new prompt fails, restore this version:
            #
            # system_prompt="""You are an expert cryptocurrency trading analysis agent for market movers scanning.
            #
            # Your mission: Analyze high-momentum market movers (5%+ moves) to identify high-probability trading opportunities.
            #
            # Analysis workflow:
            # 1. Gather multi-timeframe technical data (1m, 5m, 15m, 1h, 4h)
            # 2. Analyze market sentiment and detect catalysts using web search
            # 3. Evaluate liquidity and volume quality
            # 4. Assess BTC correlation
            # 5. Calculate 4-component confidence score:
            #    - Technical alignment: 0-40 points
            #    - Sentiment: 0-30 points
            #    - Liquidity: 0-20 points
            #    - BTC correlation: 0-10 points
            #
            # Scoring guidelines:
            # - Only recommend trades with total confidence ≥ 60
            # - Be conservative - high confidence requires strong alignment across ALL factors
            # - Technical: aligned signals across multiple timeframes
            # - Sentiment: clear catalysts, positive news flow, no major risks
            # - Liquidity: sufficient volume, tight spreads, no manipulation signs
            # - Correlation: favorable BTC relationship for the trade direction
            #
            # CRITICAL: Call submit_trading_signal() as your FINAL step with all analysis results.
            # This is REQUIRED - your analysis is not complete until you call this tool."""

            # System prompt for scanner agent
            system_prompt="""You are an expert cryptocurrency trading analysis agent for market movers scanning.

Your mission: Analyze high-momentum market movers (5%+ moves) to identify high-probability trading opportunities.

Analysis workflow:
1. Gather ALL data first:
   - fetch_technical_snapshot: Returns 15m/1h/4h data + current price in ONE call
   - fetch_sentiment_data: Returns sentiment query + web search results in ONE call

2. Calculate 4-component confidence score (0-100):
   - Technical alignment: 0-40 points (15m/1h/4h alignment?)
   - Sentiment: 0-30 points (catalysts from web results?)
   - Liquidity: 0-20 points (volume quality from technical data?)
   - Correlation: 0-10 points (BTC relationship?)

3. IMMEDIATELY call submit_trading_signal() with all 10 parameters
   - Include: confidence, entry_price, stop_loss, tp1, technical_score,
     sentiment_score, liquidity_score, correlation_score, symbol, analysis
   - Do NOT add extra reasoning after calculating confidence

Scoring guidelines:
- Only recommend trades with confidence ≥ 60
- Be conservative - require alignment across ALL factors
- Technical: Aligned trend across 15m/1h/4h timeframes
- Sentiment: Clear catalysts from web results
- Liquidity: Sufficient volume, no manipulation signs
- Correlation: BTC relationship supports trade direction

CRITICAL REQUIREMENTS:
1. Each data tool should only be called ONCE
2. If a tool returns warnings, use available data - do NOT retry
3. You MUST call submit_trading_signal() as your FINAL step
4. Your analysis is NOT complete until you call submit_trading_signal()

Speed target: Complete analysis in under 30 seconds.""",

            # Model and limits
            model="claude-sonnet-4-5",
            max_turns=10,
            max_budget_usd=0.50,  # Conservative per-analysis budget

            # Streaming
            include_partial_messages=True,
        )

        # Initialize session manager for Claude Agent SDK sessions
        from src.agent.session_manager import SessionManager
        session_manager = SessionManager(db_path)
        await session_manager.init_db()

        # Initialize token tracking if enabled
        token_tracker = None
        if config.TOKEN_TRACKING_ENABLED:
            # Ensure token tracking tables exist
            async with aiosqlite.connect(db_path) as conn:
                await create_token_tracking_tables(conn)
                await conn.commit()

            # Initialize tracker
            token_tracker = TokenTracker(
                db_path=db_path,
                operation_mode="scanner"
            )
            await token_tracker.start_session()
            console.print(f"[green]✅ Token tracking enabled - Session: {token_tracker.session_id}[/green]")

        agent = AgentWrapper(
            agent_options,
            token_tracker=token_tracker,
            session_manager=session_manager,
            operation_type=SessionManager.SCANNER
        )

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
        finally:
            # End token tracking session
            if token_tracker:
                await token_tracker.end_session()
                console.print("[green]✅ Token tracking session ended[/green]")

    try:
        asyncio.run(run_scanner())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.error(f"Scanner error: {e}", exc_info=True)

@cli.command()
@click.option('--period', type=click.Choice(['hourly', 'daily', 'session']), default='daily')
@click.option('--session-id', default=None, help='Specific session ID')
def token_stats(period, session_id):
    """View token usage statistics."""
    async def run():
        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))

        from src.agent.database.token_operations import TokenDatabase
        from src.agent.tracking.display import TokenDisplay

        token_db = TokenDatabase(db_path)
        display = TokenDisplay()

        if session_id:
            # Show specific session
            session = await token_db.get_session(session_id)
            if not session:
                console.print(f"[yellow]Session {session_id} not found[/yellow]")
                return

            display.display_stats_table(session)
        elif period == 'hourly':
            stats = await token_db.get_hourly_usage()
            console.print("[bold]Last Hour Usage[/bold]")
            display.display_stats_table(stats)
        elif period == 'daily':
            stats = await token_db.get_daily_usage()
            console.print("[bold]Last 24 Hours Usage[/bold]")
            display.display_stats_table(stats)

    asyncio.run(run())


@cli.command()
def token_limits():
    """Show rate limit status."""
    async def run():
        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))

        from src.agent.database.token_operations import TokenDatabase
        from src.agent.tracking.display import TokenDisplay
        from agent.config import config

        token_db = TokenDatabase(db_path)
        display = TokenDisplay()

        hourly_usage = await token_db.get_hourly_usage()
        daily_usage = await token_db.get_daily_usage()

        rate_limits = {
            'hourly': {
                'request_count': hourly_usage['request_count'],
                'limit': config.CLAUDE_HOURLY_LIMIT,
                'percentage': (hourly_usage['request_count'] / config.CLAUDE_HOURLY_LIMIT) * 100
            },
            'daily': {
                'request_count': daily_usage['request_count'],
                'limit': config.CLAUDE_DAILY_LIMIT,
                'percentage': (daily_usage['request_count'] / config.CLAUDE_DAILY_LIMIT) * 100
            }
        }

        table = Table(title="Claude Code Rate Limit Status")
        table.add_column("Period", style="cyan")
        table.add_column("Usage", style="yellow")
        table.add_column("Limit", style="blue")
        table.add_column("Percentage", style="magenta")

        for period_name, period_data in rate_limits.items():
            pct = period_data['percentage']
            color = "red" if pct >= 80 else "yellow" if pct >= 50 else "green"

            table.add_row(
                period_name.capitalize(),
                f"{period_data['request_count']:,}",
                f"{period_data['limit']:,}",
                f"[{color}]{pct:.1f}%[/{color}]"
            )

        display.console.print(table)

    asyncio.run(run())


@cli.command()
def fetch_limits():
    """Fetch current Claude Code rate limits from documentation."""
    async def run():
        from src.agent.tracking.limit_fetcher import fetch_current_limits_from_docs, compare_with_current_config
        from src.agent.config import config

        console.print("[cyan]Fetching current Claude Code rate limits...[/cyan]")

        limits = await fetch_current_limits_from_docs()

        if not limits:
            console.print("[yellow]Could not fetch limits from documentation[/yellow]")
            console.print("Using current config values:")
            console.print(f"  CLAUDE_HOURLY_LIMIT={config.CLAUDE_HOURLY_LIMIT}")
            console.print(f"  CLAUDE_DAILY_LIMIT={config.CLAUDE_DAILY_LIMIT}")
            return

        comparison = compare_with_current_config(
            limits,
            config.CLAUDE_HOURLY_LIMIT,
            config.CLAUDE_DAILY_LIMIT
        )

        console.print(f"[green]✓[/green] Fetched from {limits['source']}")
        console.print(f"Last updated: {limits.get('last_updated', 'unknown')}")
        console.print()

        table = Table(title="Rate Limit Comparison")
        table.add_column("Limit", style="cyan")
        table.add_column("Current Config", style="yellow")
        table.add_column("Documentation", style="green")

        table.add_row(
            "Hourly",
            str(comparison['current']['hourly']),
            str(comparison['fetched']['hourly'])
        )
        table.add_row(
            "Daily",
            str(comparison['current']['daily']),
            str(comparison['fetched']['daily'])
        )

        console.print(table)

        if comparison['needs_update']:
            console.print()
            console.print("[yellow]⚠ Configuration update recommended:[/yellow]")
            console.print()
            console.print("Add to .env:")
            for key, value in comparison['recommendations'].items():
                console.print(f"  {key}={value}")
        else:
            console.print()
            console.print("[green]✓ Configuration is up to date[/green]")

    asyncio.run(run())


@cli.command()
@click.option('--clear', 'clear_sessions', is_flag=True, help='Clear all sessions')
@click.option('--clear-type', default=None, help='Clear specific operation type (scanner, analysis, etc.)')
def sessions(clear_sessions, clear_type):
    """Manage Claude Agent SDK sessions."""
    async def run():
        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))

        from src.agent.session_manager import SessionManager

        manager = SessionManager(db_path)
        await manager.init_db()

        if clear_sessions:
            await manager.clear_all_sessions()
            console.print("[green]✅ Cleared all sessions[/green]")
        elif clear_type:
            await manager.clear_session(clear_type)
            console.print(f"[green]✅ Cleared {clear_type} session[/green]")
        else:
            # List sessions
            sessions_data = await manager.list_sessions()

            if not sessions_data:
                console.print("[yellow]No active sessions[/yellow]")
                return

            table = Table(title="Claude Agent SDK Sessions")
            table.add_column("Operation Type", style="cyan")
            table.add_column("Session ID", style="green")
            table.add_column("Created", style="blue")
            table.add_column("Last Used", style="yellow")

            for op_type, info in sessions_data.items():
                table.add_row(
                    op_type,
                    info['session_id'][:16] + '...',  # Truncate for display
                    info['created_at'],
                    info['last_used_at']
                )

            console.print(table)
            console.print(f"\n[dim]Total sessions: {len(sessions_data)}[/dim]")
            console.print("[dim]Use --clear-type <type> to clear a specific session[/dim]")
            console.print("[dim]Use --clear to clear all sessions[/dim]")

    asyncio.run(run())


@cli.command()
@click.option('--session-id', default=None, help='Session ID to show intervals for')
@click.option('--limit', default=10, help='Number of recent sessions to show')
def token_intervals(session_id, limit):
    """Show token usage intervals for sessions."""
    async def run():
        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))

        from src.agent.database.token_operations import TokenDatabase
        from src.agent.tracking.interval_display import display_interval_summary
        from src.agent.config import config

        db = TokenDatabase(db_path)

        if session_id:
            # Show specific session intervals
            intervals = await db.get_session_intervals(session_id, config.TOKEN_INTERVAL_MINUTES)

            if not intervals:
                console.print(f"[yellow]Session {session_id} not found or has no data[/yellow]")
                return

            display_interval_summary(intervals)
        else:
            # List recent sessions
            sessions = await db.get_recent_sessions(limit)

            if not sessions:
                console.print("[yellow]No completed sessions found[/yellow]")
                return

            table = Table(title="Recent Token Tracking Sessions", show_header=True)
            table.add_column("Session ID", style="cyan")
            table.add_column("Started", style="blue")
            table.add_column("Duration", style="green")
            table.add_column("Tokens", justify="right", style="green")
            table.add_column("Cost", justify="right", style="yellow")

            for session in sessions:
                duration_str = f"{int(session['duration_seconds'] // 60)}:{int(session['duration_seconds'] % 60):02d}"
                table.add_row(
                    session['session_id'][:12] + "...",
                    session['start_time'][:19],
                    duration_str,
                    f"{session['total_tokens']:,}",
                    f"${session['total_cost_usd']:.4f}"
                )

            console.print("\n")
            console.print(table)
            console.print("\n[dim]Use --session-id to see 5-minute interval breakdown[/dim]\n")

    asyncio.run(run())


if __name__ == '__main__':
    cli()
