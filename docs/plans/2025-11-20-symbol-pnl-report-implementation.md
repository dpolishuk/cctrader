# Symbol-Level P&L Report Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a CLI command that displays P&L metrics aggregated by trading symbol and time period.

**Architecture:** Add database query method to aggregate P&L from trades/positions tables, create Rich-based display module for formatted output, integrate new CLI command into main.py with parameter validation.

**Tech Stack:** Python 3.12, aiosqlite, Rich, Click, pytest

---

## Task 1: Database Layer - Get Symbol P&L Summary

**Files:**
- Modify: `src/agent/database/paper_operations.py` (add method after line 397)
- Test: `tests/test_paper_pnl_queries.py` (NEW)

**Step 1: Write the failing test**

Create `tests/test_paper_pnl_queries.py`:

```python
"""Tests for P&L query methods in paper trading database."""
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from src.agent.database.paper_operations import PaperTradingDatabase
from src.agent.database.paper_schema import init_paper_trading_db


@pytest.fixture
async def db_with_trades(tmp_path):
    """Create database with sample trades and positions."""
    db_path = tmp_path / "test.db"
    await init_paper_trading_db(db_path)

    db = PaperTradingDatabase(db_path)

    # Create portfolio
    portfolio_id = await db.create_portfolio(
        name="test_portfolio",
        starting_capital=100000.0
    )

    # Add sample trades for BTC/USDT
    now = datetime.now()
    await db.record_trade(
        portfolio_id=portfolio_id,
        symbol="BTC/USDT",
        trade_type="CLOSE",
        price=50000.0,
        quantity=0.1,
        execution_mode="realistic",
        slippage_pct=0.1,
        actual_fill_price=50005.0,
        realized_pnl=150.0
    )
    await db.record_trade(
        portfolio_id=portfolio_id,
        symbol="BTC/USDT",
        trade_type="CLOSE",
        price=51000.0,
        quantity=0.1,
        execution_mode="realistic",
        slippage_pct=0.1,
        actual_fill_price=51005.0,
        realized_pnl=-50.0
    )

    # Add sample trade for ETH/USDT
    await db.record_trade(
        portfolio_id=portfolio_id,
        symbol="ETH/USDT",
        trade_type="CLOSE",
        price=3000.0,
        quantity=1.0,
        execution_mode="realistic",
        slippage_pct=0.1,
        actual_fill_price=3003.0,
        realized_pnl=75.0
    )

    # Add open position for SOL/USDT
    await db.open_position(
        portfolio_id=portfolio_id,
        symbol="SOL/USDT",
        position_type="LONG",
        entry_price=100.0,
        quantity=10.0
    )
    await db.update_position_pnl(
        portfolio_id=portfolio_id,
        symbol="SOL/USDT",
        current_price=105.0,
        unrealized_pnl=50.0
    )

    return db, portfolio_id


@pytest.mark.asyncio
async def test_get_symbol_pnl_summary_basic(db_with_trades):
    """Test basic P&L summary aggregation by symbol."""
    db, portfolio_id = db_with_trades

    results = await db.get_symbol_pnl_summary(portfolio_id)

    # Should have 3 symbols
    assert len(results) == 3

    # Check BTC/USDT (2 trades, 1 winner)
    btc = next(r for r in results if r['symbol'] == 'BTC/USDT')
    assert btc['realized_pnl'] == 100.0  # 150 - 50
    assert btc['unrealized_pnl'] == 0.0
    assert btc['total_pnl'] == 100.0
    assert btc['trade_count'] == 2
    assert btc['win_rate'] == 50.0  # 1 winner out of 2
    assert btc['avg_pnl'] == 50.0  # 100 / 2

    # Check ETH/USDT (1 trade, 1 winner)
    eth = next(r for r in results if r['symbol'] == 'ETH/USDT')
    assert eth['realized_pnl'] == 75.0
    assert eth['unrealized_pnl'] == 0.0
    assert eth['total_pnl'] == 75.0
    assert eth['trade_count'] == 1
    assert eth['win_rate'] == 100.0
    assert eth['avg_pnl'] == 75.0

    # Check SOL/USDT (0 trades, only open position)
    sol = next(r for r in results if r['symbol'] == 'SOL/USDT')
    assert sol['realized_pnl'] == 0.0
    assert sol['unrealized_pnl'] == 50.0
    assert sol['total_pnl'] == 50.0
    assert sol['trade_count'] == 0
    assert sol['win_rate'] == 0.0
    assert sol['avg_pnl'] == 0.0


@pytest.mark.asyncio
async def test_get_symbol_pnl_summary_sorted_by_total_pnl(db_with_trades):
    """Test results are sorted by total P&L descending."""
    db, portfolio_id = db_with_trades

    results = await db.get_symbol_pnl_summary(portfolio_id)

    # Should be sorted: BTC (100), ETH (75), SOL (50)
    assert results[0]['symbol'] == 'BTC/USDT'
    assert results[1]['symbol'] == 'ETH/USDT'
    assert results[2]['symbol'] == 'SOL/USDT'


@pytest.mark.asyncio
async def test_get_symbol_pnl_summary_with_min_trades(db_with_trades):
    """Test filtering by minimum trade count."""
    db, portfolio_id = db_with_trades

    results = await db.get_symbol_pnl_summary(portfolio_id, min_trades=1)

    # Should exclude SOL/USDT (0 trades)
    assert len(results) == 2
    symbols = [r['symbol'] for r in results]
    assert 'BTC/USDT' in symbols
    assert 'ETH/USDT' in symbols
    assert 'SOL/USDT' not in symbols


@pytest.mark.asyncio
async def test_get_symbol_pnl_summary_empty_portfolio(tmp_path):
    """Test with empty portfolio (no trades or positions)."""
    db_path = tmp_path / "test.db"
    await init_paper_trading_db(db_path)

    db = PaperTradingDatabase(db_path)
    portfolio_id = await db.create_portfolio(name="empty", starting_capital=10000.0)

    results = await db.get_symbol_pnl_summary(portfolio_id)

    assert results == []
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_paper_pnl_queries.py -v`
Expected: FAIL with "PaperTradingDatabase has no attribute 'get_symbol_pnl_summary'"

