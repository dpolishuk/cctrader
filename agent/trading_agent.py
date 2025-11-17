"""Core trading agent using Claude Agent SDK."""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from claude_agent_sdk import (
    tool,
    create_sdk_mcp_server,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    AssistantMessage,
    TextBlock
)

# Import all tools
from tools.market_data import fetch_market_data, get_current_price
from tools.technical_analysis import analyze_technicals, multi_timeframe_analysis
from tools.sentiment import analyze_market_sentiment, detect_market_events
from tools.signals import generate_trading_signal
from tools.portfolio import update_portfolio, calculate_pnl
from database.schema import init_database
from database.operations import TradingDatabase

load_dotenv()

class TradingAgent:
    def __init__(self, symbol: str = "BTC/USDT", timeframes: list = None):
        self.symbol = symbol
        self.timeframes = timeframes or ["1m", "5m", "15m", "1h", "4h", "1d"]
        self.db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))
        self.db = TradingDatabase(self.db_path)
        self.running = False

    async def initialize(self):
        """Initialize database and agent."""
        await init_database(self.db_path)
        print(f"✅ Database initialized at {self.db_path}")

    def create_agent_options(self) -> ClaudeAgentOptions:
        """Create Claude Agent SDK configuration."""

        # Create SDK MCP server with all trading tools
        trading_tools_server = create_sdk_mcp_server(
            name="trading_tools",
            version="1.0.0",
            tools=[
                fetch_market_data,
                get_current_price,
                analyze_technicals,
                multi_timeframe_analysis,
                analyze_market_sentiment,
                detect_market_events,
                generate_trading_signal,
                update_portfolio,
                calculate_pnl
            ]
        )

        # Configure options
        options = ClaudeAgentOptions(
            # MCP servers
            mcp_servers={
                "trading": trading_tools_server,
                # Perplexity MCP is available via the environment
            },

            # Allowed tools (trading tools + Perplexity)
            allowed_tools=[
                "mcp__trading__fetch_market_data",
                "mcp__trading__get_current_price",
                "mcp__trading__analyze_technicals",
                "mcp__trading__multi_timeframe_analysis",
                "mcp__trading__analyze_market_sentiment",
                "mcp__trading__detect_market_events",
                "mcp__trading__generate_trading_signal",
                "mcp__trading__update_portfolio",
                "mcp__trading__calculate_pnl",
                "mcp__perplexity-mcp__perplexity_ask",
                "mcp__perplexity-mcp__perplexity_reason",
            ],

            # System prompt
            system_prompt=f"""You are an expert cryptocurrency trading analysis agent monitoring {self.symbol} on Bybit.

Your responsibilities:
1. Fetch market data across multiple timeframes: {', '.join(self.timeframes)}
2. Perform comprehensive technical analysis (RSI, MACD, Bollinger Bands)
3. Analyze market sentiment using Perplexity for news and events
4. Generate trading signals (BUY/SELL/HOLD) with confidence scores
5. Monitor portfolio positions and calculate P&L
6. Store all analysis and signals in the database

Always:
- Use multi-timeframe analysis for comprehensive view
- Combine technical indicators with sentiment analysis
- Provide clear reasoning for all signals
- Track historical signals for pattern analysis
- Alert on stop-loss and take-profit levels

When analyzing:
1. First fetch current price and recent OHLCV data
2. Run technical analysis on each timeframe
3. Query Perplexity for market sentiment and news
4. Combine all data to generate trading signal
5. Save signal to database
6. If position exists, calculate and report P&L
""",

            # Model
            model="claude-sonnet-4-5",

            # Limits
            max_turns=20,
            max_budget_usd=1.0,  # Per session

            # Streaming
            include_partial_messages=True,
        )

        return options

    async def analyze_market(self, query: str = None):
        """Run market analysis cycle."""
        if query is None:
            query = f"""Perform a complete market analysis for {self.symbol}:

1. Fetch current price and latest OHLCV data for timeframes: {', '.join(self.timeframes[:3])}
2. Run technical analysis on each timeframe
3. Use Perplexity to analyze current market sentiment and detect any significant events
4. Generate a trading signal based on all the analysis
5. Save the signal to the database
6. If there's an open position, calculate current P&L

Provide a comprehensive analysis report."""

        options = self.create_agent_options()

        async with ClaudeSDKClient(options=options) as client:
            print(f"\n🔍 Analyzing {self.symbol}...")
            print(f"📊 Query: {query}\n")

            await client.query(query)

            # Process responses
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(block.text)
                        # Could also handle ToolUseBlock to show tool usage

    async def continuous_monitor(self, interval_seconds: int = 300):
        """Continuously monitor market at specified interval."""
        self.running = True
        print(f"🚀 Starting continuous monitoring of {self.symbol}")
        print(f"⏱️  Analysis interval: {interval_seconds} seconds\n")

        while self.running:
            try:
                await self.analyze_market()

                if self.running:  # Check again in case stopped during analysis
                    print(f"\n⏸️  Sleeping for {interval_seconds} seconds...")
                    await asyncio.sleep(interval_seconds)

            except KeyboardInterrupt:
                print("\n🛑 Stopping continuous monitoring...")
                self.running = False
                break
            except Exception as e:
                print(f"\n❌ Error in monitoring cycle: {e}")
                print(f"Retrying in {interval_seconds} seconds...")
                await asyncio.sleep(interval_seconds)

    def stop(self):
        """Stop continuous monitoring."""
        self.running = False
