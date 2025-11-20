# Symbol-Level P&L Report Design

**Date:** 2025-11-20
**Status:** Design Complete - Ready for Implementation

## Overview

Implement a comprehensive P&L (Profit & Loss) reporting system that displays trading performance broken down by symbol and time period. This feature allows traders to analyze which trading pairs are performing well and identify areas for improvement.

## Requirements

- Display P&L metrics aggregated by trading symbol (e.g., BTC/USDT, ETH/USDT)
- Support multiple time period filters (daily, weekly, monthly, all-time)
- Show both realized P&L (closed trades) and unrealized P&L (open positions)
- Provide key statistics: trade count, win rate, average P&L per trade
- Use Rich library for color-coded, visually appealing CLI output
- Handle edge cases gracefully (empty portfolios, no trades in period)

## Data Structure

### Data Sources

1. **paper_trades table**: Contains realized P&L from closed positions
   - Fields: `symbol`, `realized_pnl`, `executed_at`, `portfolio_id`

2. **paper_positions table**: Contains unrealized P&L from open positions
   - Fields: `symbol`, `unrealized_pnl`, `is_open`, `portfolio_id`

### Metrics Per Symbol

- **Total P&L**: Realized P&L + Unrealized P&L
- **Realized P&L**: Sum of P&L from closed trades
- **Unrealized P&L**: Sum of P&L from currently open positions
- **Trade Count**: Number of trades executed for this symbol
- **Win Rate**: Percentage of profitable trades (realized_pnl > 0)
- **Average P&L**: Total realized P&L / number of closed trades

### Time Period Options

- **all**: All-time performance (default)
- **daily**: Last 7 days
- **weekly**: Last 4 weeks
- **monthly**: Last 12 months
- **custom**: User-specified date range (future enhancement)

## Display Format

### CLI Command

```bash
cctrader pnl-report --portfolio <name> [--period <daily|weekly|monthly|all>] [--min-trades <N>]
```

**Parameters:**
- `--portfolio` (required): Portfolio name
- `--period` (optional): Time period filter, default: 'all'
- `--min-trades` (optional): Filter symbols with minimum trade count, default: 1

### Display Layout

**Header Section:**
```
┌─ Portfolio P&L Report ────────────────────────┐
│ Portfolio: default                             │
│ Period: Last 7 Days                            │
│ Total P&L: $1,234.56 (1.23%)                  │
│ Current Equity: $101,234.56                    │
└────────────────────────────────────────────────┘
```

**Main Table:**
```
┌─────────────┬────────────┬─────────────┬───────────────┬────────┬──────────┬─────────────┐
│ Symbol      │ Total P&L  │ Realized    │ Unrealized    │ Trades │ Win Rate │ Avg P&L     │
├─────────────┼────────────┼─────────────┼───────────────┼────────┼──────────┼─────────────┤
│ BTC/USDT    │ $1,200.50  │ $1,150.00   │ $50.50        │ 15     │ 66.7%    │ $76.67      │
│ ETH/USDT    │ $345.20    │ $300.00     │ $45.20        │ 10     │ 70.0%    │ $30.00      │
│ SOL/USDT    │ -$150.30   │ -$200.00    │ $49.70        │ 8      │ 37.5%    │ -$25.00     │
├─────────────┼────────────┼─────────────┼───────────────┼────────┼──────────┼─────────────┤
│ TOTAL       │ $1,395.40  │ $1,250.00   │ $145.40       │ 33     │ 63.6%    │ $37.88      │
└─────────────┴────────────┴─────────────┴───────────────┴────────┴──────────┴─────────────┘
```

**Color Coding:**
- Green: Positive P&L values (≥ 0)
- Red: Negative P&L values (< 0)
- Yellow: Warning indicators (win rate < 50%)
- Bold: Summary/total row

**Sorting:**
- Default: By Total P&L descending (best performers first)

## Database Layer

### New Methods in PaperTradingDatabase

#### 1. `get_symbol_pnl_summary()`