**Step 3: Write minimal implementation**

Add to `src/agent/database/paper_operations.py` after line 397:

```python
async def get_symbol_pnl_summary(
    self,
    portfolio_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    min_trades: int = 0
) -> List[Dict[str, Any]]:
    """
    Get P&L summary aggregated by symbol.

    Args:
        portfolio_id: Portfolio ID
        start_date: Filter trades after this date (optional)
        end_date: Filter trades before this date (optional)
        min_trades: Minimum trade count to include symbol (default: 0)

    Returns:
        List of dicts with:
        - symbol: str
        - total_pnl: float (realized + unrealized)
        - realized_pnl: float
        - unrealized_pnl: float
        - trade_count: int
        - win_rate: float (0-100)
        - avg_pnl: float
    """
    async with aiosqlite.connect(self.db_path) as db:
        db.row_factory = aiosqlite.Row

        # Build date filter
        date_filter = ""
        params = [portfolio_id, portfolio_id]
        if start_date:
            date_filter += " AND t.executed_at >= ?"
            params.insert(1, start_date.isoformat())
        if end_date:
            date_filter += " AND t.executed_at <= ?"
            params.insert(2 if start_date else 1, end_date.isoformat())

        params.append(min_trades)

        query = f"""
        WITH realized AS (
            SELECT
                symbol,
                SUM(realized_pnl) as realized_pnl,
                COUNT(*) as trade_count,
                SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as winning_trades
            FROM paper_trades t
            WHERE portfolio_id = ?
              AND realized_pnl IS NOT NULL
              {date_filter}
            GROUP BY symbol
        ),
        unrealized AS (
            SELECT
                symbol,
                SUM(unrealized_pnl) as unrealized_pnl
            FROM paper_positions
            WHERE portfolio_id = ?
              AND is_open = 1
            GROUP BY symbol
        )
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
        LEFT JOIN unrealized u ON r.symbol = u.symbol
        UNION
        SELECT
            u.symbol,
            0 as realized_pnl,
            u.unrealized_pnl,
            u.unrealized_pnl as total_pnl,
            0 as trade_count,
            0 as win_rate,
            0 as avg_pnl
        FROM unrealized u
        LEFT JOIN realized r ON u.symbol = r.symbol
        WHERE r.symbol IS NULL
        HAVING trade_count >= ?
        ORDER BY total_pnl DESC
        """

        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_paper_pnl_queries.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add tests/test_paper_pnl_queries.py src/agent/database/paper_operations.py
git commit -m "feat: add database method to query symbol-level P&L summary

Add get_symbol_pnl_summary() method that aggregates realized and unrealized
P&L by trading symbol with statistics including win rate and average P&L.

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Display Layer - P&L Report Formatter

**Files:**
- Create: `src/agent/display/__init__.py`
- Create: `src/agent/display/pnl_report.py`
- Test: `tests/test_pnl_report_display.py` (NEW)

**Step 1: Write the failing test**

Create `tests/test_pnl_report_display.py`:

```python
"""Tests for P&L report display formatting."""
import pytest
from datetime import datetime
from src.agent.display.pnl_report import format_currency, format_percentage, create_pnl_table


