"""Integration tests for pnl-report CLI command."""
import pytest
from click.testing import CliRunner
from pathlib import Path
from src.agent.main import cli
from src.agent.database.paper_operations import PaperTradingDatabase
from src.agent.database.paper_schema import init_paper_trading_db
from src.agent.config import config


def test_pnl_report_command_exists():
    """Test that pnl-report command is registered."""
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'pnl-report' in result.output


def test_pnl_report_command_missing_portfolio():
    """Test pnl-report fails without --portfolio."""
    runner = CliRunner()
    result = runner.invoke(cli, ['pnl-report'])
    assert result.exit_code != 0
    assert 'Missing option' in result.output or 'required' in result.output.lower()


def test_pnl_report_command_success(tmp_path, monkeypatch):
    """Test successful pnl-report execution."""
    import asyncio

    # Create DB synchronously
    async def setup_db():
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

        return db_path

    db_path = asyncio.run(setup_db())

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


def test_pnl_report_command_nonexistent_portfolio(tmp_path, monkeypatch):
    """Test pnl-report with nonexistent portfolio."""
    import asyncio

    # Create empty DB synchronously
    async def setup_db():
        db_path = tmp_path / "test.db"
        await init_paper_trading_db(db_path)
        db = PaperTradingDatabase(db_path)

        # Create a portfolio so DB is valid
        await db.create_portfolio(
            name="integration_test",
            starting_capital=50000.0
        )

        return db_path

    db_path = asyncio.run(setup_db())
    monkeypatch.setattr('src.agent.config.config.DB_PATH', str(db_path))

    runner = CliRunner()
    result = runner.invoke(cli, [
        'pnl-report',
        '--portfolio', 'nonexistent'
    ])

    assert result.exit_code != 0
    assert "not found" in result.output.lower()