```python
async def get_symbol_pnl_summary(
    self,
    portfolio_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    min_trades: int = 1
) -> List[Dict[str, Any]]:
    """
    Get P&L summary aggregated by symbol.

    Returns list of dicts with:
    - symbol: str
    - total_pnl: float (realized + unrealized)
    - realized_pnl: float
    - unrealized_pnl: float
    - trade_count: int
    - win_rate: float (0-100)
    - avg_pnl: float
    """
```

**SQL Query Logic:**

```sql
-- Step 1: Get realized P&L from trades
WITH realized AS (
    SELECT
        symbol,
        SUM(realized_pnl) as realized_pnl,
        COUNT(*) as trade_count,
        SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as winning_trades
    FROM paper_trades
    WHERE portfolio_id = ?
      AND executed_at >= ?
      AND executed_at <= ?
    GROUP BY symbol
),
-- Step 2: Get unrealized P&L from open positions
unrealized AS (
    SELECT
        symbol,
        SUM(unrealized_pnl) as unrealized_pnl
    FROM paper_positions
    WHERE portfolio_id = ?
      AND is_open = 1
    GROUP BY symbol
)
-- Step 3: Combine and calculate
SELECT
    COALESCE(r.symbol, u.symbol) as symbol,
    COALESCE(r.realized_pnl, 0) as realized_pnl,
    COALESCE(u.unrealized_pnl, 0) as unrealized_pnl,
    COALESCE(r.realized_pnl, 0) + COALESCE(u.unrealized_pnl, 0) as total_pnl,
    COALESCE(r.trade_count, 0) as trade_count,
    CASE
        WHEN r.trade_count > 0
        THEN CAST(r.winning_trades AS REAL) / r.trade_count * 100
        ELSE 0
    END as win_rate,
    CASE
        WHEN r.trade_count > 0
        THEN r.realized_pnl / r.trade_count
        ELSE 0
    END as avg_pnl
FROM realized r
FULL OUTER JOIN unrealized u ON r.symbol = u.symbol
WHERE COALESCE(r.trade_count, 0) >= ?
ORDER BY total_pnl DESC
```

## CLI Integration

### File: `src/agent/main.py`

Add new command:

```python
@cli.command()
@click.option('--portfolio', required=True, help='Portfolio name')
@click.option('--period', default='all',
              type=click.Choice(['daily', 'weekly', 'monthly', 'all']),
              help='Time period for report')
@click.option('--min-trades', default=1, help='Minimum trades per symbol')
def pnl_report(portfolio, period, min_trades):
    """Display P&L report by symbol and time period."""
    async def run():
        from src.agent.display.pnl_report import display_pnl_report
        from src.agent.database.paper_operations import PaperTradingDatabase
        from pathlib import Path
        from src.agent.config import config

        db = PaperTradingDatabase(Path(config.DB_PATH))
        await display_pnl_report(db, portfolio, period, min_trades)

    asyncio.run(run())
```

### File: `src/agent/display/pnl_report.py` (NEW)

```python
"""P&L Report Display Functionality"""
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from src.agent.database.paper_operations import PaperTradingDatabase

async def display_pnl_report(
    db: PaperTradingDatabase,
    portfolio_name: str,
    period: str = 'all',
    min_trades: int = 1
) -> None:
    """Display P&L report with Rich formatting."""
    # Implementation details
```

## Error Handling

### Expected Error Scenarios

1. **Portfolio not found**
   - Check if portfolio exists before querying
   - Display error: "Portfolio '{name}' not found. Available portfolios: ..."
   - List available portfolios using `get_all_portfolios()`

2. **No trades in period**
   - Display: "No trading activity found for period: {period}"
   - Show empty table with headers

3. **Database connection errors**
   - Catch aiosqlite exceptions
   - Display: "Database error: Unable to retrieve P&L data"
   - Log full error for debugging

4. **Invalid date range**
   - Validate start_date < end_date
   - Display: "Invalid date range"

