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
        from src.agent.session_manager import SessionManager
        from src.agent.cli_banner import show_session_banner
        from src.agent.config import config

        # Initialize session manager
        db_path = Path(config.DB_PATH)
        session_manager = SessionManager(db_path)
        await session_manager.init_db()

        # Display session banner
        await show_session_banner(
            operation_type=SessionManager.MONITOR,
            model=config.CLAUDE_MODEL,
            session_manager=session_manager
        )

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
        from src.agent.session_manager import SessionManager
        from src.agent.cli_banner import show_session_banner
        from src.agent.config import config

        # Initialize session manager
        db_path = Path(config.DB_PATH)
        session_manager = SessionManager(db_path)
        await session_manager.init_db()

        # Display session banner
        await show_session_banner(
            operation_type=SessionManager.ANALYSIS,
            model=config.CLAUDE_MODEL,
            session_manager=session_manager
        )

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
        from src.agent.session_manager import SessionManager
        from src.agent.cli_banner import show_session_banner
        from src.agent.config import config

        # Initialize session manager
        db_path = Path(config.DB_PATH)
        session_manager = SessionManager(db_path)
        await session_manager.init_db()

        # Display session banner
        await show_session_banner(
            operation_type=SessionManager.PAPER_TRADING,
            model=config.CLAUDE_MODEL,
            session_manager=session_manager
        )

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
@click.option('--period', default='all',
              type=click.Choice(['daily', 'weekly', 'monthly', 'all']),
              help='Time period for report (default: all)')
@click.option('--min-trades', default=1, type=int,
              help='Minimum trades per symbol (default: 1)')
