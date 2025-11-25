# CLAUDE.md - CCTrader Development Guide

## Quick Reference

### Common Commands

```bash
# Activate virtual environment
source venv/bin/activate

# Run all tests
pytest

# Run specific test file
pytest tests/test_session_manager.py -v

# Run tests with coverage
pytest --cov=src/agent

# Single market analysis
python -m src.agent.main analyze --symbol BTC/USDT

# Continuous monitoring
python -m src.agent.main monitor --symbol BTC/USDT --interval 300

# Market movers scanner (creates new session per analysis)
python -m src.agent.main scan-movers --interval 300

# Daily mode scanner (one session per day)
python -m src.agent.main scan-movers --daily

# View recent signals
python -m src.agent.main signals --symbol BTC/USDT --limit 10

# Portfolio status
python -m src.agent.main status --symbol BTC/USDT

# P&L report
python -m src.agent.main pnl-report --portfolio default --period daily

# Token usage stats
python -m src.agent.main token-stats --period hourly
```

### Environment Setup

```bash
cp .env.example .env
# Edit .env with API keys: ANTHROPIC_API_KEY, BYBIT_API_KEY, BYBIT_API_SECRET
```

## Architecture Overview

### Core Components

```
src/agent/
├── main.py                 # CLI entry point (Click commands)
├── trading_agent.py        # TradingAgent - Claude Agent SDK integration
├── session_manager.py      # Session ID generation & persistence
├── config.py               # Configuration from environment variables
├── cli_banner.py           # Session banner display
│
├── scanner/                # Market Movers Scanner
│   ├── main_loop.py        # MarketMoversScanner - main scanning loop
│   ├── agent_wrapper.py    # AgentWrapper - Claude SDK client wrapper
│   ├── momentum_scanner.py # MomentumScanner - price change detection
│   ├── symbol_manager.py   # FuturesSymbolManager - tradeable symbols
│   ├── tools.py            # Scanner-specific Claude tools
│   ├── prompts.py          # Agent prompts
│   ├── risk_validator.py   # Signal validation before execution
│   └── config.py           # Scanner configuration
│
├── tools/                  # Claude Agent Tools (MCP-style)
│   ├── market_data.py      # fetch_market_data, get_current_price
│   ├── technical_analysis.py # analyze_trend, analyze_momentum, etc.
│   ├── sentiment.py        # fetch_sentiment_data (generates query for WebSearch)
│   ├── signals.py          # submit_trading_signal
│   ├── portfolio.py        # Portfolio management tools
│   └── paper_trading_tools.py # Paper trading execution
│
├── paper_trading/          # Paper Trading System
│   ├── portfolio_manager.py # PaperPortfolioManager
│   ├── execution_engine.py  # Trade simulation
│   ├── risk_manager.py      # Position sizing, exposure limits
│   └── metrics_calculator.py # Performance metrics
│
├── database/               # SQLite Persistence
│   ├── schema.py           # Core schema
│   ├── paper_schema.py     # Paper trading tables
│   ├── movers_schema.py    # Scanner signals table
│   ├── token_schema.py     # Token tracking tables
│   └── operations.py       # Database CRUD operations
│
└── tracking/               # Token Usage Tracking
    ├── token_tracker.py    # TokenTracker class
    └── display.py          # Usage display formatting
```

### Key Patterns

#### 1. Signal Queue Pattern
The agent communicates trading decisions through a signal queue. Tools call `signal_queue.put()` to pass signals back to the scanner:

```python
# In tools.py
def submit_trading_signal(...):
    signal = {"symbol": symbol, "direction": direction, "confidence": confidence, ...}
    signal_queue.put(signal)  # Queue is injected via tool context
```

#### 2. Persistent Client Mode (Daily Sessions)
For `--daily` mode, the AgentWrapper reuses the same Claude client across multiple analyses:

```python
# agent_wrapper.py
class AgentWrapper:
    def __init__(self, persistent_client: bool = False):
        self.persistent_client = persistent_client
        self._client = None  # Reused when persistent_client=True
```

#### 3. MCP Tools Limitation
**IMPORTANT**: MCP tools (like WebSearch, Perplexity) cannot be called from Python code. They can only be invoked by Claude during agent execution. The `fetch_sentiment_data` tool generates a query string for Claude to use with WebSearch.

#### 4. Session ID Generation
Daily session IDs follow the format `{operation_type}-{YYYY-MM-DD}`:

```python
# session_manager.py
def generate_daily_session_id(self, operation_type: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return f"{operation_type}-{today}"  # e.g., "scanner-2025-11-21"
```

### Database Tables

| Table | Purpose |
|-------|---------|
| `signals` | Historical trading signals from analysis |
| `movers_signals` | Scanner-specific signals with momentum data |
| `paper_positions` | Open paper trading positions |
| `paper_trades` | Closed trade history with P&L |
| `paper_portfolios` | Portfolio definitions and equity |
| `agent_sessions` | Session ID persistence for daily mode |
| `token_usage` | Per-request token metrics |

### Configuration

Key environment variables in `.env`:

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key |
| `BYBIT_API_KEY` / `BYBIT_API_SECRET` | Exchange credentials |
| `BYBIT_TESTNET` | Use testnet (true/false) |
| `DB_PATH` | SQLite database path |
| `MAX_TURNS` | Max agent conversation turns |
| `MAX_BUDGET_USD` | Budget limit per analysis |
| `TOKEN_TRACKING_ENABLED` | Enable token usage tracking |

## Testing

Tests use pytest with asyncio support. Key test files:

- `test_session_manager_daily.py` - Daily session ID generation
- `test_agent_wrapper_persistent.py` - Persistent client mode
- `test_scanner_bundled_tools.py` - Scanner tool integration
- `test_paper_trading.py` - Paper trading execution
- `test_risk_validator.py` - Signal validation

Run tests:
```bash
pytest                          # All tests
pytest -v                       # Verbose output
pytest -k "daily"               # Tests matching "daily"
pytest tests/test_session_manager_daily.py  # Specific file
```

## Development Notes

### Adding New Tools

1. Create tool function in `src/agent/tools/` or `src/agent/scanner/tools.py`
2. Use `@tool` decorator from claude-agent-sdk
3. Register in the appropriate tools list (agent_tools or scanner_tools)
4. Tools receive context via closure or parameter injection

### Web Search Integration

Use Perplexity MCP for reliable web search:
```python
# In Claude conversation, use:
mcp__perplexity-mcp__perplexity_ask
```

The built-in WebSearch tool may have API issues.

### Signal Flow

```
MomentumScanner.scan_all_symbols()
    → MarketMoversScanner.pre_filter_movers()
    → AgentWrapper.run(prompt, symbol)
        → Claude analyzes with tools
        → submit_trading_signal() → signal_queue
    → RiskValidator.validate_signal()
    → PaperPortfolioManager.execute_signal()
```

### Dependencies

- `claude-agent-sdk` - Claude Agent SDK
- `ccxt>=4.2.0` - Exchange connectivity (Bybit)
- `pandas-ta` - Technical indicators
- `aiosqlite` - Async SQLite
- `click` - CLI framework
- `rich` - Terminal formatting
