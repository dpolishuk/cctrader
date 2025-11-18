# Paper Trading Guide

## Overview

The paper trading system provides realistic trade simulation with:
- Configurable execution realism (instant/realistic/historical)
- Multi-layer risk management
- Real-time portfolio auditing
- Comprehensive performance metrics

## Quick Start

### 1. Create a Portfolio

```bash
python -m agent.main create-portfolio \
  --name "my_strategy" \
  --capital 100000 \
  --mode realistic
```

### 2. Start Paper Trading

```bash
python -m agent.main paper-monitor \
  --symbol BTC/USDT \
  --portfolio my_strategy \
  --interval 300
```

### 3. View Portfolio Status

```bash
python -m agent.main paper-status --name my_strategy
```

## Execution Modes

### Instant Mode
- Zero slippage
- Immediate fills at signal price
- Best for rapid strategy testing

### Realistic Mode (Recommended)
- Simulates bid-ask spread (0.02-0.05%)
- Market impact based on order size
- Variable execution time (50-200ms)
- Occasional partial fills

### Historical Mode
- Uses actual OHLCV data for fills
- Most realistic simulation
- Requires market data available

## Risk Management

### Pre-Trade Validation
All trades checked before execution:
- Position size limit (default: 5% of portfolio)
- Total exposure limit (default: 80% of portfolio)
- Daily loss limit (default: 5%)
- Drawdown limit (default: 10%)

### Circuit Breakers
Trading automatically halted when:
- Drawdown hits 10% from peak
- Daily loss hits 5%
- 3+ critical violations in 1 hour

Reset with:
```bash
python -m agent.main reset-breaker --portfolio my_strategy
```

## Portfolio Audit Dashboard

The dashboard shows:
- Portfolio equity and P&L
- Open positions with unrealized P&L
- Performance metrics (win rate, Sharpe ratio, etc.)
- Risk compliance status
- Recent violations
- Execution quality statistics

## Integration Example

```python
from agent.trading_agent import TradingAgent

# Create agent in paper trading mode
agent = TradingAgent(
    symbol="BTC/USDT",
    paper_trading=True,
    paper_portfolio="my_strategy"
)

await agent.initialize()
await agent.analyze_market()
```

## Configuration

Default risk limits can be customized when creating a portfolio:

```python
from agent.database.paper_operations import PaperTradingDatabase

db = PaperTradingDatabase(db_path)

await db.create_portfolio(
    name="aggressive_strategy",
    starting_capital=100000,
    max_position_size_pct=10.0,      # Allow larger positions
    max_total_exposure_pct=90.0,     # Higher exposure
    max_daily_loss_pct=7.0,          # More daily risk
    max_drawdown_pct=15.0            # Higher drawdown tolerance
)
```

## Architecture

### Database Schema

The paper trading system uses 6 dedicated tables:

1. **paper_portfolios** - Portfolio configuration and state
2. **paper_positions** - Open positions tracking
3. **paper_trades** - Complete trade history
4. **paper_risk_audit** - Risk compliance events
5. **paper_performance_metrics** - Aggregated statistics
6. **paper_execution_quality** - Execution analysis

### Components

#### ExecutionEngine
- Simulates trade execution with configurable realism
- Three modes: instant, realistic, historical
- Tracks slippage, execution time, partial fills

#### RiskManager
- Four-layer risk management:
  1. Pre-trade validation (blocks invalid trades)
  2. Continuous monitoring (generates warnings)
  3. Post-trade reconciliation (logs violations)
  4. Circuit breakers (auto-halts trading)

#### PaperPortfolioManager
- Manages portfolio operations
- Executes trading signals
- Updates positions and calculates P&L
- Integrates execution and risk management

#### PerformanceMetricsCalculator
- Calculates comprehensive performance metrics
- Win rate, profit factor, Sharpe ratio, Sortino ratio
- Max drawdown tracking
- Execution quality analysis

#### AuditDashboard
- Real-time portfolio visualization
- Risk compliance monitoring
- Performance metrics display
- Violation reporting

## Best Practices

1. **Start with realistic mode** for balanced testing
2. **Monitor circuit breakers** - they're there for a reason
3. **Review execution quality** regularly for realistic expectations
4. **Track Sharpe ratio** for risk-adjusted returns
5. **Test strategies thoroughly** before live trading

## Troubleshooting

### Circuit Breaker Won't Reset
- Check drawdown is below limit
- Verify no active violations
- Ensure positions are properly updated

### Positions Not Updating
- Verify `update_paper_positions` is called regularly
- Check current prices are being provided
- Review logs for errors

