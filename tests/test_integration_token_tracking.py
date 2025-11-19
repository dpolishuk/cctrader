"""Integration tests for end-to-end token tracking."""
import pytest
import pytest_asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from src.agent.tracking.token_tracker import TokenTracker
from src.agent.database.token_schema import create_token_tracking_tables


@pytest_asyncio.fixture
async def integration_setup():
    """Set up complete token tracking environment."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    # Initialize database
    import aiosqlite
    async with aiosqlite.connect(db_path) as db:
        await create_token_tracking_tables(db)
        await db.commit()

    yield db_path

    os.unlink(db_path)


@pytest.mark.asyncio
async def test_complete_tracking_workflow(integration_setup):
    """Test complete tracking workflow from start to finish."""
    db_path = integration_setup

    # Start session
    tracker = TokenTracker(db_path=db_path, operation_mode="test")
    session_id = await tracker.start_session()

    assert session_id is not None

    # Simulate multiple agent calls
    for i in range(3):
        mock_result = Mock()
        mock_result.usage = {
            'input_tokens': 1000 + (i * 100),
            'output_tokens': 500 + (i * 50)
        }
        mock_result.model = "claude-sonnet-4-5"

        await tracker.record_usage(
            result=mock_result,
            operation_type="test_analysis",
            duration_seconds=2.0 + i,
            metadata={"iteration": i}
        )

    # Verify session stats
    session_stats = await tracker.get_session_stats()

    assert session_stats['total_requests'] == 3
    assert session_stats['total_tokens_input'] == 3300  # 1000 + 1100 + 1200
    assert session_stats['total_tokens_output'] == 1650  # 500 + 550 + 600

    # Verify rate limit status
    rate_status = await tracker.get_rate_limit_status()

    assert rate_status['hourly']['request_count'] == 3
    assert rate_status['daily']['request_count'] == 3

    # End session
    await tracker.end_session()

    # Verify session ended
    session = await tracker.get_session_stats()
    assert session['is_active'] == 0
    assert session['end_time'] is not None


@pytest.mark.asyncio
async def test_cost_calculation_accuracy(integration_setup):
    """Test that cost calculation is accurate."""
    db_path = integration_setup

    tracker = TokenTracker(db_path=db_path, operation_mode="test")
    await tracker.start_session()

    # Known token counts
    mock_result = Mock()
    mock_result.usage = {
        'input_tokens': 1_000_000,  # 1M input
        'output_tokens': 500_000    # 0.5M output
    }
    mock_result.model = "claude-sonnet-4-5"

    await tracker.record_usage(
        result=mock_result,
        operation_type="test"
    )

    # Expected: $3/1M * 1M + $15/1M * 0.5M = $3 + $7.50 = $10.50
    session_stats = await tracker.get_session_stats()

    assert session_stats['total_cost_usd'] == 10.50

    await tracker.end_session()