def test_format_currency_positive():
    """Test currency formatting for positive values."""
    assert format_currency(1234.56) == "$1,234.56"
    assert format_currency(0.01) == "$0.01"


def test_format_currency_negative():
    """Test currency formatting for negative values."""
    assert format_currency(-1234.56) == "-$1,234.56"
    assert format_currency(-0.01) == "-$0.01"


def test_format_currency_zero():
    """Test currency formatting for zero."""
    assert format_currency(0) == "$0.00"


def test_format_percentage():
    """Test percentage formatting."""
    assert format_percentage(66.67) == "66.7%"
    assert format_percentage(100.0) == "100.0%"
    assert format_percentage(0.0) == "0.0%"
    assert format_percentage(37.5) == "37.5%"


def test_create_pnl_table_with_data():
    """Test creating P&L table with sample data."""
    data = [
        {
            'symbol': 'BTC/USDT',
            'total_pnl': 1200.50,
            'realized_pnl': 1150.00,
            'unrealized_pnl': 50.50,
            'trade_count': 15,
            'win_rate': 66.7,
            'avg_pnl': 76.67
        },
        {
            'symbol': 'ETH/USDT',
            'total_pnl': 345.20,
            'realized_pnl': 300.00,
            'unrealized_pnl': 45.20,
            'trade_count': 10,
            'win_rate': 70.0,
            'avg_pnl': 30.00
        }
    ]

    table = create_pnl_table(data)

    # Verify table structure
    assert table.title == "P&L by Symbol"
    assert len(table.columns) == 7
    assert table.row_count == 3  # 2 data rows + 1 total row


def test_create_pnl_table_empty():
    """Test creating P&L table with no data."""
    table = create_pnl_table([])

    assert table.title == "P&L by Symbol"
    assert table.row_count == 0
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pnl_report_display.py -v`
Expected: FAIL with "No module named 'src.agent.display'"

**Step 3: Write minimal implementation**

Create `src/agent/display/__init__.py`:

```python
"""Display modules for CLI output formatting."""
```

Create `src/agent/display/pnl_report.py`:

```python
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
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pnl_report_display.py -v`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add src/agent/display/ tests/test_pnl_report_display.py
git commit -m "feat: add P&L report display formatting with Rich tables

Create display module with currency/percentage formatters and Rich table
builder with color-coded P&L values and summary totals.

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Display Layer - Main Report Function

**Files:**
- Modify: `src/agent/display/pnl_report.py` (add function)
- Test: `tests/test_pnl_report_display.py` (add tests)

**Step 1: Write the failing test**

Add to `tests/test_pnl_report_display.py`:

```python
from unittest.mock import AsyncMock, patch
from src.agent.display.pnl_report import display_pnl_report
from src.agent.database.paper_operations import PaperTradingDatabase


@pytest.mark.asyncio
async def test_display_pnl_report_portfolio_not_found(tmp_path):
    """Test error handling when portfolio doesn't exist."""
    from src.agent.database.paper_schema import init_paper_trading_db

    db_path = tmp_path / "test.db"
    await init_paper_trading_db(db_path)
    db = PaperTradingDatabase(db_path)

    # Should raise ValueError
    with pytest.raises(ValueError, match="Portfolio 'nonexistent' not found"):
        await display_pnl_report(db, "nonexistent", "all", 1)


