# tests/test_symbol_manager.py
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from agent.scanner.symbol_manager import FuturesSymbolManager

@pytest.mark.asyncio
async def test_refresh_symbols_filters_usdt_futures():
    """Test symbol manager filters for USDT perpetual futures."""
    mock_exchange = AsyncMock()
    mock_exchange.load_markets = AsyncMock(return_value={
        'BTC/USDT': {
            'type': 'swap',
            'quote': 'USDT',
            'info': {'quoteCoin': 'USDT'},
        },
        'ETH/USDT': {
            'type': 'swap',
            'quote': 'USDT',
            'info': {'quoteCoin': 'USDT'},
        },
        'BTC/USD': {  # Should be filtered out
            'type': 'swap',
            'quote': 'USD',
            'info': {'quoteCoin': 'USD'},
        },
        'BTC/USDT:USDT': {  # Spot, should be filtered
            'type': 'spot',
            'quote': 'USDT',
            'info': {},
        },
    })

    mock_exchange.fetch_tickers = AsyncMock(return_value={
        'BTC/USDT': {'quoteVolume': 10_000_000},
        'ETH/USDT': {'quoteVolume': 6_000_000},
    })

    manager = FuturesSymbolManager(mock_exchange, min_volume_usd=5_000_000)
    symbols = await manager.refresh_symbols()

    assert len(symbols) == 2
    assert 'BTC/USDT' in symbols
    assert 'ETH/USDT' in symbols
    assert 'BTC/USD' not in symbols

@pytest.mark.asyncio
async def test_refresh_symbols_filters_by_volume():
    """Test symbol manager filters by minimum volume."""
    mock_exchange = AsyncMock()
    mock_exchange.load_markets = AsyncMock(return_value={
        'BTC/USDT': {'type': 'swap', 'quote': 'USDT', 'info': {'quoteCoin': 'USDT'}},
        'LOWVOL/USDT': {'type': 'swap', 'quote': 'USDT', 'info': {'quoteCoin': 'USDT'}},
    })

    mock_exchange.fetch_tickers = AsyncMock(return_value={
        'BTC/USDT': {'quoteVolume': 10_000_000},
        'LOWVOL/USDT': {'quoteVolume': 100_000},  # Below threshold
    })

    manager = FuturesSymbolManager(mock_exchange, min_volume_usd=5_000_000)
    symbols = await manager.refresh_symbols()

    assert len(symbols) == 1
    assert 'BTC/USDT' in symbols
    assert 'LOWVOL/USDT' not in symbols

@pytest.mark.asyncio
async def test_get_symbols_returns_cached():
    """Test get_symbols returns cached symbols without refresh."""
    mock_exchange = AsyncMock()
    manager = FuturesSymbolManager(mock_exchange)
    manager.symbols = {'BTC/USDT': {}, 'ETH/USDT': {}}

    symbols = manager.get_symbols()

    assert len(symbols) == 2
    mock_exchange.load_markets.assert_not_called()

def test_should_refresh_logic():
    """Test should_refresh method returns correct refresh status."""
    mock_exchange = MagicMock()
    manager = FuturesSymbolManager(mock_exchange)

    # Test 1: Returns True when never refreshed (last_refresh is None)
    assert manager.should_refresh() is True

    # Test 2: Returns False immediately after refresh
    manager.last_refresh = datetime.now()
    assert manager.should_refresh(refresh_interval_minutes=60) is False

    # Test 3: Returns True after interval expires
    manager.last_refresh = datetime.now() - timedelta(minutes=61)
    assert manager.should_refresh(refresh_interval_minutes=60) is True
