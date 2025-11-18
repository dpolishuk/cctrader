# Market Movers Trading Strategy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an AI-powered momentum trading system that scans all Bybit USDT futures for ±5% movers, analyzes them with Claude Agent SDK, and auto-executes paper trades with confidence-based position sizing.

**Architecture:** Two-tier system: (1) Python scanner detects movers and queues them, (2) Claude Agent performs deep multi-factor analysis (technical + sentiment + liquidity + correlation) and makes trading decisions. Portfolio-level risk controls prevent over-exposure.

**Tech Stack:** Python 3.10+, CCXT (Bybit), Claude Agent SDK, pandas-ta, SQLite, asyncio, Perplexity MCP

---

## Prerequisites

Before starting:
- Review design document: `docs/plans/2025-11-18-market-movers-trading-strategy-design.md`
- Existing codebase has: CCXT setup, paper trading database, agent tools for market data/technical analysis/sentiment
- Database schema already supports paper trading positions
- Agent SDK already configured

---

## Task 1: Create Scanner Configuration

**Files:**
- Create: `agent/scanner/config.py`
- Test: `tests/test_scanner_config.py`

**Step 1: Write failing test for scanner config**

```python
# tests/test_scanner_config.py
import pytest
from agent.scanner.config import ScannerConfig

def test_scanner_config_defaults():
    """Test scanner configuration has correct defaults."""
    config = ScannerConfig()

    assert config.scan_interval_seconds == 300
    assert config.mover_threshold_pct == 5.0
    assert config.max_movers_per_scan == 20
    assert config.min_volume_usd == 5_000_000
    assert config.min_confidence == 60
    assert config.monitoring_interval_seconds == 300

def test_scanner_config_from_env(monkeypatch):
    """Test scanner configuration from environment variables."""
    monkeypatch.setenv('SCAN_INTERVAL', '600')
    monkeypatch.setenv('MOVER_THRESHOLD', '7.0')

    config = ScannerConfig()

    assert config.scan_interval_seconds == 600
    assert config.mover_threshold_pct == 7.0
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_scanner_config.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'agent.scanner'"

**Step 3: Create scanner module structure**

```bash
mkdir -p agent/scanner
touch agent/scanner/__init__.py
```

**Step 4: Write minimal implementation**

```python
# agent/scanner/__init__.py
"""Market movers scanner module."""
from .config import ScannerConfig

__all__ = ['ScannerConfig']
```

```python
# agent/scanner/config.py
"""Scanner configuration."""
import os
from dataclasses import dataclass

@dataclass
class ScannerConfig:
    """Configuration for market movers scanner."""

    # Scanning parameters
    scan_interval_seconds: int = int(os.getenv('SCAN_INTERVAL', '300'))
    mover_threshold_pct: float = float(os.getenv('MOVER_THRESHOLD', '5.0'))
    max_movers_per_scan: int = int(os.getenv('MAX_MOVERS_PER_SCAN', '20'))
    min_volume_usd: float = float(os.getenv('MIN_VOLUME_USD', '5000000'))

    # Agent analysis
    min_confidence: int = int(os.getenv('MIN_CONFIDENCE', '60'))
    agent_timeout_seconds: int = int(os.getenv('AGENT_TIMEOUT', '120'))
    max_perplexity_queries_per_cycle: int = 20

    # Position management
    monitoring_interval_seconds: int = int(os.getenv('MONITORING_INTERVAL', '300'))
    reanalysis_interval_seconds: int = 900
    trailing_stop_update_seconds: int = 300
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_scanner_config.py -v
```

Expected: PASS (2 tests)

**Step 6: Commit**

```bash
git add agent/scanner/ tests/test_scanner_config.py
git commit -m "feat(scanner): add scanner configuration module

- Create ScannerConfig dataclass with defaults
- Support environment variable overrides
- Add tests for default and env-based config"
```

---

## Task 2: Create Risk Configuration

**Files:**
- Create: `agent/scanner/risk_config.py`
- Test: `tests/test_risk_config.py`

**Step 1: Write failing test for risk config**

```python
# tests/test_risk_config.py
import pytest
from agent.scanner.risk_config import RiskConfig, ConfidenceTier

def test_risk_config_defaults():
    """Test risk configuration has correct portfolio limits."""
    config = RiskConfig()

    assert config.max_concurrent_positions == 5
    assert config.max_total_exposure_pct == 25.0
    assert config.daily_loss_limit_pct == -8.0
    assert config.weekly_loss_limit_pct == -15.0
    assert config.max_correlated_positions == 2

def test_confidence_tier_risk_calculation():
    """Test position sizing based on confidence tiers."""
    config = RiskConfig()

    # High confidence: 80-100 → 2.5% risk
    high_risk = config.get_risk_pct_for_confidence(85)
    assert high_risk == 2.5

    # Medium confidence: 60-79 → 1.5% risk
    medium_risk = config.get_risk_pct_for_confidence(70)
    assert medium_risk == 1.5

    # Low confidence: <60 → 0% (no trade)
    low_risk = config.get_risk_pct_for_confidence(50)
    assert low_risk == 0.0

def test_correlation_groups():
    """Test correlation group definitions."""
    config = RiskConfig()

    assert 'BTC_CORRELATED' in config.correlation_groups
    assert 'BTC' in config.correlation_groups['BTC_CORRELATED']
    assert 'ETH' in config.correlation_groups['BTC_CORRELATED']
    assert 'DEFI' in config.correlation_groups
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_risk_config.py -v
```

Expected: FAIL with "cannot import name 'RiskConfig'"

**Step 3: Write minimal implementation**

```python
# agent/scanner/risk_config.py
"""Risk management configuration."""
import os
from dataclasses import dataclass, field
from typing import Dict, List
from enum import Enum

class ConfidenceTier(Enum):
    """Confidence tiers for position sizing."""
    HIGH = (80, 100, 2.5)       # (min, max, risk_pct)
    MEDIUM = (60, 79, 1.5)
    LOW = (0, 59, 0.0)

