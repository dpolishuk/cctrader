"""Tests for persistent client mode in AgentWrapper."""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from src.agent.scanner.agent_wrapper import AgentWrapper


@pytest.mark.asyncio
async def test_persistent_client_multiple_analyses():
    """Test that persistent mode reuses same client for multiple analyses."""
    # Create mock options
    mock_options = MagicMock()

    wrapper = AgentWrapper(
        agent_options=mock_options,
        persistent_client=True
    )

    # Mock the client and submit_trading_signal
    with patch('src.agent.scanner.agent_wrapper.ClaudeSDKClient') as MockClient, \
         patch('src.agent.scanner.agent_wrapper.set_signal_queue'), \
         patch('src.agent.scanner.agent_wrapper.clear_signal_queue'):

        # Create mock client
        mock_client = AsyncMock()
        mock_client.query = AsyncMock()
        mock_client.receive_response = AsyncMock(return_value=iter([]))
        mock_client.session_id = "test-session-1"

        # Mock context manager
        MockClient.return_value = mock_client
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        # Mock signal queue to return test signal
        with patch('src.agent.scanner.agent_wrapper.asyncio.Queue') as MockQueue:
            mock_queue = AsyncMock()
            mock_signal = {
                'confidence': 80,
                'symbol': 'TEST/USDT',
                'entry_price': 100.0,
                'stop_loss': 95.0,
                'tp1': 110.0,
                'technical_score': 0.8,
                'sentiment_score': 0.7,
                'liquidity_score': 0.9,
                'correlation_score': 0.6,
                'analysis': 'Test analysis'
            }
            mock_queue.get = AsyncMock(return_value=mock_signal)
            MockQueue.return_value = mock_queue

            # Run multiple analyses
            await wrapper.run("Analysis 1")
            await wrapper.run("Analysis 2")

        # Client should be created only once in persistent mode
        assert MockClient.call_count == 1


@pytest.mark.asyncio
async def test_non_persistent_client_creates_new_each_time():
    """Test that non-persistent mode creates new client for each analysis."""
    # Create mock options
    mock_options = MagicMock()

    wrapper = AgentWrapper(
        agent_options=mock_options,
        persistent_client=False
    )

    with patch('src.agent.scanner.agent_wrapper.ClaudeSDKClient') as MockClient, \
         patch('src.agent.scanner.agent_wrapper.set_signal_queue'), \
         patch('src.agent.scanner.agent_wrapper.clear_signal_queue'):

        # Create mock client
        mock_client = AsyncMock()
        mock_client.query = AsyncMock()
        mock_client.receive_response = AsyncMock(return_value=iter([]))
        mock_client.session_id = "test-session"

        # Mock context manager
        MockClient.return_value = mock_client
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        # Mock signal queue to return test signal
        with patch('src.agent.scanner.agent_wrapper.asyncio.Queue') as MockQueue:
            mock_queue = AsyncMock()
            mock_signal = {
                'confidence': 80,
                'symbol': 'TEST/USDT',
                'entry_price': 100.0,
                'stop_loss': 95.0,
                'tp1': 110.0,
                'technical_score': 0.8,
                'sentiment_score': 0.7,
                'liquidity_score': 0.9,
                'correlation_score': 0.6,
                'analysis': 'Test analysis'
            }
            mock_queue.get = AsyncMock(return_value=mock_signal)
            MockQueue.return_value = mock_queue

            await wrapper.run("Analysis 1")
            await wrapper.run("Analysis 2")

        # Client should be created twice in non-persistent mode
        assert MockClient.call_count == 2
