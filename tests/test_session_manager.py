"""Tests for Claude Agent SDK session management."""
import pytest
import pytest_asyncio
import aiosqlite
from pathlib import Path
import tempfile
import os

from src.agent.session_manager import SessionManager


@pytest_asyncio.fixture
async def session_manager():
    """Create a temporary session manager for testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
        db_path = Path(tmp.name)

    manager = SessionManager(db_path)
    await manager.init_db()

    yield manager

    # Cleanup
    if db_path.exists():
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_init_db(session_manager):
    """Test database initialization creates the table."""
    async with aiosqlite.connect(session_manager.db_path) as db:
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_sessions'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None


@pytest.mark.asyncio
async def test_save_and_get_session(session_manager):
    """Test saving and retrieving a session ID."""
    # Save a session
    await session_manager.save_session_id(
        SessionManager.SCANNER,
        "test-session-123",
        metadata='{"test": "data"}'
    )

    # Retrieve it
    session_id = await session_manager.get_session_id(SessionManager.SCANNER)
    assert session_id == "test-session-123"


@pytest.mark.asyncio
async def test_get_nonexistent_session(session_manager):
    """Test getting a session that doesn't exist returns None."""
    session_id = await session_manager.get_session_id(SessionManager.ANALYSIS)
    assert session_id is None


@pytest.mark.asyncio
async def test_session_isolation(session_manager):
    """Test that different operation types have separate sessions."""
    # Create sessions for different operation types
    await session_manager.save_session_id(SessionManager.SCANNER, "scanner-session")
    await session_manager.save_session_id(SessionManager.ANALYSIS, "analysis-session")
    await session_manager.save_session_id(SessionManager.MONITOR, "monitor-session")

    # Verify isolation
    assert await session_manager.get_session_id(SessionManager.SCANNER) == "scanner-session"
    assert await session_manager.get_session_id(SessionManager.ANALYSIS) == "analysis-session"
    assert await session_manager.get_session_id(SessionManager.MONITOR) == "monitor-session"


@pytest.mark.asyncio
async def test_update_existing_session(session_manager):
    """Test that saving a new session ID for existing operation type updates it."""
    # Save initial session
    await session_manager.save_session_id(SessionManager.SCANNER, "session-v1")
    assert await session_manager.get_session_id(SessionManager.SCANNER) == "session-v1"

    # Update with new session
    await session_manager.save_session_id(SessionManager.SCANNER, "session-v2")
    assert await session_manager.get_session_id(SessionManager.SCANNER) == "session-v2"


@pytest.mark.asyncio
async def test_clear_session(session_manager):
    """Test clearing a specific session."""
    # Create sessions
    await session_manager.save_session_id(SessionManager.SCANNER, "scanner-session")
    await session_manager.save_session_id(SessionManager.ANALYSIS, "analysis-session")

    # Clear scanner session
    await session_manager.clear_session(SessionManager.SCANNER)

    # Verify scanner is cleared but analysis remains
    assert await session_manager.get_session_id(SessionManager.SCANNER) is None
    assert await session_manager.get_session_id(SessionManager.ANALYSIS) == "analysis-session"


@pytest.mark.asyncio
async def test_clear_all_sessions(session_manager):
    """Test clearing all sessions."""
    # Create multiple sessions
    await session_manager.save_session_id(SessionManager.SCANNER, "scanner-session")
    await session_manager.save_session_id(SessionManager.ANALYSIS, "analysis-session")
    await session_manager.save_session_id(SessionManager.MONITOR, "monitor-session")

    # Clear all
    await session_manager.clear_all_sessions()

    # Verify all are cleared
    assert await session_manager.get_session_id(SessionManager.SCANNER) is None
    assert await session_manager.get_session_id(SessionManager.ANALYSIS) is None
    assert await session_manager.get_session_id(SessionManager.MONITOR) is None


@pytest.mark.asyncio
async def test_list_sessions(session_manager):
    """Test listing all active sessions."""
    # Create sessions
    await session_manager.save_session_id(SessionManager.SCANNER, "scanner-123")
    await session_manager.save_session_id(SessionManager.ANALYSIS, "analysis-456")

    # List them
    sessions = await session_manager.list_sessions()

    assert len(sessions) == 2
    assert SessionManager.SCANNER in sessions
    assert SessionManager.ANALYSIS in sessions
    assert sessions[SessionManager.SCANNER]['session_id'] == "scanner-123"
    assert sessions[SessionManager.ANALYSIS]['session_id'] == "analysis-456"


@pytest.mark.asyncio
async def test_list_empty_sessions(session_manager):
    """Test listing sessions when none exist."""
    sessions = await session_manager.list_sessions()
    assert sessions == {}
