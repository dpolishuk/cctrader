import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agent.scanner.main_loop import MarketMoversScanner
from agent.scanner.config import ScannerConfig
from agent.scanner.risk_config import RiskConfig

@pytest.mark.asyncio
async def test_scanner_initialization():
    """Test scanner initializes with dependencies."""
    mock_exchange = AsyncMock()
    mock_agent = AsyncMock()
    mock_portfolio = AsyncMock()
    mock_db = AsyncMock()

    scanner = MarketMoversScanner(
        exchange=mock_exchange,
        agent=mock_agent,
        portfolio=mock_portfolio,
        db=mock_db
    )

    assert scanner.exchange == mock_exchange
    assert scanner.agent == mock_agent
    assert scanner.portfolio == mock_portfolio
    assert scanner.db == mock_db
    assert isinstance(scanner.config, ScannerConfig)
    assert isinstance(scanner.risk_config, RiskConfig)

@pytest.mark.asyncio
async def test_pre_filter_movers_by_volume():
    """Test pre-filtering movers by volume threshold."""
    mock_exchange = AsyncMock()
    mock_exchange.fetch_ticker = AsyncMock(side_effect=[
        {'quoteVolume': 10_000_000},  # BTC - high volume
        {'quoteVolume': 1_000_000},    # ETH - low volume (below 5M)
    ])

    scanner = MarketMoversScanner(
        exchange=mock_exchange,
        agent=AsyncMock(),
        portfolio=AsyncMock(),
        db=AsyncMock()
    )

    movers = {
        'gainers': [
            {'symbol': 'BTC/USDT', 'max_change': 8.0},
            {'symbol': 'ETH/USDT', 'max_change': 6.0},
        ],
        'losers': []
    }

    filtered = await scanner.pre_filter_movers(movers)

    assert len(filtered) == 1
    assert filtered[0]['symbol'] == 'BTC/USDT'

@pytest.mark.asyncio
async def test_scanner_respects_max_movers_limit():
    """Test scanner limits to max_movers_per_scan."""
    mock_exchange = AsyncMock()
    mock_exchange.fetch_ticker = AsyncMock(return_value={'quoteVolume': 10_000_000})

    scanner = MarketMoversScanner(
        exchange=mock_exchange,
        agent=AsyncMock(),
        portfolio=AsyncMock(),
        db=AsyncMock()
    )
    scanner.config.max_movers_per_scan = 2

    # Create 5 movers
    movers = {
        'gainers': [
            {'symbol': f'SYM{i}/USDT', 'max_change': 10 - i}
            for i in range(5)
        ],
        'losers': []
    }

    filtered = await scanner.pre_filter_movers(movers)

    assert len(filtered) == 2
    # Should take highest % change
    assert filtered[0]['max_change'] == 10
    assert filtered[1]['max_change'] == 9
