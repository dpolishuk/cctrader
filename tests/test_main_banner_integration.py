"""Integration tests for session banner in CLI commands."""
import pytest
import pytest_asyncio
from pathlib import Path
import tempfile
import os
from unittest.mock import patch, AsyncMock, MagicMock
from click.testing import CliRunner

from src.agent.main import cli


@pytest.fixture
def cli_runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
        db_path = Path(tmp.name)

    yield db_path

    # Cleanup
    if db_path.exists():
        os.unlink(db_path)


class TestBannerIntegration:
    """Test that banner is properly integrated in CLI commands."""

    @patch('src.agent.main.TradingAgent')
    @patch('src.agent.cli_banner.show_session_banner')
    def test_analyze_command_shows_banner(self, mock_banner, mock_agent, cli_runner, temp_db):
        """Test that analyze command displays session banner."""
        # Mock agent initialization and cleanup
        mock_agent_instance = AsyncMock()
        mock_agent_instance.analyze_market = AsyncMock()
        mock_agent_instance.initialize = AsyncMock()
        mock_agent_instance.cleanup = AsyncMock()
        mock_agent_instance.token_tracker = None
        mock_agent.return_value = mock_agent_instance

        # Mock banner as async
        mock_banner.return_value = None

        with patch.dict(os.environ, {"DB_PATH": str(temp_db)}):
            result = cli_runner.invoke(cli, ['analyze', '--symbol', 'BTC/USDT'])

        # Verify banner was called
        assert mock_banner.called, "Banner should be displayed"
        call_args = mock_banner.call_args
        assert call_args[1]['operation_type'] == 'analysis'
        assert call_args[1]['model'] == 'claude-sonnet-4-5'
        assert call_args[1]['session_manager'] is not None

    @patch('src.agent.main.TradingAgent')
    @patch('src.agent.cli_banner.show_session_banner')
    def test_monitor_command_shows_banner(self, mock_banner, mock_agent, cli_runner, temp_db):
        """Test that monitor command displays session banner."""
        # Mock agent initialization and methods
        mock_agent_instance = AsyncMock()
        mock_agent_instance.continuous_monitor = AsyncMock(side_effect=KeyboardInterrupt())
        mock_agent_instance.initialize = AsyncMock()
        mock_agent_instance.cleanup = AsyncMock()
        mock_agent.return_value = mock_agent_instance

        mock_banner.return_value = None

        with patch.dict(os.environ, {"DB_PATH": str(temp_db)}):
            result = cli_runner.invoke(cli, ['monitor', '--symbol', 'BTC/USDT'])

        # Verify banner was called
        assert mock_banner.called, "Banner should be displayed"
        call_args = mock_banner.call_args
        assert call_args[1]['operation_type'] == 'monitor'
        assert call_args[1]['model'] == 'claude-sonnet-4-5'

    @patch('src.agent.main.TradingAgent')
    @patch('src.agent.cli_banner.show_session_banner')
    def test_paper_monitor_command_shows_banner(self, mock_banner, mock_agent, cli_runner, temp_db):
        """Test that paper_monitor command displays session banner."""
        # Mock agent initialization and methods
        mock_agent_instance = AsyncMock()
        mock_agent_instance.continuous_monitor = AsyncMock(side_effect=KeyboardInterrupt())
        mock_agent_instance.initialize = AsyncMock()
        mock_agent.return_value = mock_agent_instance

        mock_banner.return_value = None

        with patch.dict(os.environ, {"DB_PATH": str(temp_db)}):
            result = cli_runner.invoke(cli, ['paper-monitor', '--symbol', 'BTC/USDT'])

        # Verify banner was called
        assert mock_banner.called, "Banner should be displayed"
        call_args = mock_banner.call_args
        assert call_args[1]['operation_type'] == 'paper_trading'
        assert call_args[1]['model'] == 'claude-sonnet-4-5'

    @patch('src.agent.cli_banner.show_session_banner')
    def test_scan_movers_command_shows_banner(self, mock_banner, cli_runner, temp_db):
        """Test that scan_movers command displays session banner."""
        # Mock banner as async
        mock_banner.return_value = None

        # Mock all the components needed by scan_movers
        with patch.dict(os.environ, {"DB_PATH": str(temp_db)}):
            with patch('src.agent.database.paper_schema.init_paper_trading_db', new=AsyncMock()):
                with patch('src.agent.database.movers_schema.create_movers_tables', new=AsyncMock()):
                    with patch('src.agent.database.paper_operations.PaperTradingDatabase') as mock_db:
                        mock_db_instance = AsyncMock()
                        mock_db_instance.get_portfolio_by_name = AsyncMock(return_value={'id': 1})
                        mock_db.return_value = mock_db_instance

                        with patch('src.agent.paper_trading.portfolio_manager.PaperPortfolioManager') as mock_portfolio:
                            mock_portfolio_instance = AsyncMock()
                            mock_portfolio_instance.initialize = AsyncMock()
                            mock_portfolio.return_value = mock_portfolio_instance

                            with patch('src.agent.tools.market_data.get_exchange'):
                                with patch('src.agent.scanner.main_loop.MarketMoversScanner') as mock_scanner:
                                    mock_scanner_instance = MagicMock()
                                    mock_scanner_instance.start = AsyncMock(side_effect=KeyboardInterrupt())
                                    mock_scanner_instance.stop = MagicMock()
                                    mock_scanner_instance.config = MagicMock()
                                    mock_scanner.return_value = mock_scanner_instance

                                    with patch('src.agent.database.token_schema.create_token_tracking_tables', new=AsyncMock()):
                                        result = cli_runner.invoke(cli, ['scan-movers'])

        # Verify banner was called
        assert mock_banner.called, "Banner should be displayed"
        call_args = mock_banner.call_args
        assert call_args[1]['operation_type'] == 'scanner'
        assert call_args[1]['model'] == 'claude-sonnet-4-5'

    def test_banner_timing_in_analyze(self, cli_runner, temp_db):
        """Test that banner appears after DB init but before agent init."""
        call_order = []

        async def track_banner(*args, **kwargs):
            call_order.append('banner')

        def track_agent_creation(*args, **kwargs):
            # Track when TradingAgent is instantiated
            call_order.append('agent_creation')
            mock_instance = AsyncMock()
            mock_instance.analyze_market = AsyncMock()
            mock_instance.cleanup = AsyncMock()
            mock_instance.token_tracker = None
            return mock_instance

        with patch('src.agent.cli_banner.show_session_banner', side_effect=track_banner):
            with patch('src.agent.main.TradingAgent', side_effect=track_agent_creation):
                with patch.dict(os.environ, {"DB_PATH": str(temp_db)}):
                    result = cli_runner.invoke(cli, ['analyze'])

        # Verify banner comes before agent creation
        assert 'banner' in call_order, "Banner should be called"
        assert 'agent_creation' in call_order, "Agent should be created"
        banner_idx = call_order.index('banner')
        agent_idx = call_order.index('agent_creation')
        assert banner_idx < agent_idx, "Banner should appear before agent creation"
