"""Tests for agent output database schema."""
import pytest
import aiosqlite
from pathlib import Path
import tempfile

from src.agent.database.agent_schema import init_agent_schema


@pytest.mark.asyncio
async def test_agent_outputs_table_exists():
    """Test that agent_outputs table is created."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    await init_agent_schema(db_path)

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_outputs'"
        )
        result = await cursor.fetchone()
        assert result is not None
        assert result[0] == "agent_outputs"

    db_path.unlink()


@pytest.mark.asyncio
async def test_risk_decisions_table_exists():
    """Test that risk_decisions table is created."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    await init_agent_schema(db_path)

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='risk_decisions'"
        )
        result = await cursor.fetchone()
        assert result is not None

    db_path.unlink()


@pytest.mark.asyncio
async def test_execution_reports_table_exists():
    """Test that execution_reports table is created."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    await init_agent_schema(db_path)

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='execution_reports'"
        )
        result = await cursor.fetchone()
        assert result is not None

    db_path.unlink()


@pytest.mark.asyncio
async def test_trade_reviews_table_exists():
    """Test that trade_reviews table is created."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    await init_agent_schema(db_path)

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='trade_reviews'"
        )
        result = await cursor.fetchone()
        assert result is not None

    db_path.unlink()


@pytest.mark.asyncio
async def test_daily_reports_table_exists():
    """Test that daily_reports table is created."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    await init_agent_schema(db_path)

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_reports'"
        )
        result = await cursor.fetchone()
        assert result is not None

    db_path.unlink()