@pytest.mark.asyncio
async def test_display_pnl_report_success(tmp_path, capsys):
    """Test successful P&L report display."""
    from src.agent.database.paper_schema import init_paper_trading_db

    db_path = tmp_path / "test.db"
    await init_paper_trading_db(db_path)
    db = PaperTradingDatabase(db_path)

    # Create portfolio with trades
    portfolio_id = await db.create_portfolio(name="test", starting_capital=10000.0)
    await db.record_trade(
        portfolio_id=portfolio_id,
        symbol="BTC/USDT",
        trade_type="CLOSE",
        price=50000.0,
        quantity=0.1,
        execution_mode="realistic",
        slippage_pct=0.1,
        actual_fill_price=50005.0,
        realized_pnl=100.0
    )

    # Display report (should not raise)
    await display_pnl_report(db, "test", "all", 0)

    # Output captured by Rich console would be tested in integration tests
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pnl_report_display.py::test_display_pnl_report_portfolio_not_found -v`
Expected: FAIL with "display_pnl_report not defined"

**Step 3: Write minimal implementation**

Add to `src/agent/display/pnl_report.py`:

```python
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
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pnl_report_display.py -v`
Expected: PASS (8 tests)

**Step 5: Commit**

```bash
git add src/agent/display/pnl_report.py tests/test_pnl_report_display.py
git commit -m "feat: add main display_pnl_report function with header panel

Add display function that fetches portfolio, calculates date ranges,
queries P&L data, and renders formatted output with Rich.

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: CLI Integration - Add pnl-report Command

**Files:**
- Modify: `src/agent/main.py` (add command after line 496)
- Test: `tests/test_integration_pnl_report.py` (NEW)

**Step 1: Write the failing test**

Create `tests/test_integration_pnl_report.py`:

```python
"""Integration tests for pnl-report CLI command."""
import pytest
from click.testing import CliRunner
from pathlib import Path
from src.agent.main import cli
from src.agent.database.paper_operations import PaperTradingDatabase
from src.agent.database.paper_schema import init_paper_trading_db
from src.agent.config import config


@pytest.fixture
async def test_db_with_portfolio(tmp_path):
    """Create test database with portfolio and trades."""
    db_path = tmp_path / "test.db"
    await init_paper_trading_db(db_path)

    db = PaperTradingDatabase(db_path)

    # Create portfolio
    portfolio_id = await db.create_portfolio(
        name="integration_test",
        starting_capital=50000.0
    )

    # Add trades
    await db.record_trade(
        portfolio_id=portfolio_id,
        symbol="BTC/USDT",
        trade_type="CLOSE",
        price=50000.0,
        quantity=0.1,
        execution_mode="realistic",
        slippage_pct=0.1,
        actual_fill_price=50005.0,
        realized_pnl=200.0
    )

    await db.record_trade(
        portfolio_id=portfolio_id,
        symbol="ETH/USDT",
        trade_type="CLOSE",
        price=3000.0,
        quantity=1.0,
        execution_mode="realistic",
        slippage_pct=0.1,
        actual_fill_price=3003.0,
        realized_pnl=-50.0
    )

    return db_path, portfolio_id


def test_pnl_report_command_exists():
    """Test that pnl-report command is registered."""
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'pnl-report' in result.output


@pytest.mark.asyncio
async def test_pnl_report_command_missing_portfolio():
    """Test pnl-report fails without --portfolio."""
    runner = CliRunner()
    result = runner.invoke(cli, ['pnl-report'])
    assert result.exit_code != 0
    assert 'Missing option' in result.output or 'required' in result.output.lower()


@pytest.mark.asyncio
async def test_pnl_report_command_success(test_db_with_portfolio, tmp_path, monkeypatch):
    """Test successful pnl-report execution."""
    db_path, portfolio_id = await test_db_with_portfolio

    # Override DB_PATH config
    monkeypatch.setattr('src.agent.config.config.DB_PATH', str(db_path))

    runner = CliRunner()
    result = runner.invoke(cli, [
        'pnl-report',
        '--portfolio', 'integration_test',
        '--period', 'all',
        '--min-trades', '0'
    ])

    assert result.exit_code == 0
    assert 'Portfolio P&L Report' in result.output
    assert 'BTC/USDT' in result.output
    assert 'ETH/USDT' in result.output
    assert '$200.00' in result.output
    assert '-$50.00' in result.output


@pytest.mark.asyncio
async def test_pnl_report_command_nonexistent_portfolio(test_db_with_portfolio, tmp_path, monkeypatch):
    """Test pnl-report with nonexistent portfolio."""
    db_path, _ = await test_db_with_portfolio
    monkeypatch.setattr('src.agent.config.config.DB_PATH', str(db_path))

    runner = CliRunner()
    result = runner.invoke(cli, [
        'pnl-report',
        '--portfolio', 'nonexistent'
    ])

    assert result.exit_code != 0
    assert "not found" in result.output.lower()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_integration_pnl_report.py::test_pnl_report_command_exists -v`
