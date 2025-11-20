"""Tests for P&L report display formatting."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from src.agent.display.pnl_report import format_currency, format_percentage, create_pnl_table, display_pnl_report
from src.agent.database.paper_operations import PaperTradingDatabase


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
