import pytest
import aiosqlite
from pathlib import Path
from agent.database.movers_schema import create_movers_tables
from agent.database.paper_operations import PaperTradingDatabase

@pytest.mark.asyncio
async def test_create_movers_tables(tmp_path):
    """Test movers tables creation."""
    db_path = tmp_path / "test.db"

    async with aiosqlite.connect(db_path) as db:
        await create_movers_tables(db)
        await db.commit()

    # Verify tables exist
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'movers_%'"
        )
        tables = [row[0] for row in await cursor.fetchall()]

    assert 'movers_signals' in tables
    assert 'movers_rejections' in tables
    assert 'movers_metrics' in tables

@pytest.mark.asyncio
async def test_save_mover_signal(tmp_path):
    """Test saving mover signal."""
    db_path = tmp_path / "test.db"

    async with aiosqlite.connect(db_path) as db:
        await create_movers_tables(db)
        await db.commit()

    db_ops = PaperTradingDatabase(db_path)

    signal_id = await db_ops.save_mover_signal(
        symbol='BTCUSDT',
        direction='LONG',
        confidence=78,
        entry_price=90000,
        stop_loss=87500,
        tp1=95000,
        position_size_usd=200,
        risk_amount_usd=50,
        technical_score=34,
        sentiment_score=23,
        liquidity_score=18,
        correlation_score=5,
        analysis={'summary': 'Strong momentum'}
    )

    assert signal_id > 0

    # Verify saved
    signal = await db_ops.get_mover_signal(signal_id)
    assert signal is not None
    assert signal['symbol'] == 'BTCUSDT'
    assert signal['confidence'] == 78

@pytest.mark.asyncio
async def test_save_mover_rejection(tmp_path):
    """Test saving mover rejection."""
    db_path = tmp_path / "test.db"

    async with aiosqlite.connect(db_path) as db:
        await create_movers_tables(db)
        await db.commit()

    db_ops = PaperTradingDatabase(db_path)

    await db_ops.save_mover_rejection(
        symbol='ETHUSDT',
        direction='LONG',
        confidence=55,
        reason='Confidence below threshold',
        details={'required': 60, 'actual': 55}
    )

    # Verify saved
    rejections = await db_ops.get_recent_rejections(limit=10)
    assert len(rejections) == 1
    assert rejections[0]['symbol'] == 'ETHUSDT'
    assert 'threshold' in rejections[0]['reason']
