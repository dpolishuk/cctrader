"""Tests for core token tracker."""
import pytest
import pytest_asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock

from src.agent.tracking.token_tracker import TokenTracker
from src.agent.database.token_schema import create_token_tracking_tables


@pytest_asyncio.fixture
async def tracker():
    """Create token tracker with temporary database."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    import aiosqlite
    async with aiosqlite.connect(db_path) as db:
        await create_token_tracking_tables(db)
        await db.commit()

    tracker = TokenTracker(
        db_path=db_path,
        operation_mode="test"
    )
    await tracker.start_session()

    yield tracker

    await tracker.end_session()
    os.unlink(db_path)


@pytest.mark.asyncio
async def test_start_session(tracker):
    """Test starting a tracking session."""
    assert tracker.session_id is not None
    assert tracker.is_active


@pytest.mark.asyncio
async def test_record_usage(tracker):
    """Test recording token usage."""
    # Mock ResultMessage with usage dict
    mock_result = Mock()
    mock_result.usage = {
        'input_tokens': 1500,
        'output_tokens': 800
    }
    mock_result.model = "claude-sonnet-4-5"

    await tracker.record_usage(
        result=mock_result,
        operation_type="analysis",
        duration_seconds=3.2
    )

    # Verify session was updated
    session = await tracker.get_session_stats()
    assert session['total_requests'] == 1
    assert session['total_tokens_input'] == 1500
    assert session['total_tokens_output'] == 800


@pytest.mark.asyncio
async def test_get_rate_limit_status(tracker):
    """Test getting rate limit status."""
    # Record some usage
    mock_result = Mock()
    mock_result.usage = {
        'input_tokens': 1000,
        'output_tokens': 500
    }
    mock_result.model = "claude-sonnet-4-5"

    for _ in range(5):
        await tracker.record_usage(
            result=mock_result,
            operation_type="test"
        )

    status = await tracker.get_rate_limit_status()

    assert 'hourly' in status
    assert 'daily' in status
    assert status['hourly']['request_count'] == 5


@pytest.mark.asyncio
async def test_interval_tracking_initialization(tracker):
    """Test that interval tracking state initializes correctly."""
    assert hasattr(tracker, 'interval_start_time')
    assert hasattr(tracker, 'interval_number')
    assert hasattr(tracker, 'current_interval')
    assert hasattr(tracker, 'completed_intervals')

    assert tracker.interval_number == 0
    assert tracker.current_interval == {
        'tokens_input': 0,
        'tokens_output': 0,
        'cost': 0.0,
        'requests': 0
    }
    assert tracker.completed_intervals == []