@dataclass
class RiskConfig:
    """Risk management configuration."""

    # Portfolio limits
    max_concurrent_positions: int = 5
    max_total_exposure_pct: float = 25.0

    # Loss limits
    daily_loss_limit_pct: float = -8.0
    weekly_loss_limit_pct: float = -15.0

    # Correlation limits
    max_correlated_positions: int = 2

    # Stop-loss parameters
    min_stop_distance_pct: float = 2.0
    max_stop_distance_pct: float = 5.0

    # Trailing stop parameters
    breakeven_trigger_pct: float = 1.0
    trailing_trigger_pct: float = 2.0
    trailing_distance_high_confidence: float = 2.5
    trailing_distance_medium_confidence: float = 2.0

    # Profit targets
    tp1_risk_reward_ratio: float = 2.0
    tp1_exit_percentage: float = 0.5

    # Correlation groups
    correlation_groups: Dict[str, List[str]] = field(default_factory=lambda: {
        'BTC_CORRELATED': ['BTC', 'ETH', 'BNB', 'SOL', 'ADA', 'AVAX', 'DOT', 'MATIC'],
        'DEFI': ['UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'CRV', 'SUSHI'],
        'GAMING': ['AXS', 'SAND', 'MANA', 'ENJ', 'GALA', 'ILV'],
        'AI': ['FET', 'AGIX', 'OCEAN', 'GRT'],
        'MEME': ['DOGE', 'SHIB', 'PEPE', 'FLOKI'],
        'LAYER2': ['ARB', 'OP', 'MATIC', 'IMX'],
    })

    def get_risk_pct_for_confidence(self, confidence: int) -> float:
        """Get risk percentage based on confidence score."""
        for tier in ConfidenceTier:
            min_conf, max_conf, risk_pct = tier.value
            if min_conf <= confidence <= max_conf:
                return risk_pct
        return 0.0

    def get_trailing_distance(self, confidence: int) -> float:
        """Get trailing stop distance based on confidence."""
        if confidence >= 80:
            return self.trailing_distance_high_confidence
        else:
            return self.trailing_distance_medium_confidence
```

**Step 4: Update scanner __init__.py**

```python
# agent/scanner/__init__.py
"""Market movers scanner module."""
from .config import ScannerConfig
from .risk_config import RiskConfig, ConfidenceTier

__all__ = ['ScannerConfig', 'RiskConfig', 'ConfidenceTier']
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_risk_config.py -v
```

Expected: PASS (3 tests)

**Step 6: Commit**

```bash
git add agent/scanner/risk_config.py agent/scanner/__init__.py tests/test_risk_config.py
git commit -m "feat(scanner): add risk management configuration

- Create RiskConfig with portfolio limits
- Define ConfidenceTier enum for position sizing
- Add correlation group definitions
- Implement risk calculation methods"
```

---

## Task 3: Create Futures Symbol Manager

**Files:**
- Create: `agent/scanner/symbol_manager.py`
- Test: `tests/test_symbol_manager.py`

**Step 1: Write failing test for symbol manager**

```python
# tests/test_symbol_manager.py
import pytest
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
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_symbol_manager.py -v
```

Expected: FAIL with "cannot import name 'FuturesSymbolManager'"

**Step 3: Write minimal implementation**

```python
# agent/scanner/symbol_manager.py
"""Futures symbol manager for market scanning."""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class FuturesSymbolManager:
    """Manages list of tradeable Bybit USDT perpetual futures."""

    def __init__(self, exchange, min_volume_usd: float = 5_000_000):
        """
        Initialize symbol manager.

        Args:
            exchange: CCXT exchange instance
            min_volume_usd: Minimum 24h volume filter
        """
        self.exchange = exchange
        self.min_volume_usd = min_volume_usd
        self.symbols: Dict[str, Any] = {}
        self.last_refresh: Optional[datetime] = None

    async def refresh_symbols(self) -> Dict[str, Any]:
        """
        Fetch and filter tradeable USDT perpetual futures.

        Returns:
            Dict of symbol -> market info
        """
        logger.info("Refreshing futures symbols list...")

        # Load all markets
        markets = await self.exchange.load_markets()

        # Filter for USDT perpetual futures
        usdt_futures = {
            symbol: market
            for symbol, market in markets.items()
            if market.get('type') == 'swap'
            and market.get('quote') == 'USDT'
            and market.get('info', {}).get('quoteCoin') == 'USDT'
        }

        logger.info(f"Found {len(usdt_futures)} USDT perpetual futures")

        # Fetch tickers for volume filtering
        symbols_list = list(usdt_futures.keys())
        tickers = await self.exchange.fetch_tickers(symbols_list)

        # Filter by volume
        self.symbols = {
            symbol: market
            for symbol, market in usdt_futures.items()
            if symbol in tickers
            and tickers[symbol].get('quoteVolume', 0) >= self.min_volume_usd
        }

        self.last_refresh = datetime.now()
        logger.info(f"Filtered to {len(self.symbols)} symbols with ≥${self.min_volume_usd:,.0f} volume")

        return self.symbols

    def get_symbols(self) -> Dict[str, Any]:
        """
        Get cached symbols without refresh.

        Returns:
            Dict of symbol -> market info
        """
        return self.symbols

    def should_refresh(self, refresh_interval_minutes: int = 60) -> bool:
        """
        Check if symbols should be refreshed.

        Args:
            refresh_interval_minutes: Refresh interval in minutes

        Returns:
            True if refresh needed
        """
        if self.last_refresh is None:
            return True

        elapsed = datetime.now() - self.last_refresh
        return elapsed > timedelta(minutes=refresh_interval_minutes)
```

**Step 4: Update scanner __init__.py**

```python
# agent/scanner/__init__.py
"""Market movers scanner module."""
from .config import ScannerConfig
from .risk_config import RiskConfig, ConfidenceTier
from .symbol_manager import FuturesSymbolManager

__all__ = ['ScannerConfig', 'RiskConfig', 'ConfidenceTier', 'FuturesSymbolManager']
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_symbol_manager.py -v
```

Expected: PASS (3 tests)

**Step 6: Commit**

```bash
git add agent/scanner/symbol_manager.py agent/scanner/__init__.py tests/test_symbol_manager.py
git commit -m "feat(scanner): add futures symbol manager

- Implement FuturesSymbolManager class
- Filter for USDT perpetual futures only
- Apply minimum volume threshold
- Cache symbols with refresh interval check"
```

---

## Task 4: Create Momentum Scanner

**Files:**
- Create: `agent/scanner/momentum_scanner.py`
- Test: `tests/test_momentum_scanner.py`

**Step 1: Write failing test for momentum scanner**

```python
# tests/test_momentum_scanner.py
import pytest
from unittest.mock import AsyncMock
from agent.scanner.momentum_scanner import MomentumScanner

@pytest.mark.asyncio
async def test_scan_for_movers_identifies_gainers():
    """Test scanner identifies symbols with ≥5% gains."""
    mock_exchange = AsyncMock()

    # BTC: +6% in 1h, +4% in 4h → Max +6% (gainer)
    mock_exchange.fetch_ohlcv = AsyncMock(side_effect=[
        [[0, 100, 105, 99, 106, 1000], [0, 106, 108, 105, 106, 1000]],  # 1h: +6%
        [[0, 100, 104, 99, 104, 1000], [0, 104, 106, 103, 104, 1000]],  # 4h: +4%
    ])

    scanner = MomentumScanner(mock_exchange, threshold_pct=5.0)
    movers = await scanner.scan_symbol('BTC/USDT')

    assert movers is not None
    assert movers['symbol'] == 'BTC/USDT'
    assert movers['direction'] == 'LONG'
    assert movers['max_change'] >= 5.0
    assert movers['change_1h'] == pytest.approx(6.0, abs=0.1)

@pytest.mark.asyncio
async def test_scan_for_movers_identifies_losers():
    """Test scanner identifies symbols with ≥5% losses."""
    mock_exchange = AsyncMock()

    # ETH: -7% in 1h
    mock_exchange.fetch_ohlcv = AsyncMock(side_effect=[
        [[0, 100, 102, 92, 93, 1000], [0, 93, 94, 91, 93, 1000]],  # 1h: -7%
        [[0, 95, 98, 93, 95, 1000], [0, 95, 96, 94, 95, 1000]],    # 4h: 0%
    ])

    scanner = MomentumScanner(mock_exchange, threshold_pct=5.0)
    movers = await scanner.scan_symbol('ETH/USDT')

    assert movers is not None
    assert movers['direction'] == 'SHORT'
    assert movers['max_change'] >= 5.0

@pytest.mark.asyncio
async def test_scan_for_movers_filters_below_threshold():
    """Test scanner filters symbols below threshold."""
    mock_exchange = AsyncMock()

    # SOL: +3% in 1h (below 5% threshold)
    mock_exchange.fetch_ohlcv = AsyncMock(side_effect=[
        [[0, 100, 103, 99, 103, 1000], [0, 103, 104, 102, 103, 1000]],  # +3%
        [[0, 100, 102, 99, 102, 1000], [0, 102, 103, 101, 102, 1000]],  # +2%
    ])

    scanner = MomentumScanner(mock_exchange, threshold_pct=5.0)
    movers = await scanner.scan_symbol('SOL/USDT')

    assert movers is None

@pytest.mark.asyncio
async def test_scan_all_symbols():
    """Test scanning multiple symbols in batch."""
    mock_exchange = AsyncMock()

    # Setup different responses for different symbols
    responses = {
        'BTC/USDT': [
            [[0, 100, 106, 99, 106, 1000], [0, 106, 108, 105, 106, 1000]],  # +6%
            [[0, 100, 104, 99, 104, 1000], [0, 104, 106, 103, 104, 1000]],
        ],
        'ETH/USDT': [
            [[0, 100, 102, 99, 102, 1000], [0, 102, 103, 101, 102, 1000]],  # +2%
            [[0, 100, 101, 99, 101, 1000], [0, 101, 102, 100, 101, 1000]],
        ],
    }

    call_count = 0
    async def fetch_ohlcv_side_effect(symbol, timeframe, limit):
        nonlocal call_count
        result = responses[symbol][call_count % 2]
        call_count += 1
        return result

    mock_exchange.fetch_ohlcv = AsyncMock(side_effect=fetch_ohlcv_side_effect)

    scanner = MomentumScanner(mock_exchange, threshold_pct=5.0)
    movers = await scanner.scan_all_symbols(['BTC/USDT', 'ETH/USDT'])

    assert len(movers['gainers']) == 1
    assert movers['gainers'][0]['symbol'] == 'BTC/USDT'
    assert len(movers['losers']) == 0
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_momentum_scanner.py -v
```

Expected: FAIL with "cannot import name 'MomentumScanner'"

**Step 3: Write minimal implementation**

```python
# agent/scanner/momentum_scanner.py
"""Momentum scanner for detecting market movers."""
from typing import Dict, List, Optional, Any
import asyncio
import logging

logger = logging.getLogger(__name__)

class MomentumScanner:
    """Scans symbols for momentum exceeding threshold."""

    def __init__(self, exchange, threshold_pct: float = 5.0, batch_size: int = 10):
        """
        Initialize momentum scanner.

        Args:
            exchange: CCXT exchange instance
            threshold_pct: Minimum % change to qualify as mover
            batch_size: Number of symbols to fetch in parallel
        """
        self.exchange = exchange
        self.threshold_pct = threshold_pct
        self.batch_size = batch_size

    async def scan_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Scan single symbol for momentum.

        Args:
            symbol: Trading pair symbol

        Returns:
            Mover data if exceeds threshold, None otherwise
        """
        try:
            # Fetch 1h and 4h data (last 2 candles)
            ohlcv_1h = await self.exchange.fetch_ohlcv(symbol, '1h', limit=2)
            ohlcv_4h = await self.exchange.fetch_ohlcv(symbol, '4h', limit=2)

            # Calculate % changes
            change_1h = ((ohlcv_1h[-1][4] - ohlcv_1h[-2][4]) / ohlcv_1h[-2][4]) * 100
            change_4h = ((ohlcv_4h[-1][4] - ohlcv_4h[-2][4]) / ohlcv_4h[-2][4]) * 100

            # Get max absolute change
            max_change = max(abs(change_1h), abs(change_4h))

            # Check threshold
            if max_change >= self.threshold_pct:
                return {
                    'symbol': symbol,
                    'change_1h': change_1h,
                    'change_4h': change_4h,
                    'max_change': max_change,
                    'direction': 'LONG' if change_1h > 0 else 'SHORT',
                    'current_price': ohlcv_1h[-1][4],
                }

            return None

        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")
            return None

    async def scan_all_symbols(self, symbols: List[str]) -> Dict[str, List[Dict]]:
        """
        Scan all symbols for movers.

        Args:
            symbols: List of symbols to scan

        Returns:
            Dict with 'gainers' and 'losers' lists
        """
        movers = {'gainers': [], 'losers': []}

        # Process in batches
        for i in range(0, len(symbols), self.batch_size):
            batch = symbols[i:i+self.batch_size]

            # Scan batch in parallel
            tasks = [self.scan_symbol(symbol) for symbol in batch]
            results = await asyncio.gather(*tasks)

            # Categorize movers
            for result in results:
                if result is not None:
                    if result['direction'] == 'LONG':
                        movers['gainers'].append(result)
                    else:
                        movers['losers'].append(result)

        # Sort by magnitude
        movers['gainers'].sort(key=lambda x: x['max_change'], reverse=True)
        movers['losers'].sort(key=lambda x: x['max_change'], reverse=True)

        logger.info(f"Found {len(movers['gainers'])} gainers, {len(movers['losers'])} losers")

        return movers
```

**Step 4: Update scanner __init__.py**

```python
# agent/scanner/__init__.py
"""Market movers scanner module."""
from .config import ScannerConfig
from .risk_config import RiskConfig, ConfidenceTier
from .symbol_manager import FuturesSymbolManager
from .momentum_scanner import MomentumScanner

__all__ = [
    'ScannerConfig',
    'RiskConfig',
    'ConfidenceTier',
    'FuturesSymbolManager',
    'MomentumScanner',
]
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_momentum_scanner.py -v
```

Expected: PASS (4 tests)

**Step 6: Commit**

```bash
git add agent/scanner/momentum_scanner.py agent/scanner/__init__.py tests/test_momentum_scanner.py
git commit -m "feat(scanner): add momentum scanner

- Implement MomentumScanner class
- Calculate 1h and 4h percentage changes
- Filter by threshold (default 5%)
- Batch process symbols in parallel
- Categorize into gainers/losers"
```

---

## Task 5: Create Confidence Score Calculator

**Files:**
- Create: `agent/scanner/confidence.py`
- Test: `tests/test_confidence.py`

**Step 1: Write failing test for confidence calculator**

```python
# tests/test_confidence.py
import pytest
from agent.scanner.confidence import ConfidenceCalculator

def test_calculate_technical_score():
    """Test technical analysis score calculation."""
    calculator = ConfidenceCalculator()

    # Mock technical data for 5 timeframes
    technical_data = {
        '4h': {'rsi': 55, 'macd_signal': 'bullish_cross', 'bb_position': 'upper', 'volume_ratio': 2.1},
        '1h': {'rsi': 62, 'macd_signal': 'histogram_positive', 'bb_position': 'upper', 'volume_ratio': 2.3},
        '15m': {'rsi': 58, 'macd_signal': 'histogram_positive', 'bb_position': 'middle', 'volume_ratio': 1.8},
        '5m': {'rsi': 65, 'macd_signal': 'histogram_positive', 'bb_position': 'middle', 'volume_ratio': 1.2},
        '1m': {'rsi': 70, 'macd_signal': 'histogram_positive', 'bb_position': 'middle', 'volume_ratio': 2.0},
    }

    score = calculator.calculate_technical_score(technical_data)

    assert 0 <= score <= 40
    assert score >= 30  # Strong alignment should score high

def test_calculate_sentiment_score_positive():
    """Test sentiment score for positive catalyst."""
    calculator = ConfidenceCalculator()

    sentiment_data = {
        'classification': 'STRONG_POSITIVE',
        'summary': 'Major partnership announced',
    }

    score = calculator.calculate_sentiment_score(sentiment_data, direction='LONG')

    assert 25 <= score <= 30

def test_calculate_sentiment_score_inverted_for_short():
    """Test sentiment score inverted for SHORT positions."""
    calculator = ConfidenceCalculator()

    sentiment_data = {
        'classification': 'STRONG_NEGATIVE',
        'summary': 'Hack reported',
    }

    score = calculator.calculate_sentiment_score(sentiment_data, direction='SHORT')

    assert 25 <= score <= 30  # Negative news good for shorts

def test_calculate_liquidity_score():
    """Test liquidity score calculation."""
    calculator = ConfidenceCalculator()

    liquidity_data = {
        'volume_ratio': 2.3,  # 2.3x average → 20 points
        'bid_ask_spread_pct': 0.03,  # <0.05% → +5 bonus
        'order_book_depth_usd': 680000,  # >500k → +3 bonus
    }

    score = calculator.calculate_liquidity_score(liquidity_data)

    assert score == 20  # Base 20, bonuses included but capped

def test_calculate_correlation_score():
    """Test BTC correlation score calculation."""
    calculator = ConfidenceCalculator()

    correlation_data = {
        'btc_change_1h': 2.1,
        'symbol_change_1h': 7.2,
    }

    score = calculator.calculate_correlation_score(correlation_data)

    # Moving with BTC uptrend + outperforming by >3% = 10 points
    assert score == 10

def test_calculate_final_confidence():
    """Test final confidence score calculation."""
    calculator = ConfidenceCalculator()

    score = calculator.calculate_final_confidence(
        technical=34,
        sentiment=25,
        liquidity=20,
        correlation=10
    )

    assert score == 89
    assert 0 <= score <= 100
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_confidence.py -v
```

Expected: FAIL with "cannot import name 'ConfidenceCalculator'"

**Step 3: Write minimal implementation**

```python
# agent/scanner/confidence.py
"""Confidence score calculation for trading signals."""
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class ConfidenceCalculator:
    """Calculates multi-factor confidence scores (0-100)."""

    # Timeframe weights for technical analysis
    TIMEFRAME_WEIGHTS = {
        '4h': 0.30,
        '1h': 0.25,
        '15m': 0.20,
        '5m': 0.15,
        '1m': 0.10,
    }

    def calculate_technical_score(self, technical_data: Dict[str, Dict[str, Any]]) -> float:
        """
        Calculate technical alignment score (0-40 points).

        Args:
            technical_data: Dict of timeframe -> indicators

        Returns:
            Score 0-40
        """
        weighted_sum = 0.0

        for timeframe, weight in self.TIMEFRAME_WEIGHTS.items():
            if timeframe not in technical_data:
                continue

            data = technical_data[timeframe]
            points = 0

            # RSI scoring
            rsi = data.get('rsi', 50)
            if 30 <= rsi <= 70:
                points += 2
            elif rsi < 30:
                points += 1  # Oversold bounce potential
            elif rsi > 70:
                points -= 1  # Overbought

            # MACD scoring
            macd_signal = data.get('macd_signal', '')
            if macd_signal == 'bullish_cross':
                points += 2
            elif macd_signal == 'bearish_cross':
                points -= 2
            elif macd_signal == 'histogram_positive':
                points += 1

            # Bollinger Bands scoring
            bb_position = data.get('bb_position', 'middle')
            if bb_position in ['upper', 'lower']:
                points += 1

            # Volume scoring
            volume_ratio = data.get('volume_ratio', 1.0)
            if volume_ratio > 1.0:
                points += 2

            # Weight by timeframe
            max_points = 7  # Max possible per timeframe
            weighted_sum += (points / max_points) * weight * 40

        return min(weighted_sum, 40.0)

    def calculate_sentiment_score(self, sentiment_data: Dict[str, Any], direction: str) -> float:
        """
        Calculate sentiment score (0-30 points).

        Args:
            sentiment_data: Sentiment analysis results
            direction: 'LONG' or 'SHORT'

        Returns:
            Score 0-30
        """
        classification = sentiment_data.get('classification', 'NEUTRAL')

        # Base scores for LONG
        score_map = {
            'STRONG_POSITIVE': 27.5,
            'MILD_POSITIVE': 19.5,
            'NEUTRAL': 12.0,
            'MILD_NEGATIVE': 7.0,
            'STRONG_NEGATIVE': 2.0,
        }

        score = score_map.get(classification, 12.0)

        # Invert for SHORT positions
        if direction == 'SHORT':
            score = 30.0 - score

        return score

    def calculate_liquidity_score(self, liquidity_data: Dict[str, Any]) -> float:
        """
        Calculate liquidity score (0-20 points + bonuses).

        Args:
            liquidity_data: Liquidity metrics

        Returns:
            Score 0-20 (capped, but bonuses can push higher internally)
        """
        volume_ratio = liquidity_data.get('volume_ratio', 1.0)

        # Base score from volume
        if volume_ratio >= 2.0:
            score = 20
        elif volume_ratio >= 1.5:
            score = 15
        elif volume_ratio >= 1.0:
            score = 10
        else:
            score = 5

        # Bonuses (but cap total at 20)
        bid_ask_spread = liquidity_data.get('bid_ask_spread_pct', 0.1)
        if bid_ask_spread < 0.05:
            score = min(score + 5, 20)

        order_book_depth = liquidity_data.get('order_book_depth_usd', 0)
        if order_book_depth > 500_000:
            score = min(score + 3, 20)

        return min(score, 20.0)

    def calculate_correlation_score(self, correlation_data: Dict[str, Any]) -> float:
        """
        Calculate BTC correlation score (0-10 points + bonus).

        Args:
            correlation_data: BTC correlation metrics

        Returns:
            Score 0-10
        """
        btc_change = correlation_data.get('btc_change_1h', 0)
        symbol_change = correlation_data.get('symbol_change_1h', 0)
        relative_strength = symbol_change - btc_change

        # Base score
        if btc_change > 0:  # BTC uptrend
            score = 10 if symbol_change > 0 else 5
        else:  # BTC downtrend
            score = 7 if symbol_change > 0 else 3

        # Bonus for strong outperformance
        if relative_strength > 3.0:
            score = min(score + 3, 10)

        return min(score, 10.0)

    def calculate_final_confidence(
        self,
        technical: float,
        sentiment: float,
        liquidity: float,
        correlation: float
    ) -> int:
        """
        Calculate final confidence score.

        Args:
            technical: Technical score (0-40)
            sentiment: Sentiment score (0-30)
            liquidity: Liquidity score (0-20)
            correlation: Correlation score (0-10)

        Returns:
            Final confidence (0-100)
        """
        confidence = technical + sentiment + liquidity + correlation
        confidence = min(max(confidence, 0), 100)  # Clamp 0-100
        return int(confidence)
```

**Step 4: Update scanner __init__.py**

```python
# agent/scanner/__init__.py
"""Market movers scanner module."""
from .config import ScannerConfig
from .risk_config import RiskConfig, ConfidenceTier
from .symbol_manager import FuturesSymbolManager
from .momentum_scanner import MomentumScanner
from .confidence import ConfidenceCalculator

__all__ = [
    'ScannerConfig',
    'RiskConfig',
    'ConfidenceTier',
    'FuturesSymbolManager',
    'MomentumScanner',
    'ConfidenceCalculator',
]
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_confidence.py -v
```

Expected: PASS (6 tests)

**Step 6: Commit**

```bash
git add agent/scanner/confidence.py agent/scanner/__init__.py tests/test_confidence.py
git commit -m "feat(scanner): add confidence score calculator

- Implement ConfidenceCalculator class
- Calculate technical score (0-40) with timeframe weights
- Calculate sentiment score (0-30) with direction inversion
- Calculate liquidity score (0-20) with bonuses
- Calculate correlation score (0-10) with BTC alignment
- Combine into final confidence (0-100)"
```

---

## Task 6: Create Risk Validator

**Files:**
- Create: `agent/scanner/risk_validator.py`
- Test: `tests/test_risk_validator.py`

**Step 1: Write failing test for risk validator**

```python
# tests/test_risk_validator.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from agent.scanner.risk_validator import RiskValidator
from agent.scanner.risk_config import RiskConfig

@pytest.mark.asyncio
async def test_validate_all_checks_pass():
    """Test validation when all risk checks pass."""
    mock_portfolio = AsyncMock()
    mock_portfolio.count_open_positions = AsyncMock(return_value=2)
    mock_portfolio.calculate_total_exposure_pct = AsyncMock(return_value=10.0)
    mock_portfolio.calculate_daily_pnl_pct = AsyncMock(return_value=-2.0)
    mock_portfolio.calculate_weekly_pnl_pct = AsyncMock(return_value=3.0)
    mock_portfolio.get_open_positions = AsyncMock(return_value=[])

    config = RiskConfig()
    validator = RiskValidator(config, mock_portfolio)

    signal = {
        'symbol': 'BTC/USDT',
        'confidence': 75,
        'position_size_pct': 2.0,
        'risk_amount_pct': 1.5,
    }

    result = await validator.validate_signal(signal)

    assert result['valid'] is True
    assert result['reason'] is None

@pytest.mark.asyncio
async def test_reject_low_confidence():
    """Test rejection when confidence below threshold."""
    mock_portfolio = AsyncMock()
    config = RiskConfig()
    validator = RiskValidator(config, mock_portfolio)

    signal = {'confidence': 50}

    result = await validator.validate_signal(signal)

    assert result['valid'] is False
    assert 'confidence' in result['reason'].lower()

@pytest.mark.asyncio
async def test_reject_max_positions():
    """Test rejection when at max positions."""
    mock_portfolio = AsyncMock()
    mock_portfolio.count_open_positions = AsyncMock(return_value=5)

    config = RiskConfig()
    validator = RiskValidator(config, mock_portfolio)

    signal = {'confidence': 75}

    result = await validator.validate_signal(signal)

    assert result['valid'] is False
    assert 'position' in result['reason'].lower()

@pytest.mark.asyncio
async def test_reject_exposure_limit():
    """Test rejection when exposure limit exceeded."""
    mock_portfolio = AsyncMock()
    mock_portfolio.count_open_positions = AsyncMock(return_value=2)
    mock_portfolio.calculate_total_exposure_pct = AsyncMock(return_value=20.0)
    mock_portfolio.total_value = 10000

    config = RiskConfig()
    validator = RiskValidator(config, mock_portfolio)

    signal = {
        'confidence': 75,
        'position_size_usd': 800,  # Would push total to 28%
    }

    result = await validator.validate_signal(signal)

    assert result['valid'] is False
    assert 'exposure' in result['reason'].lower()

@pytest.mark.asyncio
async def test_reject_daily_loss_limit():
    """Test rejection when daily loss limit hit."""
    mock_portfolio = AsyncMock()
    mock_portfolio.count_open_positions = AsyncMock(return_value=2)
    mock_portfolio.calculate_total_exposure_pct = AsyncMock(return_value=10.0)
    mock_portfolio.calculate_daily_pnl_pct = AsyncMock(return_value=-8.5)

    config = RiskConfig()
    validator = RiskValidator(config, mock_portfolio)

    signal = {'confidence': 75, 'position_size_pct': 2.0}

    result = await validator.validate_signal(signal)

    assert result['valid'] is False
    assert 'daily' in result['reason'].lower()

@pytest.mark.asyncio
async def test_reject_correlation_limit():
    """Test rejection when too many correlated positions."""
    mock_portfolio = AsyncMock()
    mock_portfolio.count_open_positions = AsyncMock(return_value=2)
    mock_portfolio.calculate_total_exposure_pct = AsyncMock(return_value=10.0)
    mock_portfolio.calculate_daily_pnl_pct = AsyncMock(return_value=-2.0)
    mock_portfolio.calculate_weekly_pnl_pct = AsyncMock(return_value=1.0)

    # Already have 2 BTC-correlated positions
    mock_portfolio.get_open_positions = AsyncMock(return_value=[
        {'symbol': 'ETHUSDT'},
        {'symbol': 'SOLUSDT'},
    ])

    config = RiskConfig()
    validator = RiskValidator(config, mock_portfolio)

    signal = {
        'symbol': 'ADAUSDT',  # Also BTC-correlated
        'confidence': 75,
        'position_size_pct': 2.0,
        'risk_amount_pct': 1.5,
    }

    result = await validator.validate_signal(signal)

    assert result['valid'] is False
    assert 'correlation' in result['reason'].lower()
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_risk_validator.py -v
```

Expected: FAIL with "cannot import name 'RiskValidator'"

**Step 3: Write minimal implementation**

```python
# agent/scanner/risk_validator.py
"""Risk validation for trading signals."""
from typing import Dict, Any
import logging
from .risk_config import RiskConfig

logger = logging.getLogger(__name__)

class RiskValidator:
    """Validates trading signals against portfolio risk limits."""

    def __init__(self, config: RiskConfig, portfolio):
        """
        Initialize risk validator.

        Args:
            config: Risk configuration
            portfolio: Portfolio manager instance
        """
        self.config = config
        self.portfolio = portfolio

    async def validate_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate signal against all risk checks.

        Args:
            signal: Trading signal to validate

        Returns:
            Dict with 'valid' (bool) and 'reason' (str or None)
        """
        # Check 1: Confidence threshold
        confidence = signal.get('confidence', 0)
        if confidence < self.config.min_confidence:
            return {
                'valid': False,
                'reason': f'Confidence {confidence} below threshold {self.config.min_confidence}'
            }

        # Check 2: Position limit
        open_positions = await self.portfolio.count_open_positions()
        if open_positions >= self.config.max_concurrent_positions:
            return {
                'valid': False,
                'reason': f'At maximum {self.config.max_concurrent_positions} positions'
            }

        # Check 3: Exposure limit
        current_exposure = await self.portfolio.calculate_total_exposure_pct()
        position_size_pct = signal.get('position_size_pct', 0)
        position_size_usd = signal.get('position_size_usd', 0)

        if position_size_usd > 0 and hasattr(self.portfolio, 'total_value'):
            new_exposure_pct = (position_size_usd / self.portfolio.total_value) * 100
        else:
            new_exposure_pct = position_size_pct

        total_exposure = current_exposure + new_exposure_pct

        if total_exposure > self.config.max_total_exposure_pct:
            return {
                'valid': False,
                'reason': f'Exposure would be {total_exposure:.1f}% (max {self.config.max_total_exposure_pct}%)'
            }

        # Check 4: Daily loss limit
        daily_pnl = await self.portfolio.calculate_daily_pnl_pct()
        if daily_pnl <= self.config.daily_loss_limit_pct:
            return {
                'valid': False,
                'reason': f'Daily loss limit hit: {daily_pnl:.2f}%'
            }

        # Check 5: Weekly loss limit
        weekly_pnl = await self.portfolio.calculate_weekly_pnl_pct()
        if weekly_pnl <= self.config.weekly_loss_limit_pct:
            return {
                'valid': False,
                'reason': f'Weekly loss limit hit: {weekly_pnl:.2f}%'
            }

        # Check 6: Correlation limit
        correlation_check = await self._check_correlation_limit(signal)
        if not correlation_check['valid']:
            return correlation_check

        # All checks passed
        return {'valid': True, 'reason': None}

    async def _check_correlation_limit(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Check correlation group limits."""
        symbol = signal.get('symbol', '')

        # Find correlation group for new signal
        new_group = None
        for group, symbols in self.config.correlation_groups.items():
            if any(sym in symbol for sym in symbols):
                new_group = group
                break

        if new_group is None:
            # Uncategorized symbol, allow
            return {'valid': True, 'reason': None}

        # Count existing positions in same group
        open_positions = await self.portfolio.get_open_positions()
        count_in_group = 0

        for position in open_positions:
            pos_symbol = position.get('symbol', '')
            for group, symbols in self.config.correlation_groups.items():
                if group == new_group and any(sym in pos_symbol for sym in symbols):
                    count_in_group += 1
                    break

        if count_in_group >= self.config.max_correlated_positions:
            return {
                'valid': False,
                'reason': f'Already have {count_in_group} positions in {new_group} group (max {self.config.max_correlated_positions})'
            }

        return {'valid': True, 'reason': None}
```

**Step 4: Update scanner __init__.py**

```python
# agent/scanner/__init__.py
"""Market movers scanner module."""
from .config import ScannerConfig
from .risk_config import RiskConfig, ConfidenceTier
from .symbol_manager import FuturesSymbolManager
from .momentum_scanner import MomentumScanner
from .confidence import ConfidenceCalculator
from .risk_validator import RiskValidator

__all__ = [
    'ScannerConfig',
    'RiskConfig',
    'ConfidenceTier',
    'FuturesSymbolManager',
    'MomentumScanner',
    'ConfidenceCalculator',
    'RiskValidator',
]
```

**Step 5: Add missing constant to RiskConfig**

```python
# agent/scanner/risk_config.py (add this attribute)
@dataclass
class RiskConfig:
    """Risk management configuration."""

    # ... existing fields ...

    # Minimum confidence threshold for trading
    min_confidence: int = 60
```

**Step 6: Run test to verify it passes**

```bash
pytest tests/test_risk_validator.py -v
```

Expected: PASS (6 tests)

**Step 7: Commit**

```bash
git add agent/scanner/risk_validator.py agent/scanner/risk_config.py agent/scanner/__init__.py tests/test_risk_validator.py
git commit -m "feat(scanner): add risk validation system

- Implement RiskValidator class
- Validate confidence threshold
- Check position and exposure limits
- Enforce daily/weekly loss limits
- Validate correlation constraints
- Add min_confidence to RiskConfig"
```

---

## Task 7: Create Agent Prompt Templates

**Files:**
- Create: `agent/scanner/prompts.py`
- Test: `tests/test_prompts.py`

**Step 1: Write failing test for prompt templates**

```python
# tests/test_prompts.py
import pytest
from agent.scanner.prompts import PromptBuilder

def test_build_analysis_prompt():
    """Test building agent analysis prompt."""
    builder = PromptBuilder()

    mover_context = {
        'symbol': 'SOLUSDT',
        'direction': 'LONG',
        'change_1h': 7.2,
        'change_4h': 5.8,
        'current_price': 145.30,
        'volume_24h': 1_200_000_000,
    }

    portfolio_context = {
        'total_value': 10000,
        'open_positions': 2,
        'exposure_pct': 15.0,
    }

    prompt = builder.build_analysis_prompt(mover_context, portfolio_context)

    assert 'SOLUSDT' in prompt
    assert 'LONG' in prompt
    assert '+7.2%' in prompt
    assert 'multi-timeframe' in prompt.lower()
    assert 'perplexity' in prompt.lower()
    assert 'confidence' in prompt.lower()
    assert '60' in prompt  # Min confidence threshold

def test_build_reanalysis_prompt():
    """Test building position re-analysis prompt."""
    builder = PromptBuilder()

    position = {
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'entry_price': 90000,
        'current_price': 91500,
        'pnl_pct': 1.67,
        'original_confidence': 78,
        'duration_minutes': 45,
    }

    prompt = builder.build_reanalysis_prompt(position)

    assert 'BTCUSDT' in prompt
    assert 'Re-analyze' in prompt
    assert '90000' in prompt or '90,000' in prompt
    assert 'confidence' in prompt.lower()
    assert 'sentiment changed' in prompt.lower()
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_prompts.py -v
```

Expected: FAIL with "cannot import name 'PromptBuilder'"

**Step 3: Write minimal implementation**

```python
# agent/scanner/prompts.py
"""Prompt templates for Claude Agent analysis."""
from typing import Dict, Any

class PromptBuilder:
    """Builds prompts for agent analysis tasks."""

    def build_analysis_prompt(
        self,
        mover_context: Dict[str, Any],
        portfolio_context: Dict[str, Any]
    ) -> str:
        """
        Build prompt for analyzing a market mover.

        Args:
            mover_context: Mover details (symbol, direction, changes, price)
            portfolio_context: Portfolio state (value, positions, exposure)

        Returns:
            Formatted prompt string
        """
        symbol = mover_context['symbol']
        direction = mover_context['direction']
        change_1h = mover_context['change_1h']
        change_4h = mover_context['change_4h']
        current_price = mover_context['current_price']
        volume_24h = mover_context.get('volume_24h', 0)

        portfolio_value = portfolio_context['total_value']
        open_positions = portfolio_context['open_positions']
        exposure_pct = portfolio_context['exposure_pct']

        prompt = f"""Analyze {symbol} as a potential {direction} opportunity.

Context:
- Current momentum: {change_1h:+.2f}% in 1h, {change_4h:+.2f}% in 4h
- Current price: ${current_price:,.2f}
- 24h volume: ${volume_24h:,.0f}
- Paper portfolio: ${portfolio_value:,.0f}
- Open positions: {open_positions}/5
- Current exposure: {exposure_pct:.1f}%

Your task:
1. Gather multi-timeframe technical analysis (1m, 5m, 15m, 1h, 4h)
2. Analyze market sentiment and detect catalysts using Perplexity
3. Check liquidity and volume quality
4. Assess correlation with BTC
5. Calculate confidence score (0-100):
   - Technical alignment: 0-40 points
   - Sentiment: 0-30 points
   - Liquidity: 0-20 points
   - Correlation: 0-10 points
6. Determine if HIGH PROBABILITY trade (confidence ≥ 60)
7. If yes, specify entry, stop-loss, take-profit, position size

Use your tools systematically. Think step-by-step. Show reasoning.

IMPORTANT: Only recommend trades with confidence ≥ 60. Be conservative.
"""
        return prompt

    def build_reanalysis_prompt(self, position: Dict[str, Any]) -> str:
        """
        Build prompt for re-analyzing an open position.

        Args:
            position: Position details

        Returns:
            Formatted prompt string
        """
        symbol = position['symbol']
        direction = position['direction']
        entry_price = position['entry_price']
        current_price = position['current_price']
        pnl_pct = position['pnl_pct']
        original_confidence = position['original_confidence']
        duration = position['duration_minutes']

        prompt = f"""Re-analyze open position for {symbol} {direction}.

Position details:
- Entry: ${entry_price:,.2f} @ {duration} minutes ago
- Current price: ${current_price:,.2f}
- P&L: {pnl_pct:+.2f}%
- Original confidence: {original_confidence}
- Time in position: {duration} minutes

Check:
1. Has market sentiment changed? (query Perplexity)
2. Are technicals still aligned?
3. Any new events or catalysts?
4. Is momentum weakening?

Calculate updated confidence score. If <40, recommend early exit.
"""
        return prompt
```

**Step 4: Update scanner __init__.py**

```python
# agent/scanner/__init__.py
"""Market movers scanner module."""
from .config import ScannerConfig
from .risk_config import RiskConfig, ConfidenceTier
from .symbol_manager import FuturesSymbolManager
from .momentum_scanner import MomentumScanner
from .confidence import ConfidenceCalculator
from .risk_validator import RiskValidator
from .prompts import PromptBuilder

__all__ = [
    'ScannerConfig',
    'RiskConfig',
    'ConfidenceTier',
    'FuturesSymbolManager',
    'MomentumScanner',
    'ConfidenceCalculator',
    'RiskValidator',
    'PromptBuilder',
]
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_prompts.py -v
```

Expected: PASS (2 tests)

**Step 6: Commit**

```bash
git add agent/scanner/prompts.py agent/scanner/__init__.py tests/test_prompts.py
git commit -m "feat(scanner): add agent prompt templates

- Implement PromptBuilder class
- Create analysis prompt with mover + portfolio context
- Create re-analysis prompt for open positions
- Include step-by-step instructions for agent"
```

---

## Task 8: Extend Database Schema for Market Movers

**Files:**
- Create: `agent/database/movers_schema.py`
- Modify: `agent/database/paper_operations.py` (add movers methods)
- Test: `tests/test_movers_database.py`

**Step 1: Write failing test for movers database**

```python
# tests/test_movers_database.py
import pytest
import aiosqlite
from pathlib import Path
from agent.database.movers_schema import create_movers_tables
from agent.database.paper_operations import PaperTradingDatabase

@pytest.mark.asyncio
async def test_create_movers_tables(tmp_path):
    """Test movers tables creation."""
    db_path = tmp_path / "test.db"

    async with aiosqlite.connect(db_path) as db:
        await create_movers_tables(db)
        await db.commit()

    # Verify tables exist
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'movers_%'"
        )
        tables = [row[0] for row in await cursor.fetchall()]

    assert 'movers_signals' in tables
    assert 'movers_rejections' in tables
    assert 'movers_metrics' in tables

@pytest.mark.asyncio
async def test_save_mover_signal(tmp_path):
    """Test saving mover signal."""
    db_path = tmp_path / "test.db"

    async with aiosqlite.connect(db_path) as db:
        await create_movers_tables(db)
        await db.commit()

    db_ops = PaperTradingDatabase(db_path)

    signal_id = await db_ops.save_mover_signal(
        symbol='BTCUSDT',
        direction='LONG',
        confidence=78,
        entry_price=90000,
        stop_loss=87500,
        tp1=95000,
        position_size_usd=200,
        risk_amount_usd=50,
        technical_score=34,
        sentiment_score=23,
        liquidity_score=18,
        correlation_score=5,
        analysis={'summary': 'Strong momentum'}
    )

    assert signal_id > 0

    # Verify saved
    signal = await db_ops.get_mover_signal(signal_id)
    assert signal is not None
    assert signal['symbol'] == 'BTCUSDT'
    assert signal['confidence'] == 78

@pytest.mark.asyncio
async def test_save_mover_rejection(tmp_path):
    """Test saving mover rejection."""
    db_path = tmp_path / "test.db"

    async with aiosqlite.connect(db_path) as db:
        await create_movers_tables(db)
        await db.commit()

    db_ops = PaperTradingDatabase(db_path)

    await db_ops.save_mover_rejection(
        symbol='ETHUSDT',
        direction='LONG',
        confidence=55,
        reason='Confidence below threshold',
        details={'required': 60, 'actual': 55}
    )

    # Verify saved
    rejections = await db_ops.get_recent_rejections(limit=10)
    assert len(rejections) == 1
    assert rejections[0]['symbol'] == 'ETHUSDT'
    assert 'threshold' in rejections[0]['reason']
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_movers_database.py -v
```

Expected: FAIL with "cannot import name 'create_movers_tables'"

**Step 3: Write schema implementation**

```python
# agent/database/movers_schema.py
"""Database schema for market movers strategy."""
import aiosqlite

async def create_movers_tables(db: aiosqlite.Connection):
    """Create tables for market movers strategy."""

    # Signals table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS movers_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            confidence INTEGER NOT NULL,
            entry_price REAL NOT NULL,
            stop_loss REAL NOT NULL,
            tp1 REAL NOT NULL,
            position_size_usd REAL NOT NULL,
            risk_amount_usd REAL NOT NULL,
            technical_score REAL,
            sentiment_score REAL,
            liquidity_score REAL,
            correlation_score REAL,
            analysis TEXT,
            status TEXT DEFAULT 'PENDING'
        )
    """)

    # Rejections table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS movers_rejections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            confidence INTEGER,
            reason TEXT NOT NULL,
            details TEXT
        )
    """)

    # Metrics table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS movers_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            cycle_duration_seconds REAL,
            movers_found INTEGER,
            signals_generated INTEGER,
            signals_executed INTEGER,
            signals_rejected INTEGER,
            open_positions INTEGER,
            total_exposure_pct REAL,
            daily_pnl_pct REAL,
            weekly_pnl_pct REAL,
            risk_level TEXT
        )
    """)

    # Create indexes
    await db.execute("CREATE INDEX IF NOT EXISTS idx_movers_signals_symbol ON movers_signals(symbol)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_movers_signals_timestamp ON movers_signals(timestamp)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_movers_rejections_reason ON movers_rejections(reason)")