def pnl_report(portfolio, period, min_trades):
    """Display P&L report by symbol and time period."""
    async def run():
        from src.agent.display.pnl_report import display_pnl_report
        from src.agent.database.paper_operations import PaperTradingDatabase
        from pathlib import Path
        from src.agent.config import config

        try:
            db = PaperTradingDatabase(Path(config.DB_PATH))
            await display_pnl_report(db, portfolio, period, min_trades)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {str(e)}")
            raise click.Abort()
        except Exception as e:
            console.print(f"[red]Error:[/red] Failed to generate P&L report: {str(e)}")
            logger.exception("P&L report failed")
            raise click.Abort()

    asyncio.run(run())

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
@click.option('--daily', is_flag=True, help='Maintain single session per day (all analyses in one conversation)')
@click.option('--dashboard', is_flag=True, help='Enable visual dashboard for cycle monitoring')
@click.option('--no-sentiment', is_flag=True, help='Disable sentiment analysis (technical-only mode)')
def scan_movers(interval, portfolio, daily, dashboard, no_sentiment):
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

        # Setup logging - use RichHandler when dashboard enabled to avoid display corruption
        if dashboard:
            from rich.logging import RichHandler
            # Remove any existing handlers
            logging.root.handlers = []
            # Use RichHandler that coordinates with Rich's Live display
            rich_handler = RichHandler(
                console=console,
                show_time=True,
                show_path=False,
                markup=True,
                rich_tracebacks=True,
            )
            rich_handler.setFormatter(logging.Formatter("%(message)s"))
            logging.root.addHandler(rich_handler)
            logging.root.setLevel(logging.INFO)
        else:
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
        from claude_agent_sdk import (
            ClaudeAgentOptions,
            create_sdk_mcp_server,
            PermissionResultAllow,
            PermissionResultDeny,
            ToolPermissionContext,
        )
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
        from src.agent.scanner.prompts import build_scanner_system_prompt
        from src.agent.scanner.config import ScannerConfig
        from src.agent.tracking.token_tracker import TokenTracker
        from src.agent.database.token_schema import create_token_tracking_tables
        import aiosqlite

        # Create scanner config with sentiment setting
        use_sentiment = not no_sentiment
        scanner_config = ScannerConfig(use_sentiment=use_sentiment)

        # Build tools list conditionally based on sentiment flag
        scanner_tools = [
            fetch_technical_snapshot,
            submit_trading_signal,
            analyze_trend,
            analyze_momentum,
            analyze_volatility,
            analyze_patterns,
        ]
        if use_sentiment:
            scanner_tools.insert(1, fetch_sentiment_data)  # Add after fetch_technical_snapshot

        # Create MCP server with ONLY bundled tools for scanner agent
        # Individual tools removed to prevent timeout issues from sequential calls
        trading_tools_server = create_sdk_mcp_server(
            name="trading_tools",
            version="1.0.0",
            tools=scanner_tools
        )

        # Tool permission callback to block WebSearch when sentiment is disabled
        async def can_use_tool_callback(
            tool_name: str,
            tool_input: dict,
            context: ToolPermissionContext
        ):
            """Block web search tools when sentiment analysis is disabled."""
            # Block WebSearch and related tools when sentiment is disabled
            if not use_sentiment:
                blocked_tools = ["WebSearch", "mcp__web-search__search", "web-search"]
                if tool_name in blocked_tools or "web" in tool_name.lower() and "search" in tool_name.lower():
                    return PermissionResultDeny(
                        behavior="deny",
                        message="WebSearch is disabled in technical-only mode (--no-sentiment)",
                        interrupt=False
                    )
            # Allow everything else
            return PermissionResultAllow(behavior="allow")

        agent_options = ClaudeAgentOptions(
            # MCP servers
            mcp_servers={
                "trading": trading_tools_server,
                # OpenWebSearch MCP is available via environment
            },

            # Allowed tools - scanner uses only bundled tools (conditionally includes sentiment)
            allowed_tools=[
                "mcp__trading__fetch_technical_snapshot",
                "mcp__trading__submit_trading_signal",
                "mcp__trading__analyze_trend",
                "mcp__trading__analyze_momentum",
                "mcp__trading__analyze_volatility",
                "mcp__trading__analyze_patterns",
            ] + ([
                "mcp__trading__fetch_sentiment_data",
                "mcp__web-search__search",  # Used internally by fetch_sentiment_data
            ] if use_sentiment else []),

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

            # System prompt for scanner agent (dynamic based on sentiment flag)
            system_prompt=build_scanner_system_prompt(use_sentiment),

            # Model and limits
            model=config.CLAUDE_MODEL,
            max_turns=10,
            max_budget_usd=0.50,  # Conservative per-analysis budget

            # Streaming
            include_partial_messages=True,

            # Tool permission callback (blocks WebSearch when --no-sentiment)
            can_use_tool=can_use_tool_callback,
        )

        # Initialize session manager for Claude Agent SDK sessions
        from src.agent.session_manager import SessionManager
        session_manager = SessionManager(db_path)
        await session_manager.init_db()

        # Display session banner
        from src.agent.cli_banner import show_session_banner
        await show_session_banner(
            operation_type=SessionManager.SCANNER,
            model=config.CLAUDE_MODEL,
            session_manager=session_manager
        )

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
            operation_type=SessionManager.SCANNER,
            persistent_client=daily  # Enable persistent client in daily mode
        )

        # Initialize dashboard if enabled
        scanner_dashboard = None
        event_callback = None
        if dashboard:
            from src.agent.scanner.dashboard import ScannerDashboard, ScannerEvent
            # Pass shared console for RichHandler coordination
            scanner_dashboard = ScannerDashboard(console=console, use_sentiment=use_sentiment)
            scanner_dashboard.session_id = session_manager.get_session_id(SessionManager.SCANNER)

            def event_callback(event_type: str, data: dict):
                """Handle scanner events for dashboard."""
                scanner_dashboard.handle_event(event_type, **data)

                # Update portfolio info periodically
                if event_type == ScannerEvent.CYCLE_START:
                    # This will be updated from portfolio manager
                    pass

            console.print("[green]✓[/green] Dashboard mode enabled")

        # Create and start scanner with config
        scanner_config.scan_interval_seconds = interval  # Set interval before passing
        scanner = MarketMoversScanner(
            exchange=exchange,
            agent=agent,
            portfolio=manager,
            db=db,
            config=scanner_config,  # Pass config with sentiment setting
            daily_mode=daily,  # Pass daily mode flag
            event_callback=event_callback,  # Pass dashboard callback
        )

        # Inject scanner config into tools module for web search URL/timeout
        from src.agent.scanner.tools import set_scanner_config
        set_scanner_config(scanner.config)

        # Log daily mode status
        if daily:
            console.print("[green]✓[/green] Daily mode enabled - maintaining single session per day")
            console.print(f"[dim]  All symbol analyses will be in one continuous conversation[/dim]\n")

        # Log sentiment mode status
        if no_sentiment:
            console.print("[yellow]⚠[/yellow] Sentiment analysis disabled - technical-only mode")
            console.print(f"[dim]  Scoring: Technical (0-55), Liquidity (0-30), Correlation (0-15)[/dim]\n")

        console.print("[bold cyan]Scanner initialized. Press Ctrl+C to stop.[/bold cyan]")

        try:
            if scanner_dashboard:
                # Run with live dashboard display
                async with await scanner_dashboard.live_display():
                    # Update portfolio periodically
                    async def update_portfolio_display():
                        """Update portfolio display in dashboard."""
                        while scanner.running:
                            try:
                                summary = await manager.get_portfolio_summary()
                                portfolio_info = summary.get("portfolio", {})
                                scanner_dashboard.update_portfolio({
                                    "equity": portfolio_info.get("current_equity", 0),
                                    "positions": summary.get("positions", {}).get("count", 0),
                                    "exposure_pct": summary.get("positions", {}).get("exposure_pct", 0),
                                    "pnl_pct": portfolio_info.get("total_pnl_pct", 0),
                                })
                            except Exception as e:
                                logger.warning(f"Portfolio display update error: {e}")
                            await asyncio.sleep(5)

                    # Run portfolio updater in background
                    portfolio_task = asyncio.create_task(update_portfolio_display())

                    try:
                        await scanner.start()
                    finally:
                        portfolio_task.cancel()
                        try:
                            await portfolio_task
                        except asyncio.CancelledError:
                            pass
            else:
                # Run without dashboard
                await scanner.start()
        except KeyboardInterrupt:
            await scanner.stop()
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