### Edge Cases

1. **Empty portfolio (no trades)**
   - Display header with $0.00 P&L
   - Show message: "No trades recorded for this portfolio"

2. **Symbols with only open positions**
   - realized_pnl = 0
   - Show unrealized_pnl only
   - trade_count = 0, win_rate = N/A

3. **Symbols with only closed trades**
   - unrealized_pnl = 0
   - Show realized_pnl only

4. **All trades in period are break-even**
   - Win rate = 0% (no winners)
   - Display normally without warnings

## Testing Strategy

### Unit Tests (tests/test_pnl_report.py)

1. **Database Query Tests**
   - Test `get_symbol_pnl_summary()` with various portfolios
   - Test date range filtering
   - Test min_trades filtering
   - Test edge cases (no trades, only open positions, etc.)

2. **P&L Calculation Tests**
   - Verify realized + unrealized = total
   - Verify win rate calculation
   - Verify average P&L calculation

3. **Time Period Tests**
   - Daily: trades from last 7 days
   - Weekly: trades from last 4 weeks
   - Monthly: trades from last 12 months
   - All: all trades

### Integration Tests

1. **CLI Command Tests**
   - Test command execution with valid parameters
   - Test error handling for invalid portfolio
   - Test output formatting (snapshot testing)

2. **End-to-End Tests**
   - Create test portfolio with sample trades
   - Run pnl-report command
   - Verify correct output

### Test Data Fixtures

```python
# Sample portfolio with multiple symbols
portfolio_id = 1
trades = [
    {"symbol": "BTC/USDT", "realized_pnl": 100.0},
    {"symbol": "BTC/USDT", "realized_pnl": -50.0},
    {"symbol": "ETH/USDT", "realized_pnl": 75.0},
    {"symbol": "SOL/USDT", "realized_pnl": -25.0},
]
positions = [
    {"symbol": "BTC/USDT", "unrealized_pnl": 25.0, "is_open": 1},
    {"symbol": "ETH/USDT", "unrealized_pnl": -10.0, "is_open": 1},
]
```

## Implementation Plan

### Phase 1: Database Layer
1. Add `get_symbol_pnl_summary()` method to PaperTradingDatabase
2. Add helper method for date range calculation
3. Write unit tests for database methods

### Phase 2: Display Layer
1. Create `src/agent/display/pnl_report.py`
2. Implement Rich formatting for header and table
3. Add color coding logic

### Phase 3: CLI Integration
1. Add `pnl_report` command to main.py
2. Wire up command to display layer
3. Add parameter validation

### Phase 4: Testing
1. Write unit tests for all components
2. Write integration tests for CLI command
3. Test edge cases and error scenarios

### Phase 5: Documentation
1. Update README with pnl-report command usage
2. Add example screenshots
3. Document time period calculations

## File Structure

```
src/agent/
├── database/
│   └── paper_operations.py          (add get_symbol_pnl_summary)
├── display/
│   └── pnl_report.py                (NEW - formatting logic)
└── main.py                          (add pnl_report command)

tests/
├── test_pnl_report.py               (NEW - unit tests)
└── test_integration_pnl_report.py   (NEW - integration tests)

docs/plans/
└── 2025-11-20-symbol-pnl-report-design.md (this file)
```

## Future Enhancements

- Export P&L report to CSV/JSON
- Add custom date range support
- Include additional metrics (Sharpe ratio per symbol, max drawdown)
- Add filtering by symbol pattern (e.g., only show *USDT pairs)
- Add comparison mode (compare two time periods)
- Add visualization (chart of P&L over time per symbol)

## Success Criteria

- ✅ Users can run `cctrader pnl-report --portfolio default` and see P&L by symbol
- ✅ Report shows accurate realized, unrealized, and total P&L
- ✅ Time period filtering works correctly
- ✅ Color coding makes it easy to identify winners/losers
- ✅ All tests pass (>95% code coverage)
- ✅ Error messages are clear and actionable
