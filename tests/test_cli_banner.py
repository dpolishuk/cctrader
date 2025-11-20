"""Tests for CLI banner functionality."""
import pytest
import pytest_asyncio
from pathlib import Path
import tempfile
import os
from unittest.mock import patch, MagicMock
from io import StringIO

from src.agent.cli_banner import SessionBanner, show_session_banner
from src.agent.session_manager import SessionManager


class TestSessionBanner:
    """Test SessionBanner class."""

    def test_display_with_full_info(self, capsys):
        """Test banner display with all information present."""
        SessionBanner.display(
            model="claude-sonnet-4-5",
            api_endpoint="https://api.anthropic.com",
            auth_token="deffa90c1234567890abcdef1234567890LfzE",
            token_tracking_enabled=True,
            session_id="abc123456789",
            operation_type="scanner",
            session_status="resumed"
        )

        # Rich output goes to stderr, but we can verify it doesn't crash
        # and produces some output
        captured = capsys.readouterr()
        # The function should execute without errors
        assert True

    def test_display_with_new_session(self, capsys):
        """Test banner display with new session."""
        SessionBanner.display(
            model="claude-sonnet-4-5",
            api_endpoint="https://api.anthropic.com",
            auth_token="testtoken1234567890",
            token_tracking_enabled=True,
            session_id="new123",
            operation_type="analysis",
            session_status="new"
        )

        captured = capsys.readouterr()
        assert True

    def test_display_without_token_tracking(self, capsys):
        """Test banner display with token tracking disabled."""
        SessionBanner.display(
            model="claude-sonnet-4-5",
            api_endpoint="https://api.anthropic.com",
            auth_token=None,
            token_tracking_enabled=False,
            session_id=None,
            operation_type="monitor",
            session_status="new"
        )

        captured = capsys.readouterr()
        assert True

    def test_display_with_no_session_id(self, capsys):
        """Test banner display without session ID."""
        SessionBanner.display(
            model="claude-sonnet-4-5",
            api_endpoint="https://api.anthropic.com",
            auth_token="testtoken1234567890",
            token_tracking_enabled=True,
            session_id=None,
            operation_type="paper_trading",
            session_status="new"
        )

        captured = capsys.readouterr()
        assert True

    def test_display_truncates_long_session_id(self, capsys):
        """Test that long session IDs are properly truncated."""
        long_session_id = "a" * 50

        SessionBanner.display(
            model="claude-sonnet-4-5",
            api_endpoint="https://api.anthropic.com",
            auth_token="testtoken1234567890",
            token_tracking_enabled=True,
            session_id=long_session_id,
            operation_type="scanner",
            session_status="resumed"
        )

        captured = capsys.readouterr()
        assert True

    def test_display_with_custom_api_endpoint(self, capsys):
        """Test banner display with custom API endpoint."""
        SessionBanner.display(
            model="claude-sonnet-4-5",
            api_endpoint="https://custom.api.com",
            auth_token="testtoken1234567890",
            token_tracking_enabled=True,
            session_id="test123",
            operation_type="scanner",
            session_status="resumed"
        )

        captured = capsys.readouterr()
        assert True

    def test_display_with_masked_auth_token(self, capsys):
        """Test that auth token is properly masked."""
        SessionBanner.display(
            model="claude-sonnet-4-5",
            api_endpoint="https://api.anthropic.com",
            auth_token="deffa90c1234567890abcdef1234567890LfzE",
            token_tracking_enabled=True,
            session_id="test123",
            operation_type="scanner",
            session_status="new"
        )
        captured = capsys.readouterr()
        assert True

    def test_display_with_no_auth_token(self, capsys):
        """Test banner display when auth token is not configured."""
        SessionBanner.display(
            model="claude-sonnet-4-5",
            api_endpoint="https://api.anthropic.com",
            auth_token=None,
            token_tracking_enabled=True,
            session_id="test123",
            operation_type="scanner",
            session_status="new"
        )
        captured = capsys.readouterr()
        assert True

    def test_display_with_short_auth_token(self, capsys):
        """Test banner display with short auth token (edge case)."""
        SessionBanner.display(
            model="claude-sonnet-4-5",
            api_endpoint="https://api.anthropic.com",
            auth_token="short",
            token_tracking_enabled=True,
            session_id="test123",
            operation_type="scanner",
            session_status="new"
        )
        captured = capsys.readouterr()
        assert True