@cli.command()
@click.option('--symbol', default='BTCUSDT', help='Symbol to display in demo')
@click.option('--once', is_flag=True, help='Run once without live updates')
def pipeline_demo(symbol, once):
    """Demo the multi-agent pipeline dashboard visualization."""
    import asyncio
    import time
    from rich.console import Console
    from src.agent.pipeline.dashboard import (
        PipelineDashboard,
        DashboardConfig,
        StageStatus
    )
    from src.agent.pipeline.dashboard.events import StageEvent

    console = Console()

    async def run_demo():
        # Create dashboard
        config = DashboardConfig(
            show_sidebar=True,
            show_history=True,
            max_history=5
        )
        dashboard = PipelineDashboard(config=config)

        # Set up portfolio state
        dashboard.update_portfolio({
            "equity": 10450.0,
            "open_positions": 3,
            "current_exposure_pct": 12.0,
            "daily_pnl_pct": 1.2,
            "weekly_pnl_pct": 3.8
        })

        dashboard.update_stats({
            "analyzed": 12,
            "approved": 8,
            "rejected": 2,
            "modified": 2,
            "executed": 6,
            "aborted": 2,
            "win_rate": 66.7
        })

        if once:
            # Static demo - show completed pipeline
            dashboard.start_pipeline(symbol=symbol, session_id="demo-session")

            # Simulate completed analysis
            dashboard.handle_event(StageEvent(
                stage="analysis",
                status=StageStatus.COMPLETE,
                symbol=symbol,
                elapsed_ms=2300,
                output={
                    "analysis_report": {
                        "symbol": symbol,
                        "technical": {"trend_score": 0.85},
                        "sentiment": {"score": 22},
                        "liquidity": {"assessment": "good"},
                        "btc_correlation": 0.3
                    },
                    "proposed_signal": {
                        "direction": "LONG",
                        "confidence": 72,
                        "entry_price": 67500.0,
                        "stop_loss": 64125.0,
                        "take_profit": 72900.0,
                        "position_size_pct": 3.0,
                        "reasoning": "Strong uptrend on 4h timeframe"
                    }
                }
            ))

            # Simulate risk audit
            dashboard.handle_event(StageEvent(
                stage="risk_auditor",
                status=StageStatus.COMPLETE,
                symbol=symbol,
                elapsed_ms=1800,
                output={
                    "risk_decision": {
                        "action": "MODIFY",
                        "original_confidence": 72,
                        "audited_confidence": 68,
                        "modifications": ["Reduced position size from 3% to 2.5%"],
                        "warnings": ["High BTC correlation"],
                        "risk_score": 35
                    },
                    "audited_signal": {
                        "direction": "LONG",
                        "confidence": 68,
                        "entry_price": 67500.0,
                        "stop_loss": 64125.0,
                        "take_profit": 72900.0,
                        "position_size_pct": 2.5,
                        "reasoning": "Adjusted for risk limits"
                    },
                    "portfolio_snapshot": {
                        "equity": 10450.0,
                        "open_positions": 3,
                        "current_exposure_pct": 12.0,
                        "daily_pnl_pct": 1.2,
                        "weekly_pnl_pct": 3.8
                    }
                }
            ))

            # Simulate execution
            dashboard.handle_event(StageEvent(
                stage="execution",
                status=StageStatus.COMPLETE,
                symbol=symbol,
                elapsed_ms=900,
                output={
                    "execution_report": {
                        "status": "FILLED",
                        "order_type": "LIMIT",
                        "requested_entry": 67500.0,
                        "actual_entry": 67489.5,
                        "slippage_pct": -0.016,
                        "position_size": 0.0037,
                        "position_value_usd": 249.91,
                        "execution_time_ms": 850
                    },
                    "position_opened": {
                        "symbol": symbol,
                        "direction": "LONG",
                        "entry_price": 67489.5,
                        "stop_loss": 64125.0,
                        "take_profit": 72900.0,
                        "size": 0.0037,
                        "opened_at": "2025-01-25T14:35:22Z"
                    }
                }
            ))

            dashboard.finalize_pipeline("EXECUTED", "+0.8%")

            # Add some history entries
            from datetime import datetime
            from src.agent.pipeline.dashboard.history_feed import PipelineHistoryEntry

            dashboard.history.add(PipelineHistoryEntry(
                symbol="ETHUSDT",
                outcome="NO_TRADE",
                timestamp=datetime.now(),
                detail="low confidence"
            ))
            dashboard.history.add(PipelineHistoryEntry(
                symbol="SOLUSDT",
                outcome="REJECTED",
                timestamp=datetime.now(),
                detail="daily loss limit"
            ))

            # Render once
            dashboard.render_once()

        else:
            # Live demo with animation
            console.print("[bold cyan]Starting live pipeline demo...[/bold cyan]")
            console.print("Press Ctrl+C to exit\n")

            async with dashboard.live_display():
                while True:
                    # Simulate a pipeline run
                    dashboard.start_pipeline(symbol=symbol, session_id=f"demo-{int(time.time())}")

                    # Analysis stage
                    dashboard.handle_event(StageEvent(
                        stage="analysis", status=StageStatus.RUNNING, symbol=symbol, elapsed_ms=0
                    ))
                    await asyncio.sleep(2)

                    dashboard.handle_event(StageEvent(
                        stage="analysis",
                        status=StageStatus.COMPLETE,
                        symbol=symbol,
                        elapsed_ms=2000,
                        output={
                            "analysis_report": {"symbol": symbol, "technical": {}, "sentiment": {}, "liquidity": {}, "btc_correlation": 0.5},
                            "proposed_signal": {
                                "direction": "LONG",
                                "confidence": 72,
                                "entry_price": 67500.0,
                                "stop_loss": 64125.0,
                                "take_profit": 72900.0,
                                "position_size_pct": 3.0,
                                "reasoning": "Strong trend"
                            }
                        }
                    ))
                    await asyncio.sleep(1)

                    # Risk stage
                    dashboard.handle_event(StageEvent(
                        stage="risk_auditor", status=StageStatus.RUNNING, symbol=symbol, elapsed_ms=0
                    ))
                    await asyncio.sleep(1.5)

                    dashboard.handle_event(StageEvent(
                        stage="risk_auditor",
                        status=StageStatus.COMPLETE,
                        symbol=symbol,
                        elapsed_ms=1500,
                        output={
                            "risk_decision": {"action": "APPROVE", "original_confidence": 72, "audited_confidence": 72, "modifications": [], "warnings": [], "risk_score": 25},
                            "audited_signal": {"direction": "LONG", "confidence": 72, "entry_price": 67500.0, "stop_loss": 64125.0, "take_profit": 72900.0, "position_size_pct": 3.0, "reasoning": "Approved"},
                            "portfolio_snapshot": {"equity": 10450, "open_positions": 3, "current_exposure_pct": 12, "daily_pnl_pct": 1.2, "weekly_pnl_pct": 3.8}
                        }
                    ))
                    await asyncio.sleep(1)

                    # Execution stage
                    dashboard.handle_event(StageEvent(
                        stage="execution", status=StageStatus.RUNNING, symbol=symbol, elapsed_ms=0
                    ))
                    await asyncio.sleep(1)

                    dashboard.handle_event(StageEvent(
                        stage="execution",
                        status=StageStatus.COMPLETE,
                        symbol=symbol,
                        elapsed_ms=900,
                        output={
                            "execution_report": {"status": "FILLED", "order_type": "LIMIT", "requested_entry": 67500.0, "actual_entry": 67489.5, "slippage_pct": -0.02, "position_size": 0.004, "position_value_usd": 270, "execution_time_ms": 800},
                            "position_opened": {"symbol": symbol, "direction": "LONG", "entry_price": 67489.5, "stop_loss": 64125.0, "take_profit": 72900.0, "size": 0.004, "opened_at": "2025-01-25T14:35:22Z"}
                        }
                    ))

                    dashboard.finalize_pipeline("EXECUTED", "+0.5%")

                    # Wait before next cycle
                    await asyncio.sleep(5)

    try:
        asyncio.run(run_demo())
    except KeyboardInterrupt:
        console.print("\n[yellow]Demo stopped[/yellow]")


