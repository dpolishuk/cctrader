"""Tests for P&L query methods in paper trading database."""
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from pathlib import Path
from src.agent.database.paper_operations import PaperTradingDatabase
from src.agent.database.paper_schema import init_paper_trading_db


@pytest_asyncio.fixture
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
    position_id = await db.open_position(
        portfolio_id=portfolio_id,
        symbol="SOL/USDT",
        position_type="LONG",
        entry_price=100.0,
        quantity=10.0
    )
    await db.update_position_price(
        position_id=position_id,
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
