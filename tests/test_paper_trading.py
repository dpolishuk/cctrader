"""Integration tests for paper trading system."""
import pytest
import pytest_asyncio
import asyncio
from pathlib import Path
import os
import tempfile

from agent.database.paper_schema import init_paper_trading_db
from agent.database.paper_operations import PaperTradingDatabase
from agent.paper_trading.portfolio_manager import PaperPortfolioManager
from agent.paper_trading.risk_manager import TradeProposal

@pytest_asyncio.fixture
async def test_db():
    """Create temporary test database."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    await init_paper_trading_db(db_path)

    yield db_path

    # Cleanup
    os.unlink(db_path)

@pytest.mark.asyncio
async def test_create_portfolio(test_db):
    """Test portfolio creation."""
    db = PaperTradingDatabase(test_db)

    portfolio_id = await db.create_portfolio(
        name="test_portfolio",
        starting_capital=100000.0
    )

    assert portfolio_id > 0

    portfolio = await db.get_portfolio(portfolio_id)
    assert portfolio['name'] == "test_portfolio"
    assert portfolio['starting_capital'] == 100000.0

@pytest.mark.asyncio
async def test_open_position(test_db):
    """Test opening a position."""
    manager = PaperPortfolioManager(test_db, "test_portfolio")
    await manager.initialize()

    signal = {
        "type": "BUY",
        "confidence": 0.8,
        "symbol": "BTC/USDT"
    }

    result = await manager.execute_signal(
        signal=signal,
        current_price=90000.0
    )

    assert result['executed'] == True
    assert result['action'] == "OPEN_LONG"
    assert 'execution_details' in result

@pytest.mark.asyncio
async def test_risk_validation(test_db):
    """Test risk validation blocks oversized trades."""
    manager = PaperPortfolioManager(test_db, "test_portfolio")
    await manager.initialize()

    # Try to open position larger than limit
    trade = TradeProposal(
        symbol="BTC/USDT",
        side="BUY",
        quantity=10.0,  # Very large position
        price=90000.0,
        position_type="LONG"
    )

    is_valid, violations = await manager.risk_manager.validate_trade(trade)

    assert is_valid == False
    assert len(violations) > 0

@pytest.mark.asyncio
async def test_circuit_breaker(test_db):
    """Test circuit breaker triggers on drawdown."""
    db = PaperTradingDatabase(test_db)
    portfolio_id = await db.create_portfolio(
        name="test_cb",
        starting_capital=100000.0,
        max_drawdown_pct=10.0
    )

    # Simulate large loss
    await db.update_portfolio_equity(portfolio_id, 85000.0)  # >10% drawdown

    manager = PaperPortfolioManager(test_db, "test_cb")
    await manager.initialize()

    should_trigger, reason = await manager.risk_manager.check_circuit_breakers()

    assert should_trigger == True
    assert "Drawdown" in reason

@pytest.mark.asyncio
async def test_close_position(test_db):
    """Test closing a position."""
    manager = PaperPortfolioManager(test_db, "test_close")
    await manager.initialize()

    # Open position
    signal = {
        "type": "BUY",
        "confidence": 0.8,
        "symbol": "BTC/USDT"
    }

    open_result = await manager.execute_signal(
        signal=signal,
        current_price=90000.0
    )

    assert open_result['executed'] == True

    # Close position
    close_signal = {
        "type": "SELL",
        "confidence": 0.7,
        "symbol": "BTC/USDT"
    }

    close_result = await manager.execute_signal(
        signal=close_signal,
        current_price=91000.0
    )

    assert close_result['executed'] == True
    assert close_result['action'] == "CLOSE"
    assert 'execution_details' in close_result
    assert close_result['execution_details']['realized_pnl'] > 0  # Should be profitable

@pytest.mark.asyncio
async def test_portfolio_summary(test_db):
    """Test portfolio summary generation."""
    manager = PaperPortfolioManager(test_db, "test_summary")
    await manager.initialize()

    summary = await manager.get_portfolio_summary()

    assert 'portfolio' in summary
    assert 'positions' in summary
    assert 'risk' in summary
    assert summary['portfolio']['name'] == "test_summary"
    assert summary['portfolio']['starting_capital'] == 100000.0

@pytest.mark.asyncio
async def test_execution_modes(test_db):
    """Test different execution modes."""
    # Test instant mode
    db = PaperTradingDatabase(test_db)
    portfolio_id = await db.create_portfolio(
        name="test_instant",
        starting_capital=100000.0,
        execution_mode="instant"
    )

    manager = PaperPortfolioManager(test_db, "test_instant")
    await manager.initialize()

    signal = {
        "type": "BUY",
        "confidence": 0.8,
        "symbol": "BTC/USDT"
    }

    result = await manager.execute_signal(
        signal=signal,
        current_price=90000.0
    )

    assert result['executed'] == True
    # In instant mode, slippage should be 0
    assert result['execution_details']['slippage_pct'] == 0.0

# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
