"""Integration tests for token interval tracking."""
import pytest
import asyncio
import time
import aiosqlite
from pathlib import Path
from src.agent.tracking.token_tracker import TokenTracker
from src.agent.database.token_operations import TokenDatabase
from src.agent.database.token_schema import create_token_tracking_tables


@pytest.mark.asyncio
async def test_full_interval_tracking_workflow(tmp_path):
    """Test complete interval tracking workflow."""
    db_path = tmp_path / "integration_test.db"

    # Initialize database
    async with aiosqlite.connect(db_path) as db:
        await create_token_tracking_tables(db)
        await db.commit()

    tracker = TokenTracker(db_path=db_path, operation_mode="integration_test")

    # Override interval duration for faster testing
    tracker.INTERVAL_DURATION = 1.0  # 1 second

    # Start session
    session_id = await tracker.start_session()
    assert tracker.interval_start_time is not None
    assert tracker.interval_number == 1

    # Create mock result
    class MockResult:
        usage = {'input_tokens': 100, 'output_tokens': 50}
        model = 'claude-3-5-sonnet-20241022'

    # Record usage in interval 1
    await tracker.record_usage(MockResult(), operation_type="test")
    assert tracker.current_interval['tokens_input'] == 100
    assert tracker.current_interval['tokens_output'] == 50
    assert tracker.current_interval['requests'] == 1
    assert len(tracker.completed_intervals) == 0

    # Wait for interval to complete
    await asyncio.sleep(1.1)

    # Record usage to trigger interval completion
    await tracker.record_usage(MockResult(), operation_type="test")

    # Verify interval completed
    assert tracker.interval_number == 2
    assert len(tracker.completed_intervals) == 1
    assert tracker.completed_intervals[0]['interval_number'] == 1
    assert tracker.completed_intervals[0]['tokens_input'] == 100
    assert tracker.completed_intervals[0]['tokens_output'] == 50
    assert tracker.completed_intervals[0]['requests'] == 1

    # Verify new interval started fresh
    assert tracker.current_interval['tokens_input'] == 100
    assert tracker.current_interval['tokens_output'] == 50
    assert tracker.current_interval['requests'] == 1

    # End session
    await tracker.end_session()

    # Verify session data in database
    db = TokenDatabase(db_path)
    session = await db.get_session(session_id)
    assert session['total_tokens_input'] == 200
    assert session['total_tokens_output'] == 100
    assert session['total_requests'] == 2


@pytest.mark.asyncio
async def test_end_session_captures_partial_interval(tmp_path):
    """Test that end_session captures partial interval."""
    db_path = tmp_path / "partial_test.db"

    # Initialize database
    async with aiosqlite.connect(db_path) as db:
        await create_token_tracking_tables(db)
        await db.commit()

    tracker = TokenTracker(db_path=db_path, operation_mode="partial_test")

    # Start session
    await tracker.start_session()

    class MockResult:
        usage = {'input_tokens': 50, 'output_tokens': 25}
        model = 'claude-3-5-sonnet-20241022'

    # Record some usage
    await tracker.record_usage(MockResult(), operation_type="test")

    # Verify partial interval is in current_interval (not completed yet)
    assert len(tracker.completed_intervals) == 0  # No completed intervals
    assert tracker.current_interval['tokens_input'] == 50
    assert tracker.current_interval['tokens_output'] == 25
    assert tracker.current_interval['requests'] == 1

    # End session immediately (before interval completes)
    # This should display the partial interval but not move it to completed_intervals
    await tracker.end_session()

    # After session ends, partial interval remains in current_interval
    # (it's displayed but not formally "completed")
    assert tracker.current_interval['tokens_input'] == 50
    assert tracker.current_interval['tokens_output'] == 25


@pytest.mark.asyncio
async def test_interval_query_from_database(tmp_path):
    """Test querying intervals from database after session ends."""
    db_path = tmp_path / "query_test.db"

    # Initialize database
    async with aiosqlite.connect(db_path) as db:
        await create_token_tracking_tables(db)
        await db.commit()

    tracker = TokenTracker(db_path=db_path, operation_mode="query_test")

    # Set short interval
    tracker.INTERVAL_DURATION = 0.5

    # Start session
    session_id = await tracker.start_session()

    class MockResult:
        usage = {'input_tokens': 100, 'output_tokens': 50}
        model = 'claude-3-5-sonnet-20241022'

    # Record usage in first interval
    await tracker.record_usage(MockResult(), operation_type="test")

    # Wait for interval to complete
    await asyncio.sleep(0.6)

    # Record usage to trigger completion and start second interval
    await tracker.record_usage(MockResult(), operation_type="test")

    # End session
    await tracker.end_session()

    # Query intervals from database
    db = TokenDatabase(db_path)
    intervals = await db.get_session_intervals(session_id, interval_minutes=0.5/60)  # Convert to minutes

    # Should have captured at least the first completed interval
    assert len(intervals) >= 1
    assert intervals[0]['tokens_input'] == 100
    assert intervals[0]['tokens_output'] == 50


@pytest.mark.asyncio
async def test_multiple_sessions_recent_query(tmp_path):
    """Test querying recent sessions."""
    db_path = tmp_path / "recent_test.db"

    # Initialize database
    async with aiosqlite.connect(db_path) as db:
        await create_token_tracking_tables(db)
        await db.commit()

    # Create multiple sessions
    for i in range(3):
        tracker = TokenTracker(db_path=db_path, operation_mode=f"test_{i}")
        await tracker.start_session()

        class MockResult:
            usage = {'input_tokens': 100 * (i+1), 'output_tokens': 50 * (i+1)}
            model = 'claude-3-5-sonnet-20241022'

        await tracker.record_usage(MockResult(), operation_type="test")
        await tracker.end_session()

    # Query recent sessions
    db = TokenDatabase(db_path)
    sessions = await db.get_recent_sessions(limit=10)

    # Should have all 3 sessions
    assert len(sessions) == 3

    # Should be in reverse chronological order (most recent first)
    assert sessions[0]['total_tokens_input'] == 300  # Session 3
    assert sessions[1]['total_tokens_input'] == 200  # Session 2
    assert sessions[2]['total_tokens_input'] == 100  # Session 1