```

**Step 4: Add methods to PaperTradingDatabase**

```python
# agent/database/paper_operations.py (add these methods to the class)

import json

# Add these methods to PaperTradingDatabase class:

async def save_mover_signal(
    self,
    symbol: str,
    direction: str,
    confidence: int,
    entry_price: float,
    stop_loss: float,
    tp1: float,
    position_size_usd: float,
    risk_amount_usd: float,
    technical_score: float = None,
    sentiment_score: float = None,
    liquidity_score: float = None,
    correlation_score: float = None,
    analysis: Dict = None
) -> int:
    """Save a mover signal to database."""
    async with aiosqlite.connect(self.db_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO movers_signals
            (symbol, direction, confidence, entry_price, stop_loss, tp1,
             position_size_usd, risk_amount_usd, technical_score, sentiment_score,
             liquidity_score, correlation_score, analysis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (symbol, direction, confidence, entry_price, stop_loss, tp1,
             position_size_usd, risk_amount_usd, technical_score, sentiment_score,
             liquidity_score, correlation_score, json.dumps(analysis) if analysis else None)
        )
        await db.commit()
        return cursor.lastrowid

async def get_mover_signal(self, signal_id: int) -> Optional[Dict]:
    """Get mover signal by ID."""
    async with aiosqlite.connect(self.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM movers_signals WHERE id = ?",
            (signal_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                result = dict(row)
                if result.get('analysis'):
                    result['analysis'] = json.loads(result['analysis'])
                return result
            return None

async def save_mover_rejection(
    self,
    symbol: str,
    direction: str,
    confidence: int,
    reason: str,
    details: Dict = None
) -> int:
    """Save a mover rejection to database."""
    async with aiosqlite.connect(self.db_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO movers_rejections
            (symbol, direction, confidence, reason, details)
            VALUES (?, ?, ?, ?, ?)
            """,
            (symbol, direction, confidence, reason, json.dumps(details) if details else None)
        )
        await db.commit()
        return cursor.lastrowid

async def get_recent_rejections(self, limit: int = 10) -> List[Dict]:
    """Get recent rejections."""
    async with aiosqlite.connect(self.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM movers_rejections ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                result = dict(row)
                if result.get('details'):
                    result['details'] = json.loads(result['details'])
                results.append(result)
            return results

async def save_movers_metrics(self, metrics: Dict) -> int:
    """Save movers scan cycle metrics."""
    async with aiosqlite.connect(self.db_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO movers_metrics
            (cycle_duration_seconds, movers_found, signals_generated,
             signals_executed, signals_rejected, open_positions,
             total_exposure_pct, daily_pnl_pct, weekly_pnl_pct, risk_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (metrics.get('cycle_duration_seconds'),
             metrics.get('movers_found'),
             metrics.get('signals_generated'),
             metrics.get('signals_executed'),
             metrics.get('signals_rejected'),
             metrics.get('open_positions'),
             metrics.get('total_exposure_pct'),
             metrics.get('daily_pnl_pct'),
             metrics.get('weekly_pnl_pct'),
             metrics.get('risk_level'))
        )
        await db.commit()
        return cursor.lastrowid
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_movers_database.py -v
```

Expected: PASS (3 tests)

**Step 6: Commit**

```bash
git add agent/database/movers_schema.py agent/database/paper_operations.py tests/test_movers_database.py
git commit -m "feat(database): add market movers schema and operations

- Create movers_signals table for signal storage
- Create movers_rejections table for rejection tracking
- Create movers_metrics table for scan cycle metrics
- Add database methods to PaperTradingDatabase
- Add tests for schema and operations"
```

---

## Task 9: Create Main Scanner Loop

**Files:**
- Create: `agent/scanner/main_loop.py`
- Test: `tests/test_main_loop.py`

Due to complexity, this will be implemented with integration test approach.

**Step 1: Write integration test for scanner loop**

```python
# tests/test_main_loop.py
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
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_main_loop.py::test_scanner_initialization -v
```

Expected: FAIL with "cannot import name 'MarketMoversScanner'"

**Step 3: Write implementation (scaffold first)**

```python
# agent/scanner/main_loop.py
"""Main scanner loop for market movers strategy."""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from .config import ScannerConfig
from .risk_config import RiskConfig
from .symbol_manager import FuturesSymbolManager
from .momentum_scanner import MomentumScanner
from .confidence import ConfidenceCalculator
from .risk_validator import RiskValidator
from .prompts import PromptBuilder

logger = logging.getLogger(__name__)

class MarketMoversScanner:
    """Main market movers scanner orchestrator."""

    def __init__(
        self,
        exchange,
        agent,
        portfolio,
        db,
        config: Optional[ScannerConfig] = None,
        risk_config: Optional[RiskConfig] = None
    ):
        """
        Initialize market movers scanner.

        Args:
            exchange: CCXT exchange instance
            agent: Claude Agent instance
            portfolio: Portfolio manager
            db: Database operations instance
            config: Scanner configuration (optional)
            risk_config: Risk configuration (optional)
        """
        self.exchange = exchange
        self.agent = agent
        self.portfolio = portfolio
        self.db = db

        self.config = config or ScannerConfig()
        self.risk_config = risk_config or RiskConfig()

        # Initialize components
        self.symbol_manager = FuturesSymbolManager(
            exchange,
            min_volume_usd=self.config.min_volume_usd
        )
        self.momentum_scanner = MomentumScanner(
            exchange,
            threshold_pct=self.config.mover_threshold_pct
        )
        self.confidence_calculator = ConfidenceCalculator()
        self.risk_validator = RiskValidator(self.risk_config, portfolio)
        self.prompt_builder = PromptBuilder()

        self.running = False

    async def start(self):
        """Start the scanning loop."""
        logger.info("🚀 Market Movers Scanner starting...")

        # Initialize symbol list
        await self.symbol_manager.refresh_symbols()
        logger.info(f"📊 Monitoring {len(self.symbol_manager.get_symbols())} futures pairs")

        self.running = True

        while self.running:
            try:
                await self.scan_cycle()
            except Exception as e:
                logger.error(f"❌ Error in scan cycle: {e}", exc_info=True)
                await asyncio.sleep(30)

            # Wait until next scan
            await asyncio.sleep(self.config.scan_interval_seconds)

    def stop(self):
        """Stop the scanning loop."""
        logger.info("Stopping scanner...")
        self.running = False

    async def scan_cycle(self):
        """Execute one complete scan cycle."""
        cycle_start = datetime.now()
        logger.info(f"\n{'='*80}")
        logger.info(f"🔍 SCAN CYCLE - {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*80}\n")

        # TODO: Implement full scan cycle
        # This is a placeholder
        await asyncio.sleep(1)

        cycle_duration = (datetime.now() - cycle_start).total_seconds()
        logger.info(f"\n⏱️  Cycle completed in {cycle_duration:.1f}s")
        logger.info(f"{'='*80}\n")

    async def pre_filter_movers(self, movers: Dict[str, List]) -> List[Dict]:
        """
        Pre-filter movers by volume before deep analysis.

        Args:
            movers: Dict with 'gainers' and 'losers' lists

        Returns:
            List of filtered movers
        """
        all_movers = movers['gainers'] + movers['losers']

        # Filter by volume
        filtered = []
        for mover in all_movers:
            ticker = await self.exchange.fetch_ticker(mover['symbol'])
            volume_24h = ticker.get('quoteVolume', 0)

            if volume_24h >= self.config.min_volume_usd:
                mover['volume_24h'] = volume_24h
                filtered.append(mover)

        # Sort by % change and take top N
        filtered.sort(key=lambda x: x['max_change'], reverse=True)
        return filtered[:self.config.max_movers_per_scan]
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_main_loop.py -v
```

Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add agent/scanner/main_loop.py tests/test_main_loop.py
git commit -m "feat(scanner): add main scanner loop scaffold

- Implement MarketMoversScanner orchestrator class
- Initialize all scanner components
- Add start/stop methods for main loop
- Implement pre_filter_movers with volume check
- Add scan_cycle placeholder for full implementation"
```

---

## Task 10: Integration with Existing CLI

**Files:**
- Modify: `agent/main.py` (add scanner command)
- Test: Manual testing

**Step 1: Add scanner command to CLI**

```python
# agent/main.py (add this to existing CLI)

# At top of file, add import:
from agent.scanner.main_loop import MarketMoversScanner
from agent.database.movers_schema import create_movers_tables

# Add new command in main():

@click.command()
@click.option('--interval', default=300, help='Scan interval in seconds')
def scan_movers(interval):
    """Run market movers scanner."""
    import asyncio
    from agent.tools.market_data import get_exchange
    from agent.trading_agent import create_agent
    from agent.paper_trading.portfolio_manager import PortfolioManager
    from agent.database.paper_operations import PaperTradingDatabase
    from pathlib import Path

    async def run_scanner():
        # Initialize dependencies
        exchange = get_exchange()
        agent = create_agent()

        db_path = Path(config.DB_PATH)
        db = PaperTradingDatabase(db_path)

        # Create movers tables
        import aiosqlite
        async with aiosqlite.connect(db_path) as conn:
            await create_movers_tables(conn)
            await conn.commit()

        # Get or create portfolio
        portfolio_id = 1  # Default portfolio
        portfolio_data = await db.get_portfolio(portfolio_id)

        if not portfolio_data:
            portfolio_id = await db.create_portfolio(
                name="Market Movers",
                starting_capital=10000.0
            )
            portfolio_data = await db.get_portfolio(portfolio_id)

        portfolio = PortfolioManager(
            portfolio_id=portfolio_id,
            db=db,
            exchange=exchange
        )

        # Create and start scanner
        scanner = MarketMoversScanner(
            exchange=exchange,
            agent=agent,
            portfolio=portfolio,
            db=db
        )

        scanner.config.scan_interval_seconds = interval

        try:
            await scanner.start()
        except KeyboardInterrupt:
            scanner.stop()
            logger.info("Scanner stopped by user")

    asyncio.run(run_scanner())

# Add to main CLI group:
cli.add_command(scan_movers)
```

**Step 2: Test manually**

```bash
python -m agent.main scan-movers --interval 60
```

Expected: Scanner starts, initializes symbol list, begins scan cycles

**Step 3: Commit**

```bash
git add agent/main.py
git commit -m "feat(cli): add scan-movers command

- Add scan_movers CLI command
- Initialize scanner with dependencies
- Create movers database tables on startup
- Support custom scan interval parameter"
```

---

## Next Steps

**Plan saved to:** `docs/plans/2025-11-18-market-movers-implementation.md`

This implementation plan creates the foundation for the Market Movers strategy:
- ✅ Scanner configuration and risk management
- ✅ Symbol management and momentum detection
- ✅ Confidence scoring system
- ✅ Risk validation framework
- ✅ Database schema for movers
- ✅ Main scanner loop scaffold
- ✅ CLI integration

**Remaining work (separate plan recommended):**
1. Complete scan_cycle implementation with agent integration
2. Implement position monitoring loop
3. Add dynamic stop-loss management
4. Build dashboard/reporting
5. Full integration testing with paper trading
6. Performance optimization

**Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**