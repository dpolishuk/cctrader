"""Tests for daily session ID functionality."""
import pytest
from datetime import datetime
from pathlib import Path
from src.agent.session_manager import SessionManager


@pytest.mark.asyncio
async def test_generate_daily_session_id():
    """Test that daily session IDs include date."""
    manager = SessionManager(Path(":memory:"))

    session_id = manager.generate_daily_session_id("scanner")

    # Should be format: scanner-YYYY-MM-DD
    today = datetime.now().strftime("%Y-%m-%d")
    assert session_id == f"scanner-{today}"


@pytest.mark.asyncio
async def test_different_dates_different_session_ids():
    """Test that different dates generate different session IDs."""
    manager = SessionManager(Path(":memory:"))

    # Mock different dates
    from unittest.mock import patch, Mock

    with patch('src.agent.session_manager.datetime') as mock_datetime:
        mock_now = Mock()
        mock_now.strftime.return_value = "2025-11-21"
        mock_datetime.now.return_value = mock_now
        session_id_1 = manager.generate_daily_session_id("scanner")

    with patch('src.agent.session_manager.datetime') as mock_datetime:
        mock_now = Mock()
        mock_now.strftime.return_value = "2025-11-22"
        mock_datetime.now.return_value = mock_now
        session_id_2 = manager.generate_daily_session_id("scanner")

    assert session_id_1 != session_id_2
    assert session_id_1 == "scanner-2025-11-21"
    assert session_id_2 == "scanner-2025-11-22"
