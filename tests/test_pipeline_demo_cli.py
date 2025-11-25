"""Tests for pipeline demo CLI command."""
import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock, AsyncMock

from src.agent.main import cli


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


def test_pipeline_demo_command_exists(runner):
    """Test that pipeline-demo command exists."""
    result = runner.invoke(cli, ['pipeline-demo', '--help'])
    assert result.exit_code == 0
    assert 'demo' in result.output.lower() or 'pipeline' in result.output.lower()


def test_pipeline_demo_once_option(runner):
    """Test --once flag is available."""
    result = runner.invoke(cli, ['pipeline-demo', '--help'])
    assert '--once' in result.output


def test_pipeline_demo_symbol_option(runner):
    """Test --symbol option is available."""
    result = runner.invoke(cli, ['pipeline-demo', '--help'])
    assert '--symbol' in result.output