Expected: FAIL with "'pnl-report' not in help output"

**Step 3: Write minimal implementation**

Add to `src/agent/main.py` after the `paper_monitor` command (around line 496):

```python
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
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_integration_pnl_report.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add src/agent/main.py tests/test_integration_pnl_report.py
git commit -m "feat: add pnl-report CLI command

Add new CLI command 'pnl-report' with --portfolio, --period, and
--min-trades options to display symbol-level P&L analysis.

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: Fix Date Range Query (if needed)

**Files:**
- Modify: `src/agent/database/paper_operations.py` (fix get_symbol_pnl_summary if date filtering broken)
- Test: `tests/test_paper_pnl_queries.py` (add date range test)

**Step 1: Write the failing test**

Add to `tests/test_paper_pnl_queries.py`:

```python
@pytest.mark.asyncio
async def test_get_symbol_pnl_summary_with_date_range(tmp_path):
    """Test P&L summary with date range filtering."""
    from datetime import datetime, timedelta

    db_path = tmp_path / "test.db"
    await init_paper_trading_db(db_path)

    db = PaperTradingDatabase(db_path)
    portfolio_id = await db.create_portfolio(name="test", starting_capital=10000.0)

    # Add old trade (outside range)
    old_date = datetime.now() - timedelta(days=30)
    # Manually insert with specific date
    import aiosqlite
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            """INSERT INTO paper_trades
            (portfolio_id, symbol, trade_type, price, quantity, execution_mode,
             slippage_pct, actual_fill_price, realized_pnl, executed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (portfolio_id, "OLD/USDT", "CLOSE", 100.0, 1.0, "realistic",
             0.1, 100.1, 50.0, old_date.isoformat())
        )
        await conn.commit()

    # Add recent trade (inside range)
    recent_date = datetime.now() - timedelta(days=3)
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            """INSERT INTO paper_trades
            (portfolio_id, symbol, trade_type, price, quantity, execution_mode,
             slippage_pct, actual_fill_price, realized_pnl, executed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (portfolio_id, "NEW/USDT", "CLOSE", 200.0, 1.0, "realistic",
             0.1, 200.2, 100.0, recent_date.isoformat())
        )
        await conn.commit()

    # Query with date range (last 7 days)
    start_date = datetime.now() - timedelta(days=7)
    results = await db.get_symbol_pnl_summary(
        portfolio_id=portfolio_id,
        start_date=start_date
    )

    # Should only include NEW/USDT (not OLD/USDT)
    assert len(results) == 1
    assert results[0]['symbol'] == 'NEW/USDT'
    assert results[0]['realized_pnl'] == 100.0
```

**Step 2: Run test to verify behavior**

Run: `python -m pytest tests/test_paper_pnl_queries.py::test_get_symbol_pnl_summary_with_date_range -v`

**Expected Outcome:** Either PASS (date filtering already works) or FAIL (needs fix)

**Step 3: Fix if needed**

If test fails, review the SQL query in `get_symbol_pnl_summary()` and ensure date parameters are inserted in correct positions in the params list.

**Step 4: Verify fix**

Run: `python -m pytest tests/test_paper_pnl_queries.py::test_get_symbol_pnl_summary_with_date_range -v`
Expected: PASS

**Step 5: Commit (only if fixes were needed)**

```bash
git add tests/test_paper_pnl_queries.py src/agent/database/paper_operations.py
git commit -m "fix: correct date range filtering in get_symbol_pnl_summary