@cli.command()
@click.option('--once', is_flag=True, help='Run once without live updates')
def scanner_demo(once):
    """Demo the scanner dashboard visualization."""
    import asyncio
    import time
    import logging
    from rich.console import Console
    from src.agent.scanner.dashboard import ScannerDashboard, ScannerEvent

    console = Console()

    async def run_demo():
        # Create dashboard with log capture
        dashboard = ScannerDashboard(enable_log_capture=True)
        dashboard.session_id = "demo-session"

        # Set up portfolio state
        dashboard.update_portfolio({
            "equity": 10450.0,
            "positions": 3,
            "exposure_pct": 12.0,
            "pnl_pct": 1.2,
        })

        dashboard.update_stats({
            "total_signals": 5,
            "total_executed": 3,
            "win_rate": 66.7,
        })

        # Demo movers data
        demo_movers = [
            {"symbol": "BTCUSDT", "change_pct": 7.2, "direction": "gainer"},
            {"symbol": "ETHUSDT", "change_pct": 5.8, "direction": "gainer"},
            {"symbol": "SOLUSDT", "change_pct": -6.1, "direction": "loser"},
            {"symbol": "AVAXUSDT", "change_pct": 5.2, "direction": "gainer"},
            {"symbol": "LINKUSDT", "change_pct": -5.5, "direction": "loser"},
        ]

        if once:
            # Static demo - show completed cycle
            dashboard.handle_event(ScannerEvent.CYCLE_START, cycle_number=5, movers=demo_movers)

            # Mark first few as complete
            dashboard.complete_mover("BTCUSDT", "NO_TRADE", confidence=45)
            dashboard.complete_mover("ETHUSDT", "EXECUTED", confidence=72, entry_price=3450.0)
            dashboard.update_mover("SOLUSDT", status="analyzing", stage="analysis", stage_detail="sentiment")

            # Add some mock log lines
            if dashboard.split_screen:
                dashboard.split_screen.log_buffer.add("14:35:22 INFO SCAN CYCLE #5 - Analyzing 5 movers")
                dashboard.split_screen.log_buffer.add("14:35:23 INFO BTCUSDT: Technical score 28/40, weak setup")
                dashboard.split_screen.log_buffer.add("14:35:24 INFO BTCUSDT: Confidence 45/100 (below threshold)")
                dashboard.split_screen.log_buffer.add("14:35:25 INFO ETHUSDT: Technical score 35/40, strong setup")
                dashboard.split_screen.log_buffer.add("14:35:26 INFO ETHUSDT: Signal generated - Confidence 72/100")
                dashboard.split_screen.log_buffer.add("14:35:27 INFO ETHUSDT: Risk check PASSED")
                dashboard.split_screen.log_buffer.add("14:35:28 INFO ETHUSDT: EXECUTED @ $3,450.00")

            # Render once
            dashboard.render_once()

        else:
            # Live demo with animation
            console.print("[bold cyan]Starting live scanner dashboard demo...[/bold cyan]")
            console.print("Press Ctrl+C to exit\n")

            # Set up logging to capture
            demo_logger = logging.getLogger("scanner_demo")
            demo_logger.setLevel(logging.INFO)

            async with await dashboard.live_display():
                # Add demo logger to capture
                if dashboard.split_screen:
                    demo_logger.addHandler(dashboard.split_screen.get_log_handler())

                cycle = 0
                while True:
                    cycle += 1

                    # Start new cycle
                    dashboard.handle_event(ScannerEvent.CYCLE_START, cycle_number=cycle, movers=demo_movers)
                    demo_logger.info(f"SCAN CYCLE #{cycle} - Analyzing {len(demo_movers)} movers")
                    await asyncio.sleep(1)

                    # Process each mover
                    for i, mover in enumerate(demo_movers):
                        symbol = mover["symbol"]
                        dashboard.handle_event(ScannerEvent.MOVER_START, symbol=symbol)
                        demo_logger.info(f"{symbol}: Starting analysis")
                        await asyncio.sleep(0.5)

                        dashboard.handle_event(ScannerEvent.ANALYSIS_PHASE, symbol=symbol, phase="technical")
                        demo_logger.info(f"{symbol}: Technical analysis")
                        await asyncio.sleep(0.5)

                        dashboard.handle_event(ScannerEvent.ANALYSIS_PHASE, symbol=symbol, phase="sentiment")
                        demo_logger.info(f"{symbol}: Sentiment analysis")
                        await asyncio.sleep(0.5)

                        # Random outcome
                        import random
                        confidence = random.randint(35, 85)
                        if confidence >= 60:
                            dashboard.handle_event(
                                ScannerEvent.SIGNAL_GENERATED,
                                symbol=symbol,
                                confidence=confidence,
                                entry_price=random.uniform(1000, 70000),
                            )
                            demo_logger.info(f"{symbol}: Signal generated - Confidence {confidence}/100")

                            dashboard.handle_event(ScannerEvent.RISK_CHECK, symbol=symbol)
                            await asyncio.sleep(0.3)

                            if random.random() > 0.3:
                                dashboard.handle_event(ScannerEvent.EXECUTION, symbol=symbol)
                                dashboard.handle_event(
                                    ScannerEvent.MOVER_COMPLETE,
                                    symbol=symbol,
                                    result="EXECUTED",
                                    confidence=confidence,
                                    entry_price=random.uniform(1000, 70000),
                                )
                                demo_logger.info(f"{symbol}: EXECUTED")
                            else:
                                dashboard.handle_event(
                                    ScannerEvent.MOVER_COMPLETE,
                                    symbol=symbol,
                                    result="REJECTED",
                                    confidence=confidence,
                                )
                                demo_logger.info(f"{symbol}: REJECTED (risk limit)")
                        else:
                            dashboard.handle_event(
                                ScannerEvent.MOVER_COMPLETE,
                                symbol=symbol,
                                result="NO_TRADE",
                                confidence=confidence,
                            )
                            demo_logger.info(f"{symbol}: NO_TRADE (confidence {confidence})")

                        await asyncio.sleep(0.3)

                    # Complete cycle
                    dashboard.handle_event(
                        ScannerEvent.CYCLE_COMPLETE,
                        signals_generated=random.randint(1, 3),
                        trades_executed=random.randint(0, 2),
                        trades_rejected=random.randint(0, 1),
                    )
                    demo_logger.info(f"Cycle #{cycle} completed")

                    # Wait before next cycle
                    await asyncio.sleep(3)

    try:
        asyncio.run(run_demo())
    except KeyboardInterrupt:
        console.print("\n[yellow]Demo stopped[/yellow]")


if __name__ == '__main__':
    cli()