### High Slippage
- Normal in realistic mode (0.05-0.2%)
- Switch to instant mode if testing strategy logic
- Review market volatility at execution time

## CLI Commands Reference

### create-portfolio
Create a new paper trading portfolio.

```bash
python -m agent.main create-portfolio --name PORTFOLIO_NAME [OPTIONS]

Options:
  --name TEXT                 Portfolio name [required]
  --capital FLOAT            Starting capital (default: 100000.0)
  --mode [instant|realistic|historical]
                             Execution mode (default: realistic)
```

### paper-monitor
Start continuous market monitoring in paper trading mode.

```bash
python -m agent.main paper-monitor [OPTIONS]

Options:
  --symbol TEXT              Trading pair symbol (default: BTC/USDT)
  --portfolio TEXT           Paper trading portfolio name (default: default)
  --interval INTEGER         Analysis interval in seconds (default: 300)
```

### paper-status
Show paper trading portfolio status and audit dashboard.

```bash
python -m agent.main paper-status --name PORTFOLIO_NAME
```

### reset-breaker
Manually reset circuit breaker to resume trading.

```bash
python -m agent.main reset-breaker --portfolio PORTFOLIO_NAME
```

## MCP Tools

When using the trading agent, the following MCP tools are available for paper trading:

- `create_paper_portfolio` - Create new portfolio
- `execute_paper_trade` - Execute trading signal in paper mode
- `get_paper_portfolio_status` - Get portfolio status and metrics
- `update_paper_positions` - Update positions with current prices
- `reset_circuit_breaker` - Reset circuit breaker

## Performance Metrics Explained

### Win Rate
Percentage of profitable trades vs total trades.

### Profit Factor
Ratio of gross profit to gross loss. Values > 1.0 indicate profitability.

### Sharpe Ratio
Risk-adjusted return metric. Higher is better (>1.0 is good, >2.0 is excellent).

### Sortino Ratio
Similar to Sharpe but only penalizes downside volatility. More favorable metric for most strategies.

### Max Drawdown
Largest peak-to-trough decline in portfolio value. Critical risk metric.

### Average Slippage
Average difference between signal price and execution price. Lower is better.

## Example Workflow

### Initial Setup
```bash
# Create portfolio
python -m agent.main create-portfolio --name btc_momentum --capital 50000 --mode realistic

# Check it was created
python -m agent.main paper-status --name btc_momentum
```

### Running Strategy
```bash
# Start paper trading
python -m agent.main paper-monitor --symbol BTC/USDT --portfolio btc_momentum --interval 300
```

### Monitoring
```bash
# Check status periodically (in another terminal)
python -m agent.main paper-status --name btc_momentum
```

### Recovery
```bash
# If circuit breaker triggers
python -m agent.main reset-breaker --portfolio btc_momentum
```

## Advanced Topics

### Custom Execution Modes

You can modify execution behavior by editing `agent/paper_trading/execution_engine.py`:

- Adjust slippage parameters in `_realistic_execution()`
- Customize partial fill probability
- Add custom volatility modeling

### Custom Risk Rules

Extend the risk manager in `agent/paper_trading/risk_manager.py`:

```python
async def _check_custom_rule(self) -> Tuple[bool, Optional[str]]:
    """Add your custom risk check."""
    # Your logic here
    return True, None
```

Then call it in `validate_trade()`.

### Performance Analytics

Access detailed metrics via database:

```python
from agent.database.paper_operations import PaperTradingDatabase

db = PaperTradingDatabase(db_path)
trades = await db.get_trade_history(portfolio_id, limit=1000)

# Analyze trades
for trade in trades:
    print(f"{trade['symbol']}: {trade['realized_pnl']}")
```

## FAQ

**Q: Can I run multiple paper portfolios simultaneously?**
A: Yes! Create multiple portfolios with different names and run separate monitor processes.

**Q: Does paper trading use real market data?**
A: Yes, it uses live market data from the exchange via the same market data tools as live trading.

**Q: Can I switch from paper to live trading?**
A: The agent supports both modes, but they are completely separate. Test thoroughly in paper mode before going live.

**Q: How accurate is the realistic execution mode?**
A: It simulates typical crypto market conditions with 0.02-0.05% spread and reasonable slippage. It's conservative but realistic.

**Q: What happens to my data if I restart?**
A: All data is persisted in SQLite database. Your portfolios, positions, and history are preserved across restarts.

## Support

For issues or questions:
- Check logs for error messages
- Review risk audit table for violations
- Consult the troubleshooting section above
- File issues on the project repository