Fix parameter ordering in SQL query to properly filter trades by date range.

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: Run Full Test Suite

**Files:**
- None (verification only)

**Step 1: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS (237 + new tests)

**Step 2: Check coverage (optional)**

Run: `python -m pytest tests/ --cov=src/agent --cov-report=term-missing`
Expected: >90% coverage for new modules

**Step 3: Manual smoke test**

```bash
# Create test portfolio if needed
cctrader paper-monitor --portfolio smoke_test --symbol BTC/USDT --interval 60

# Run P&L report
cctrader pnl-report --portfolio smoke_test --period all
```

Expected: Report displays without errors (even if empty)

---

## Task 7: Final Integration and Cleanup

**Files:**
- Modify: `README.md` (add pnl-report documentation)

**Step 1: Update README**

Add to README.md under CLI Commands section:

```markdown
### P&L Report

Display profit and loss metrics aggregated by trading symbol:

```bash
cctrader pnl-report --portfolio <name> [--period <daily|weekly|monthly|all>] [--min-trades <N>]
```

**Options:**
- `--portfolio`: Portfolio name (required)
- `--period`: Time period for analysis (default: all)
  - `daily`: Last 7 days
  - `weekly`: Last 4 weeks
  - `monthly`: Last 12 months
  - `all`: All-time performance
- `--min-trades`: Minimum trades to include symbol (default: 1)

**Example Output:**

```
┌─ Portfolio P&L Report ────────────────────────┐
│ Portfolio: default                             │
│ Period: Last 7 Days                            │
│ Total P&L: $1,234.56 (1.23%)                  │
│ Current Equity: $101,234.56                    │
└────────────────────────────────────────────────┘

┌─ P&L by Symbol ───────────────────────────────────────────────────────────┐
│ Symbol      │ Total P&L  │ Realized    │ Unrealized    │ Trades │ Win Rate │
├─────────────┼────────────┼─────────────┼───────────────┼────────┼──────────┤
│ BTC/USDT    │ $1,200.50  │ $1,150.00   │ $50.50        │ 15     │ 66.7%    │
│ ETH/USDT    │ $345.20    │ $300.00     │ $45.20        │ 10     │ 70.0%    │
│ SOL/USDT    │ -$150.30   │ -$200.00    │ $49.70        │ 8      │ 37.5%    │
└─────────────┴────────────┴─────────────┴───────────────┴────────┴──────────┘
```
```

**Step 2: Commit README update**

```bash
git add README.md
git commit -m "docs: add pnl-report command documentation to README

Add usage examples and output format for new pnl-report CLI command.

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
```

**Step 3: Final test run**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

**Step 4: Review git log**

Run: `git log --oneline -10`
Expected: See all 7+ commits for P&L report feature

---

## Success Criteria Checklist

- [ ] `cctrader pnl-report --portfolio default` displays P&L by symbol
- [ ] Report shows accurate realized, unrealized, and total P&L
- [ ] Time period filtering works correctly (daily/weekly/monthly/all)
- [ ] Color coding makes winners/losers easy to identify
- [ ] All tests pass (237 base + ~15 new = 252+ total)
- [ ] Error messages are clear for invalid portfolios
- [ ] Empty portfolios display gracefully
- [ ] README documentation is complete

---

## Reference Skills

- @superpowers:test-driven-development - Follow RED-GREEN-REFACTOR for each task
- @superpowers:verification-before-completion - Run tests after each step
- @superpowers:systematic-debugging - If tests fail unexpectedly

## Notes for Engineer

- **DRY**: Reuse `format_currency` and `format_percentage` helpers throughout
- **YAGNI**: Don't add features not in plan (CSV export, charts, etc.)
- **TDD**: Write test first, watch it fail, implement, watch it pass
- **Commit frequently**: After each task completion
- **SQLite FULL OUTER JOIN**: SQLite doesn't support FULL OUTER JOIN natively, so we use LEFT JOIN + UNION pattern
- **Rich library**: Already used in project for CLI output, consistent with existing commands
