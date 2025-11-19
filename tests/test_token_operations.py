"""Tests for token tracking database operations."""
import pytest
import pytest_asyncio
import aiosqlite
import tempfile
import os
from pathlib import Path
from datetime import datetime
import json

from src.agent.database.token_schema import create_token_tracking_tables
from src.agent.database.token_operations import TokenDatabase


@pytest_asyncio.fixture
async def token_db():
    """Create temporary token tracking database."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    async with aiosqlite.connect(db_path) as db:
        await create_token_tracking_tables(db)
        await db.commit()

    token_db = TokenDatabase(db_path)

    yield token_db

    # Cleanup
    os.unlink(db_path)


@pytest.mark.asyncio
async def test_create_session(token_db):
    """Test creating a new tracking session."""
    session_id = await token_db.create_session(
        operation_mode="test_mode"
    )

    assert session_id is not None
    assert len(session_id) > 0

    # Verify session exists in database
    session = await token_db.get_session(session_id)
    assert session is not None
    assert session['operation_mode'] == "test_mode"
    assert session['is_active'] == 1


@pytest.mark.asyncio
async def test_record_token_usage(token_db):
    """Test recording token usage."""
    session_id = await token_db.create_session("test")

    usage_id = await token_db.record_token_usage(
        session_id=session_id,
        operation_type="analysis",
        model="claude-sonnet-4-5",
        tokens_input=1000,
        tokens_output=500,
        cost_usd=0.0105,
        duration_seconds=2.5,
        metadata={"symbol": "BTC/USDT"}
    )

    assert usage_id > 0

    # Verify session was updated
    session = await token_db.get_session(session_id)
    assert session['total_requests'] == 1
    assert session['total_tokens_input'] == 1000
    assert session['total_tokens_output'] == 500
    assert session['total_cost_usd'] == 0.0105


@pytest.mark.asyncio
async def test_get_hourly_usage(token_db):
    """Test getting hourly usage statistics."""
    session_id = await token_db.create_session("test")

    # Record multiple usages
    for i in range(3):
        await token_db.record_token_usage(
            session_id=session_id,
            operation_type="analysis",
            model="claude-sonnet-4-5",
            tokens_input=1000,
            tokens_output=500,
            cost_usd=0.0105,
            duration_seconds=2.0
        )

    stats = await token_db.get_hourly_usage()

    assert stats['request_count'] == 3
    assert stats['total_tokens'] == 4500  # (1000 + 500) * 3
    assert stats['total_cost_usd'] == 0.0315  # 0.0105 * 3


@pytest.mark.asyncio
async def test_get_daily_usage(token_db):
    """Test getting daily usage statistics."""
    session_id = await token_db.create_session("test")

    # Record 5 token usages
    for i in range(5):
        await token_db.record_token_usage(
            session_id=session_id,
            operation_type="analysis",
            model="claude-sonnet-4-5",
            tokens_input=1000,
            tokens_output=500,
            cost_usd=0.0105,
            duration_seconds=2.0
        )

    stats = await token_db.get_daily_usage()

    assert stats['request_count'] == 5
    assert stats['total_tokens'] == 7500  # (1000 + 500) * 5
    assert abs(stats['total_cost_usd'] - 0.0525) < 1e-10  # 0.0105 * 5


@pytest.mark.asyncio
async def test_end_session(token_db):
    """Test ending a session."""
    session_id = await token_db.create_session("test")

    await token_db.end_session(session_id)

    session = await token_db.get_session(session_id)
    assert session['is_active'] == 0
    assert session['end_time'] is not None