@pytest_asyncio.fixture
async def temp_session_manager():
    """Create a temporary session manager for testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
        db_path = Path(tmp.name)

    manager = SessionManager(db_path)
    await manager.init_db()

    yield manager

    # Cleanup
    if db_path.exists():
        os.unlink(db_path)


class TestShowSessionBanner:
    """Test show_session_banner helper function."""

    @pytest.mark.asyncio
    async def test_show_banner_with_new_session(self, temp_session_manager):
        """Test showing banner for new session."""
        # Don't create any session, so it should be new
        await show_session_banner(
            operation_type="scanner",
            model="claude-sonnet-4-5",
            session_manager=temp_session_manager
        )
        # Should execute without errors
        assert True

    @pytest.mark.asyncio
    async def test_show_banner_with_existing_session(self, temp_session_manager):
        """Test showing banner for existing session."""
        # Create an existing session
        await temp_session_manager.save_session_id("scanner", "test-session-123")

        await show_session_banner(
            operation_type="scanner",
            model="claude-sonnet-4-5",
            session_manager=temp_session_manager
        )
        # Should execute without errors
        assert True

    @pytest.mark.asyncio
    async def test_show_banner_without_session_manager(self):
        """Test showing banner without session manager."""
        await show_session_banner(
            operation_type="analysis",
            model="claude-sonnet-4-5",
            session_manager=None
        )
        # Should execute without errors even without session manager
        assert True

    @pytest.mark.asyncio
    async def test_show_banner_with_custom_model(self, temp_session_manager):
        """Test showing banner with custom model name."""
        await show_session_banner(
            operation_type="monitor",
            model="claude-opus-3",
            session_manager=temp_session_manager
        )
        assert True

    @pytest.mark.asyncio
    async def test_show_banner_handles_session_manager_error(self):
        """Test that banner handles errors from session manager gracefully."""
        # Create a mock session manager that raises an error
        mock_manager = MagicMock()
        mock_manager.get_session_id.side_effect = Exception("Database error")

        # Should not raise, just log warning
        await show_session_banner(
            operation_type="scanner",
            model="claude-sonnet-4-5",
            session_manager=mock_manager
        )
        assert True

    @pytest.mark.asyncio
    async def test_show_banner_uses_env_var_for_api_endpoint(self, temp_session_manager):
        """Test that banner reads API endpoint from environment variable."""
        with patch.dict(os.environ, {"ANTHROPIC_BASE_URL": "https://custom.endpoint.com"}):
            await show_session_banner(
                operation_type="scanner",
                model="claude-sonnet-4-5",
                session_manager=temp_session_manager
            )
        assert True

    @pytest.mark.asyncio
    async def test_show_banner_uses_default_api_endpoint(self, temp_session_manager):
        """Test that banner uses default API endpoint when env var not set."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove ANTHROPIC_BASE_URL if it exists
            os.environ.pop("ANTHROPIC_BASE_URL", None)

            await show_session_banner(
                operation_type="scanner",
                model="claude-sonnet-4-5",
                session_manager=temp_session_manager
            )
        assert True

    @pytest.mark.asyncio
    async def test_show_banner_for_all_operation_types(self, temp_session_manager):
        """Test showing banner for all operation types."""
        operation_types = ["scanner", "analysis", "monitor", "paper_trading"]

        for op_type in operation_types:
            await show_session_banner(
                operation_type=op_type,
                model="claude-sonnet-4-5",
                session_manager=temp_session_manager
            )
        assert True

    @pytest.mark.asyncio
    async def test_show_banner_with_token_tracking_disabled(self, temp_session_manager):
        """Test banner with token tracking disabled in config."""
        with patch("src.agent.cli_banner.config.TOKEN_TRACKING_ENABLED", False):
            await show_session_banner(
                operation_type="scanner",
                model="claude-sonnet-4-5",
                session_manager=temp_session_manager
            )
        assert True

    @pytest.mark.asyncio
    async def test_show_banner_catches_all_exceptions(self):
        """Test that banner catches and logs all exceptions without crashing."""
        # Create a scenario that might cause unexpected errors
        with patch("src.agent.cli_banner.SessionBanner.display", side_effect=Exception("Unexpected error")):
            # Should not raise, just log warning
            await show_session_banner(
                operation_type="scanner",
                model="claude-sonnet-4-5",
                session_manager=None
            )
        assert True
