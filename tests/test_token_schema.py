"""Tests for token tracking database schema."""
import pytest
import pytest_asyncio
import aiosqlite
import tempfile
import os
from pathlib import Path

from src.agent.database.token_schema import create_token_tracking_tables


@pytest_asyncio.fixture
async def test_db():
    """Create temporary test database."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    yield db_path

    # Cleanup
    os.unlink(db_path)


@pytest.mark.asyncio
async def test_create_token_tracking_tables(test_db):
    """Test creating token tracking tables."""
    async with aiosqlite.connect(test_db) as db:
        await create_token_tracking_tables(db)
        await db.commit()

        # Verify token_usage table exists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='token_usage'"
        )
        result = await cursor.fetchone()
        assert result is not None

        # Verify token_sessions table exists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='token_sessions'"
        )
        result = await cursor.fetchone()
        assert result is not None

        # Verify rate_limit_tracking table exists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='rate_limit_tracking'"
        )
        result = await cursor.fetchone()
        assert result is not None


@pytest.mark.asyncio
async def test_token_usage_table_schema(test_db):
    """Test token_usage table has correct columns."""
    async with aiosqlite.connect(test_db) as db:
        await create_token_tracking_tables(db)
        await db.commit()

        cursor = await db.execute("PRAGMA table_info(token_usage)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        expected_columns = [
            'id', 'timestamp', 'session_id', 'operation_type',
            'model', 'tokens_input', 'tokens_output', 'tokens_total',
            'cost_usd', 'duration_seconds', 'metadata'
        ]

        for col in expected_columns:
            assert col in column_names
