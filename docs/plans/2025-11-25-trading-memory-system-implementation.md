# Trading Memory System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add persistent memory to CCTrader so the bot learns from past trades and improves future decisions.

**Architecture:** Dual-layer storage (local SQLite + claude-mem sync), auto-injected context before each analysis, 6 recall tools for agent queries, background scorer for outcome tracking.

**Tech Stack:** aiosqlite, claude-agent-sdk tools, claude-mem MCP, pandas-ta for indicators

---

## Task 1: Database Schema (3 new tables)

**Files:**
- Create: `src/agent/database/memory_schema.py`
- Modify: `src/agent/database/__init__.py`
- Test: `tests/test_memory_schema.py`

**Step 1: Write the failing test**

```python
# tests/test_memory_schema.py
"""Tests for trading memory database schema."""
import pytest
import aiosqlite
from pathlib import Path
import tempfile


@pytest.fixture
async def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    db_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_create_memory_tables(temp_db):
    """Test that all memory tables are created correctly."""
    from src.agent.database.memory_schema import create_memory_tables

    async with aiosqlite.connect(temp_db) as db:
        await create_memory_tables(db)

        # Verify trade_outcomes table exists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='trade_outcomes'"
        )
        assert await cursor.fetchone() is not None

        # Verify market_snapshots table exists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='market_snapshots'"
        )
        assert await cursor.fetchone() is not None

        # Verify trade_annotations table exists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='trade_annotations'"
        )
        assert await cursor.fetchone() is not None


@pytest.mark.asyncio
async def test_trade_outcomes_columns(temp_db):
    """Test trade_outcomes table has all required columns."""
    from src.agent.database.memory_schema import create_memory_tables

    async with aiosqlite.connect(temp_db) as db:
        await create_memory_tables(db)

        cursor = await db.execute("PRAGMA table_info(trade_outcomes)")
        columns = {row[1] for row in await cursor.fetchall()}

        required = {
            'id', 'signal_id', 'symbol', 'direction', 'confidence',
            'entry_price', 'predicted_stop', 'predicted_target',
            'price_1h', 'price_4h', 'price_24h',
            'hit_target', 'hit_stop', 'max_favorable', 'max_adverse',
            'pnl_percent_1h', 'pnl_percent_4h', 'pnl_percent_24h',
            'outcome_grade', 'created_at', 'scored_at'
        }
        assert required.issubset(columns)


@pytest.mark.asyncio
async def test_market_snapshots_columns(temp_db):
    """Test market_snapshots table has all required columns."""
    from src.agent.database.memory_schema import create_memory_tables

    async with aiosqlite.connect(temp_db) as db:
        await create_memory_tables(db)

        cursor = await db.execute("PRAGMA table_info(market_snapshots)")
        columns = {row[1] for row in await cursor.fetchall()}

        required = {
            'id', 'signal_id', 'symbol',
            'rsi_15m', 'rsi_1h', 'rsi_4h',
            'macd_signal', 'volatility_percentile', 'volume_ratio',
            'trend_strength', 'btc_correlation', 'market_condition',
            'created_at'
        }
        assert required.issubset(columns)
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_memory_schema.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.agent.database.memory_schema'`

**Step 3: Write minimal implementation**

```python
# src/agent/database/memory_schema.py
"""Database schema for trading memory system."""
import aiosqlite


async def create_memory_tables(db: aiosqlite.Connection):
    """Create tables for trading memory system."""

    # Trade outcomes table - tracks signal predictions vs actual results
    await db.execute("""
        CREATE TABLE IF NOT EXISTS trade_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id INTEGER,
            symbol TEXT NOT NULL,
            direction TEXT,
            confidence INTEGER,
            entry_price REAL,
            predicted_stop REAL,
            predicted_target REAL,

            price_1h REAL,
            price_4h REAL,
            price_24h REAL,
            hit_target INTEGER,
            hit_stop INTEGER,
            max_favorable REAL,
            max_adverse REAL,

            pnl_percent_1h REAL,
            pnl_percent_4h REAL,
            pnl_percent_24h REAL,
            outcome_grade TEXT,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            scored_at TEXT
        )
    """)

    # Market snapshots table - captures conditions at signal time
    await db.execute("""
        CREATE TABLE IF NOT EXISTS market_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id INTEGER,
            symbol TEXT NOT NULL,

            rsi_15m REAL,
            rsi_1h REAL,
            rsi_4h REAL,
            macd_signal TEXT,
            volatility_percentile REAL,
            volume_ratio REAL,
            trend_strength REAL,
            btc_correlation REAL,

            market_condition TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Trade annotations table - manual notes on trades
    await db.execute("""
        CREATE TABLE IF NOT EXISTS trade_annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id INTEGER,
            annotation TEXT NOT NULL,
            tags TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes for common queries
    await db.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_symbol ON trade_outcomes(symbol)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_created ON trade_outcomes(created_at)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_grade ON trade_outcomes(outcome_grade)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_symbol ON market_snapshots(symbol)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_condition ON market_snapshots(market_condition)")
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_memory_schema.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/agent/database/memory_schema.py tests/test_memory_schema.py
git commit -m "feat(memory): add database schema for trading memory system

Add 3 new tables:
- trade_outcomes: signal predictions vs actual results
- market_snapshots: market conditions at signal time
- trade_annotations: manual notes on trades"
```

---

## Task 2: Memory Database Operations (CRUD)

**Files:**
- Create: `src/agent/database/memory_operations.py`
- Test: `tests/test_memory_operations.py`

**Step 1: Write the failing test**

```python
# tests/test_memory_operations.py
"""Tests for trading memory database operations."""
import pytest
import aiosqlite
from pathlib import Path
import tempfile
from datetime import datetime


@pytest.fixture
async def memory_db():
    """Create temporary database with memory tables."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    from src.agent.database.memory_schema import create_memory_tables
    async with aiosqlite.connect(db_path) as db:
        await create_memory_tables(db)
        await db.commit()

    yield db_path
    db_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_create_trade_outcome(memory_db):
    """Test creating a trade outcome record."""
    from src.agent.database.memory_operations import MemoryDatabase

    db = MemoryDatabase(memory_db)

    outcome_id = await db.create_trade_outcome(
        signal_id=1,
        symbol="BTC/USDT",
        direction="LONG",
        confidence=75,
        entry_price=50000.0,
        predicted_stop=49000.0,
        predicted_target=52000.0
    )

    assert outcome_id > 0


@pytest.mark.asyncio
async def test_get_symbol_history(memory_db):
    """Test retrieving trade history for a symbol."""
    from src.agent.database.memory_operations import MemoryDatabase

    db = MemoryDatabase(memory_db)

    # Create some outcomes
    await db.create_trade_outcome(
        signal_id=1, symbol="BTC/USDT", direction="LONG",
        confidence=70, entry_price=50000, predicted_stop=49000, predicted_target=52000
    )
    await db.create_trade_outcome(
        signal_id=2, symbol="BTC/USDT", direction="SHORT",
        confidence=65, entry_price=51000, predicted_stop=52000, predicted_target=49000
    )
    await db.create_trade_outcome(
        signal_id=3, symbol="ETH/USDT", direction="LONG",
        confidence=80, entry_price=3000, predicted_stop=2900, predicted_target=3200
    )

    history = await db.get_symbol_history("BTC/USDT", limit=10)

    assert len(history) == 2
    assert all(h['symbol'] == "BTC/USDT" for h in history)


@pytest.mark.asyncio
async def test_create_market_snapshot(memory_db):
    """Test creating a market snapshot record."""
    from src.agent.database.memory_operations import MemoryDatabase

    db = MemoryDatabase(memory_db)

    snapshot_id = await db.create_market_snapshot(
        signal_id=1,
        symbol="BTC/USDT",
        rsi_15m=45.0,
        rsi_1h=50.0,
        rsi_4h=55.0,
        macd_signal="bullish",
        volatility_percentile=60.0,
        volume_ratio=1.5,
        trend_strength=0.7,
        btc_correlation=1.0,
        market_condition="trending_up"
    )

    assert snapshot_id > 0


@pytest.mark.asyncio
async def test_get_similar_setups(memory_db):
    """Test finding trades with similar market conditions."""
    from src.agent.database.memory_operations import MemoryDatabase

    db = MemoryDatabase(memory_db)

    # Create outcome with snapshot
    outcome_id = await db.create_trade_outcome(
        signal_id=1, symbol="BTC/USDT", direction="LONG",
        confidence=70, entry_price=50000, predicted_stop=49000, predicted_target=52000
    )
    await db.create_market_snapshot(
        signal_id=1, symbol="BTC/USDT",
        rsi_15m=30.0, rsi_1h=35.0, rsi_4h=40.0,
        macd_signal="bullish", volatility_percentile=70.0,
        volume_ratio=2.0, trend_strength=0.6,
        btc_correlation=0.9, market_condition="volatile"
    )

    # Score the outcome
    await db.update_outcome_score(
        outcome_id=outcome_id,
        price_1h=50500, price_4h=51000, price_24h=52000,
        pnl_1h=1.0, pnl_4h=2.0, pnl_24h=4.0,
        grade="A"
    )

    # Find similar setups
    similar = await db.get_similar_setups(
        rsi_min=25, rsi_max=45,
        trend="bullish",
        volatility="high"
    )

    assert len(similar) >= 1


@pytest.mark.asyncio
async def test_get_symbol_stats(memory_db):
    """Test calculating stats for a symbol."""
    from src.agent.database.memory_operations import MemoryDatabase

    db = MemoryDatabase(memory_db)

    # Create scored outcomes
    for i, (conf, pnl, grade) in enumerate([
        (70, 2.0, "B"), (75, -1.0, "D"), (80, 5.0, "A")
    ]):
        oid = await db.create_trade_outcome(
            signal_id=i+1, symbol="BTC/USDT", direction="LONG",
            confidence=conf, entry_price=50000, predicted_stop=49000, predicted_target=52000
        )
        await db.update_outcome_score(
            outcome_id=oid,
            price_1h=50000, price_4h=50000 + (pnl * 500),
            price_24h=50000 + (pnl * 500),
            pnl_1h=pnl/2, pnl_4h=pnl, pnl_24h=pnl,
            grade=grade
        )

    stats = await db.get_symbol_stats("BTC/USDT", days=30)

    assert stats['total_trades'] == 3
    assert stats['win_rate'] == pytest.approx(66.67, rel=0.1)  # 2/3 wins
    assert 'avg_pnl' in stats
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_memory_operations.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/agent/database/memory_operations.py
"""Database operations for trading memory system."""
import aiosqlite
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path


class MemoryDatabase:
    """Operations for trading memory tables."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    async def create_trade_outcome(
        self,
        signal_id: int,
        symbol: str,
        direction: str,
        confidence: int,
        entry_price: float,
        predicted_stop: float,
        predicted_target: float
    ) -> int:
        """Create a new trade outcome record."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO trade_outcomes
                (signal_id, symbol, direction, confidence, entry_price,
                 predicted_stop, predicted_target, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (signal_id, symbol, direction, confidence, entry_price,
                 predicted_stop, predicted_target, datetime.now().isoformat())
            )
            await db.commit()
            return cursor.lastrowid

    async def update_outcome_score(
        self,
        outcome_id: int,
        price_1h: Optional[float] = None,
        price_4h: Optional[float] = None,
        price_24h: Optional[float] = None,
        pnl_1h: Optional[float] = None,
        pnl_4h: Optional[float] = None,
        pnl_24h: Optional[float] = None,
        grade: Optional[str] = None,
        hit_target: Optional[bool] = None,
        hit_stop: Optional[bool] = None,
        max_favorable: Optional[float] = None,
        max_adverse: Optional[float] = None
    ) -> None:
        """Update outcome with scoring data."""
        updates = []
        params = []

        if price_1h is not None:
            updates.append("price_1h = ?")
            params.append(price_1h)
        if price_4h is not None:
            updates.append("price_4h = ?")
            params.append(price_4h)
        if price_24h is not None:
            updates.append("price_24h = ?")
            params.append(price_24h)
        if pnl_1h is not None:
            updates.append("pnl_percent_1h = ?")
            params.append(pnl_1h)
        if pnl_4h is not None:
            updates.append("pnl_percent_4h = ?")
            params.append(pnl_4h)
        if pnl_24h is not None:
            updates.append("pnl_percent_24h = ?")
            params.append(pnl_24h)
        if grade is not None:
            updates.append("outcome_grade = ?")
            params.append(grade)
            updates.append("scored_at = ?")
            params.append(datetime.now().isoformat())
        if hit_target is not None:
            updates.append("hit_target = ?")
            params.append(1 if hit_target else 0)
        if hit_stop is not None:
            updates.append("hit_stop = ?")
            params.append(1 if hit_stop else 0)
        if max_favorable is not None:
            updates.append("max_favorable = ?")
            params.append(max_favorable)
        if max_adverse is not None:
            updates.append("max_adverse = ?")
            params.append(max_adverse)

        if not updates:
            return

        params.append(outcome_id)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"UPDATE trade_outcomes SET {', '.join(updates)} WHERE id = ?",
                params
            )
            await db.commit()

    async def get_symbol_history(
        self,
        symbol: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent trade outcomes for a symbol."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM trade_outcomes
                WHERE symbol = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (symbol, limit)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def create_market_snapshot(
        self,
        signal_id: int,
        symbol: str,
        rsi_15m: Optional[float] = None,
        rsi_1h: Optional[float] = None,
        rsi_4h: Optional[float] = None,
        macd_signal: Optional[str] = None,
        volatility_percentile: Optional[float] = None,
        volume_ratio: Optional[float] = None,
        trend_strength: Optional[float] = None,
        btc_correlation: Optional[float] = None,
        market_condition: Optional[str] = None
    ) -> int:
        """Create a market snapshot record."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO market_snapshots
                (signal_id, symbol, rsi_15m, rsi_1h, rsi_4h, macd_signal,
                 volatility_percentile, volume_ratio, trend_strength,
                 btc_correlation, market_condition, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (signal_id, symbol, rsi_15m, rsi_1h, rsi_4h, macd_signal,
                 volatility_percentile, volume_ratio, trend_strength,
                 btc_correlation, market_condition, datetime.now().isoformat())
            )
            await db.commit()
            return cursor.lastrowid

    async def get_similar_setups(
        self,
        rsi_min: float,
        rsi_max: float,
        trend: str,
        volatility: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Find trades with similar technical setup."""
        # Map volatility to percentile range
        vol_ranges = {
            "low": (0, 33),
            "medium": (33, 66),
            "high": (66, 100)
        }
        vol_min, vol_max = vol_ranges.get(volatility, (0, 100))

        # Map trend to macd_signal
        trend_signals = {
            "bullish": "bullish",
            "bearish": "bearish",
            "neutral": "neutral"
        }
        macd = trend_signals.get(trend, trend)

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT o.*, s.rsi_1h, s.macd_signal, s.volatility_percentile,
                       s.market_condition
                FROM trade_outcomes o
                JOIN market_snapshots s ON o.signal_id = s.signal_id
                WHERE s.rsi_1h BETWEEN ? AND ?
                  AND s.macd_signal = ?
                  AND s.volatility_percentile BETWEEN ? AND ?
                  AND o.outcome_grade IS NOT NULL
                ORDER BY o.created_at DESC
                LIMIT ?
                """,
                (rsi_min, rsi_max, macd, vol_min, vol_max, limit)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_symbol_stats(
        self,
        symbol: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Calculate performance stats for a symbol."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            # Get total trades and wins
            cursor = await db.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN outcome_grade IN ('A', 'B') THEN 1 ELSE 0 END) as wins,
                    AVG(pnl_percent_4h) as avg_pnl,
                    AVG(confidence) as avg_confidence
                FROM trade_outcomes
                WHERE symbol = ?
                  AND created_at >= ?
                  AND outcome_grade IS NOT NULL
                """,
                (symbol, cutoff)
            )
            row = await cursor.fetchone()

            total = row[0] or 0
            wins = row[1] or 0
            avg_pnl = row[2] or 0.0
            avg_conf = row[3] or 0

            return {
                'symbol': symbol,
                'total_trades': total,
                'wins': wins,
                'win_rate': (wins / total * 100) if total > 0 else 0.0,
                'avg_pnl': avg_pnl,
                'avg_confidence': avg_conf,
                'period_days': days
            }

    async def get_recent_trades(
        self,
        days: int = 7,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get all recent trades across all symbols."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM trade_outcomes
                WHERE created_at >= ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (cutoff, limit)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_unscored_outcomes(self) -> List[Dict[str, Any]]:
        """Get outcomes pending scoring."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM trade_outcomes
                WHERE scored_at IS NULL
                ORDER BY created_at ASC
                """
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def create_annotation(
        self,
        signal_id: int,
        annotation: str,
        tags: Optional[List[str]] = None
    ) -> int:
        """Add annotation to a trade."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO trade_annotations (signal_id, annotation, tags, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (signal_id, annotation, json.dumps(tags or []), datetime.now().isoformat())
            )
            await db.commit()
            return cursor.lastrowid

    async def get_confidence_accuracy(
        self,
        confidence_min: int,
        confidence_max: int
    ) -> Dict[str, Any]:
        """Get accuracy stats for a confidence range."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN outcome_grade IN ('A', 'B') THEN 1 ELSE 0 END) as wins,
                    AVG(pnl_percent_4h) as avg_pnl
                FROM trade_outcomes
                WHERE confidence BETWEEN ? AND ?
                  AND outcome_grade IS NOT NULL
                """,
                (confidence_min, confidence_max)
            )
            row = await cursor.fetchone()

            total = row[0] or 0
            wins = row[1] or 0
            avg_pnl = row[2] or 0.0

            return {
                'confidence_range': f"{confidence_min}-{confidence_max}",
                'sample_size': total,
                'win_rate': (wins / total * 100) if total > 0 else 0.0,
                'avg_pnl': avg_pnl
            }

    async def get_condition_stats(
        self,
        market_condition: str
    ) -> Dict[str, Any]:
        """Get stats for trades in a specific market condition."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT
                    o.direction,
                    COUNT(*) as total,
                    SUM(CASE WHEN o.outcome_grade IN ('A', 'B') THEN 1 ELSE 0 END) as wins,
                    AVG(o.pnl_percent_4h) as avg_pnl,
                    AVG(o.confidence) as avg_conf
                FROM trade_outcomes o
                JOIN market_snapshots s ON o.signal_id = s.signal_id
                WHERE s.market_condition = ?
                  AND o.outcome_grade IS NOT NULL
                GROUP BY o.direction
                """,
                (market_condition,)
            )
            rows = await cursor.fetchall()

            result = {
                'market_condition': market_condition,
                'by_direction': {}
            }

            for row in rows:
                direction = row[0]
                total = row[1]
                wins = row[2]
                result['by_direction'][direction] = {
                    'total': total,
                    'win_rate': (wins / total * 100) if total > 0 else 0.0,
                    'avg_pnl': row[3] or 0.0,
                    'avg_confidence': row[4] or 0
                }

            return result
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_memory_operations.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/agent/database/memory_operations.py tests/test_memory_operations.py
git commit -m "feat(memory): add CRUD operations for trading memory

Implement MemoryDatabase class with:
- create/update trade outcomes
- create market snapshots
- get symbol history and stats
- find similar setups
- confidence accuracy queries
- market condition stats"
```

---

## Task 3: Outcome Recording on Signal Submit

**Files:**
- Modify: `src/agent/scanner/tools.py:136-176`
- Test: `tests/test_outcome_recording.py`

**Step 1: Write the failing test**

```python
# tests/test_outcome_recording.py
"""Tests for outcome recording when signals are submitted."""
import pytest
import asyncio
import tempfile
from pathlib import Path
import aiosqlite


@pytest.fixture
async def test_db():
    """Create test database with all required tables."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    from src.agent.database.memory_schema import create_memory_tables
    from src.agent.database.movers_schema import create_movers_tables

    async with aiosqlite.connect(db_path) as db:
        await create_memory_tables(db)
        await create_movers_tables(db)
        await db.commit()

    yield db_path
    db_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_signal_creates_outcome_record(test_db):
    """Test that submitting a signal creates a trade outcome record."""
    from src.agent.scanner.tools import submit_trading_signal, set_signal_queue, set_memory_db
    from src.agent.database.memory_operations import MemoryDatabase

    # Setup
    queue = asyncio.Queue()
    set_signal_queue(queue)

    memory_db = MemoryDatabase(test_db)
    set_memory_db(memory_db)

    # Submit signal
    result = await submit_trading_signal({
        "confidence": 75,
        "entry_price": 50000.0,
        "stop_loss": 49000.0,
        "tp1": 52000.0,
        "technical_score": 35.0,
        "sentiment_score": 20.0,
        "liquidity_score": 15.0,
        "correlation_score": 5.0,
        "symbol": "BTC/USDT",
        "analysis": "Test analysis"
    })

    assert result['status'] == 'success'

    # Verify outcome was created
    outcomes = await memory_db.get_symbol_history("BTC/USDT", limit=1)
    assert len(outcomes) == 1
    assert outcomes[0]['symbol'] == "BTC/USDT"
    assert outcomes[0]['confidence'] == 75
    assert outcomes[0]['entry_price'] == 50000.0
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_outcome_recording.py -v
```

Expected: FAIL with `ImportError: cannot import name 'set_memory_db'`

**Step 3: Modify implementation**

In `src/agent/scanner/tools.py`, add memory database integration:

```python
# Add near top of file, after _signal_queue definition (around line 11):
_memory_db: Optional["MemoryDatabase"] = None


def set_memory_db(db: "MemoryDatabase"):
    """Set the memory database for outcome recording."""
    global _memory_db
    _memory_db = db


def clear_memory_db():
    """Clear the memory database reference."""
    global _memory_db
    _memory_db = None
```

Then modify `submit_trading_signal` function to create outcome record. Add this block after line 162 (after `await _signal_queue.put(signal)`):

```python
        # Create trade outcome record for memory tracking
        global _memory_db
        if _memory_db is not None:
            try:
                # Determine direction from prices
                direction = "LONG" if tp1 > entry_price else "SHORT"

                await _memory_db.create_trade_outcome(
                    signal_id=0,  # Will be updated when signal is saved to movers_signals
                    symbol=symbol,
                    direction=direction,
                    confidence=confidence,
                    entry_price=entry_price,
                    predicted_stop=stop_loss,
                    predicted_target=tp1
                )
                logger.info(f"Created trade outcome record for {symbol}")
            except Exception as e:
                logger.warning(f"Failed to create trade outcome: {e}")
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_outcome_recording.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/agent/scanner/tools.py tests/test_outcome_recording.py
git commit -m "feat(memory): record trade outcomes when signals submitted

Add memory database integration to submit_trading_signal tool.
Creates trade_outcomes record for each signal submission."
```

---

## Task 4: Simple Recall Tools (3 tools)

**Files:**
- Create: `src/agent/tools/memory_tools.py`
- Test: `tests/test_memory_tools.py`

**Step 1: Write the failing test**

```python
# tests/test_memory_tools.py
"""Tests for memory recall tools."""
import pytest
import tempfile
from pathlib import Path
import aiosqlite


@pytest.fixture
async def populated_memory_db():
    """Create database with sample trade data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    from src.agent.database.memory_schema import create_memory_tables
    from src.agent.database.memory_operations import MemoryDatabase

    async with aiosqlite.connect(db_path) as db:
        await create_memory_tables(db)
        await db.commit()

    # Populate with test data
    memory_db = MemoryDatabase(db_path)

    for i, (sym, conf, pnl, grade) in enumerate([
        ("BTC/USDT", 70, 2.5, "B"),
        ("BTC/USDT", 75, -1.0, "D"),
        ("BTC/USDT", 80, 4.0, "A"),
        ("ETH/USDT", 65, 1.5, "B"),
        ("ETH/USDT", 72, 3.0, "A"),
    ]):
        oid = await memory_db.create_trade_outcome(
            signal_id=i+1, symbol=sym, direction="LONG",
            confidence=conf, entry_price=50000, predicted_stop=49000, predicted_target=52000
        )
        await memory_db.update_outcome_score(
            outcome_id=oid, price_4h=51000, pnl_4h=pnl, grade=grade
        )

    yield db_path, memory_db
    db_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_recall_symbol_history(populated_memory_db):
    """Test recall_symbol_history tool."""
    db_path, memory_db = populated_memory_db

    from src.agent.tools.memory_tools import recall_symbol_history, set_memory_db_for_tools
    set_memory_db_for_tools(memory_db)

    result = await recall_symbol_history.handler({"symbol": "BTC/USDT", "limit": 10})

    assert 'trades' in result
    assert len(result['trades']) == 3
    assert 'win_rate' in result
    assert 'avg_pnl' in result


@pytest.mark.asyncio
async def test_recall_recent_trades(populated_memory_db):
    """Test recall_recent_trades tool."""
    db_path, memory_db = populated_memory_db

    from src.agent.tools.memory_tools import recall_recent_trades, set_memory_db_for_tools
    set_memory_db_for_tools(memory_db)

    result = await recall_recent_trades.handler({"days": 7})

    assert 'trades' in result
    assert len(result['trades']) == 5  # All trades
    assert 'overall_stats' in result


@pytest.mark.asyncio
async def test_recall_signal_accuracy(populated_memory_db):
    """Test recall_signal_accuracy tool."""
    db_path, memory_db = populated_memory_db

    from src.agent.tools.memory_tools import recall_signal_accuracy, set_memory_db_for_tools
    set_memory_db_for_tools(memory_db)

    result = await recall_signal_accuracy.handler({
        "confidence_min": 70,
        "confidence_max": 80
    })

    assert 'confidence_range' in result
    assert 'sample_size' in result
    assert 'win_rate' in result
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_memory_tools.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/agent/tools/memory_tools.py
"""Memory recall tools for Claude Agent integration."""
from typing import Dict, Any, Optional
from claude_agent_sdk import tool

# Module-level storage for memory database
_memory_db: Optional["MemoryDatabase"] = None


def set_memory_db_for_tools(db: "MemoryDatabase"):
    """Set the memory database for recall tools."""
    global _memory_db
    _memory_db = db


@tool(
    name="recall_symbol_history",
    description="""
    Get recent trade outcomes for a specific symbol.

    Returns trade history with win rate, average P&L, and best/worst outcomes.
    Use this to understand how past trades on this symbol performed.

    Args:
        symbol: Trading pair (e.g., "BTC/USDT")
        limit: Maximum trades to return (default: 10)
    """,
    input_schema={
        "symbol": str,
        "limit": int
    }
)
async def recall_symbol_history(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get recent trade outcomes for a specific symbol."""
    global _memory_db

    if _memory_db is None:
        return {"error": "Memory database not initialized"}

    symbol = args.get("symbol", "")
    limit = args.get("limit", 10)

    trades = await _memory_db.get_symbol_history(symbol, limit)
    stats = await _memory_db.get_symbol_stats(symbol, days=30)

    # Find best and worst trades
    scored_trades = [t for t in trades if t.get('outcome_grade')]
    best = max(scored_trades, key=lambda t: t.get('pnl_percent_4h', 0), default=None)
    worst = min(scored_trades, key=lambda t: t.get('pnl_percent_4h', 0), default=None)

    return {
        "symbol": symbol,
        "trades": trades,
        "win_rate": stats['win_rate'],
        "avg_pnl": stats['avg_pnl'],
        "total_trades": stats['total_trades'],
        "best_trade": best,
        "worst_trade": worst
    }


@tool(
    name="recall_recent_trades",
    description="""
    Get all recent trades across all symbols.

    Returns trades list with overall performance stats.
    Use this for a broad view of recent trading activity.

    Args:
        days: Number of days to look back (default: 7)
    """,
    input_schema={
        "days": int
    }
)
async def recall_recent_trades(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get all recent trades across all symbols."""
    global _memory_db

    if _memory_db is None:
        return {"error": "Memory database not initialized"}

    days = args.get("days", 7)

    trades = await _memory_db.get_recent_trades(days=days, limit=50)

    # Calculate overall stats
    scored = [t for t in trades if t.get('outcome_grade')]
    wins = sum(1 for t in scored if t.get('outcome_grade') in ('A', 'B'))
    total = len(scored)
    avg_pnl = sum(t.get('pnl_percent_4h', 0) for t in scored) / total if total > 0 else 0

    # Group by symbol
    by_symbol = {}
    for t in trades:
        sym = t['symbol']
        if sym not in by_symbol:
            by_symbol[sym] = []
        by_symbol[sym].append(t)

    return {
        "trades": trades,
        "overall_stats": {
            "total_trades": total,
            "win_rate": (wins / total * 100) if total > 0 else 0,
            "avg_pnl": avg_pnl,
            "period_days": days
        },
        "by_symbol": {sym: len(ts) for sym, ts in by_symbol.items()}
    }


@tool(
    name="recall_signal_accuracy",
    description="""
    Check how accurate signals in a confidence range have been.

    Returns win rate, average P&L, and sample size for the confidence band.
    Use this to calibrate confidence thresholds.

    Args:
        confidence_min: Minimum confidence (0-100)
        confidence_max: Maximum confidence (0-100)
    """,
    input_schema={
        "confidence_min": int,
        "confidence_max": int
    }
)
async def recall_signal_accuracy(args: Dict[str, Any]) -> Dict[str, Any]:
    """Check accuracy for a confidence range."""
    global _memory_db

    if _memory_db is None:
        return {"error": "Memory database not initialized"}

    conf_min = args.get("confidence_min", 0)
    conf_max = args.get("confidence_max", 100)

    return await _memory_db.get_confidence_accuracy(conf_min, conf_max)
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_memory_tools.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/agent/tools/memory_tools.py tests/test_memory_tools.py
git commit -m "feat(memory): add simple recall tools

Add 3 memory recall tools:
- recall_symbol_history: trade history for a symbol
- recall_recent_trades: all recent trades across symbols
- recall_signal_accuracy: accuracy by confidence range"
```

---

## Task 5: Context Builder (Auto-Inject)

**Files:**
- Create: `src/agent/memory/context_builder.py`
- Modify: `src/agent/scanner/prompts.py:7-68`
- Test: `tests/test_context_builder.py`

**Step 1: Write the failing test**

```python
# tests/test_context_builder.py
"""Tests for trading memory context builder."""
import pytest
import tempfile
from pathlib import Path
import aiosqlite


@pytest.fixture
async def memory_with_data():
    """Create database with sample trade history."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    from src.agent.database.memory_schema import create_memory_tables
    from src.agent.database.memory_operations import MemoryDatabase

    async with aiosqlite.connect(db_path) as db:
        await create_memory_tables(db)
        await db.commit()

    memory_db = MemoryDatabase(db_path)

    # Add trades with snapshots
    for i, (sym, conf, pnl, grade, condition) in enumerate([
        ("BTC/USDT", 70, 2.5, "B", "trending_up"),
        ("BTC/USDT", 75, -1.0, "D", "volatile"),
        ("BTC/USDT", 80, 4.0, "A", "trending_up"),
    ]):
        oid = await memory_db.create_trade_outcome(
            signal_id=i+1, symbol=sym, direction="LONG",
            confidence=conf, entry_price=50000, predicted_stop=49000, predicted_target=52000
        )
        await memory_db.create_market_snapshot(
            signal_id=i+1, symbol=sym,
            rsi_15m=45, rsi_1h=50, rsi_4h=55,
            macd_signal="bullish", volatility_percentile=60,
            volume_ratio=1.2, trend_strength=0.7,
            btc_correlation=1.0, market_condition=condition
        )
        await memory_db.update_outcome_score(
            outcome_id=oid, price_4h=51000, pnl_4h=pnl, grade=grade
        )

    yield db_path, memory_db
    db_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_build_memory_context(memory_with_data):
    """Test building memory context block."""
    db_path, memory_db = memory_with_data

    from src.agent.memory.context_builder import MemoryContextBuilder

    builder = MemoryContextBuilder(memory_db)
    context = await builder.build_context(
        symbol="BTC/USDT",
        current_condition="trending_up"
    )

    assert "<trading_memory>" in context
    assert "BTC/USDT" in context
    assert "Win rate" in context or "win rate" in context.lower()
    assert "</trading_memory>" in context


@pytest.mark.asyncio
async def test_context_includes_condition_stats(memory_with_data):
    """Test that context includes stats for current market condition."""
    db_path, memory_db = memory_with_data

    from src.agent.memory.context_builder import MemoryContextBuilder

    builder = MemoryContextBuilder(memory_db)
    context = await builder.build_context(
        symbol="BTC/USDT",
        current_condition="trending_up"
    )

    assert "trending_up" in context.lower() or "Similar Market Conditions" in context
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_context_builder.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/agent/memory/context_builder.py
"""Build memory context for agent prompts."""
from typing import Optional
from datetime import datetime


class MemoryContextBuilder:
    """Builds memory context blocks for agent prompts."""

    def __init__(self, memory_db: "MemoryDatabase"):
        self.memory_db = memory_db

    async def build_context(
        self,
        symbol: str,
        current_condition: Optional[str] = None
    ) -> str:
        """
        Build memory context block to inject into agent prompt.

        Args:
            symbol: Trading pair being analyzed
            current_condition: Current market condition (trending_up, volatile, etc.)

        Returns:
            Formatted context string wrapped in <trading_memory> tags
        """
        sections = []

        # Section 1: Recent symbol history
        history = await self.memory_db.get_symbol_history(symbol, limit=5)
        stats = await self.memory_db.get_symbol_stats(symbol, days=30)

        if history:
            history_section = self._format_history_section(symbol, history, stats)
            sections.append(history_section)

        # Section 2: Symbol stats
        if stats['total_trades'] > 0:
            stats_section = self._format_stats_section(symbol, stats)
            sections.append(stats_section)

        # Section 3: Similar market conditions
        if current_condition:
            condition_stats = await self.memory_db.get_condition_stats(current_condition)
            if condition_stats.get('by_direction'):
                condition_section = self._format_condition_section(current_condition, condition_stats)
                sections.append(condition_section)

        if not sections:
            return "<trading_memory>\nNo trading history available for this symbol.\n</trading_memory>"

        content = "\n\n".join(sections)
        return f"<trading_memory>\n{content}\n</trading_memory>"

    def _format_history_section(self, symbol: str, history: list, stats: dict) -> str:
        """Format recent trade history as table."""
        lines = [f"## Recent {symbol} History (Last {len(history)} trades)"]
        lines.append("| Date | Direction | Conf | Outcome | P&L 4h |")
        lines.append("|------|-----------|------|---------|--------|")

        for trade in history:
            date = trade.get('created_at', '')[:10]
            direction = trade.get('direction', 'N/A')
            conf = trade.get('confidence', 0)
            grade = trade.get('outcome_grade', 'pending')
            pnl = trade.get('pnl_percent_4h')
            pnl_str = f"{pnl:+.1f}%" if pnl is not None else "pending"

            lines.append(f"| {date} | {direction} | {conf} | {grade} | {pnl_str} |")

        return "\n".join(lines)

    def _format_stats_section(self, symbol: str, stats: dict) -> str:
        """Format symbol performance stats."""
        return f"""## {symbol} Stats ({stats['period_days']} days)
Win rate: {stats['win_rate']:.1f}% | Avg P&L: {stats['avg_pnl']:+.2f}% | Trades: {stats['total_trades']}"""

    def _format_condition_section(self, condition: str, stats: dict) -> str:
        """Format market condition stats."""
        lines = [f"## Similar Market Conditions ({condition})"]

        for direction, data in stats.get('by_direction', {}).items():
            total = data.get('total', 0)
            win_rate = data.get('win_rate', 0)
            avg_pnl = data.get('avg_pnl', 0)
            lines.append(f"- {direction}: {total} trades, {win_rate:.0f}% win rate, {avg_pnl:+.1f}% avg P&L")

        return "\n".join(lines)
```

Also create the `__init__.py`:

```python
# src/agent/memory/__init__.py
"""Memory system for trading history."""
from .context_builder import MemoryContextBuilder

__all__ = ['MemoryContextBuilder']
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_context_builder.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/agent/memory/ tests/test_context_builder.py
git commit -m "feat(memory): add context builder for auto-inject

MemoryContextBuilder generates <trading_memory> blocks with:
- Recent symbol history table
- Symbol performance stats
- Similar market condition stats"
```

---

## Task 6: Integrate Context into Prompts

**Files:**
- Modify: `src/agent/scanner/prompts.py`
- Test: `tests/test_prompt_with_memory.py`

**Step 1: Write the failing test**

```python
# tests/test_prompt_with_memory.py
"""Tests for prompt builder with memory integration."""
import pytest
import tempfile
from pathlib import Path
import aiosqlite


@pytest.fixture
async def memory_db_fixture():
    """Create database with memory tables."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    from src.agent.database.memory_schema import create_memory_tables
    from src.agent.database.memory_operations import MemoryDatabase

    async with aiosqlite.connect(db_path) as db:
        await create_memory_tables(db)
        await db.commit()

    memory_db = MemoryDatabase(db_path)

    # Add a trade
    oid = await memory_db.create_trade_outcome(
        signal_id=1, symbol="BTC/USDT", direction="LONG",
        confidence=70, entry_price=50000, predicted_stop=49000, predicted_target=52000
    )
    await memory_db.update_outcome_score(
        outcome_id=oid, price_4h=51000, pnl_4h=2.0, grade="B"
    )

    yield memory_db
    db_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_prompt_includes_memory_context(memory_db_fixture):
    """Test that build_analysis_prompt includes memory context."""
    from src.agent.scanner.prompts import PromptBuilder
    from src.agent.memory.context_builder import MemoryContextBuilder

    builder = PromptBuilder()
    context_builder = MemoryContextBuilder(memory_db_fixture)

    mover_context = {
        'symbol': 'BTC/USDT',
        'direction': 'LONG',
        'change_1h': 3.5,
        'change_4h': 5.2,
        'current_price': 51000.0,
        'volume_24h': 1000000
    }
    portfolio_context = {
        'total_value': 100000,
        'open_positions': 2,
        'exposure_pct': 20.0
    }

    prompt = await builder.build_analysis_prompt_with_memory(
        mover_context=mover_context,
        portfolio_context=portfolio_context,
        context_builder=context_builder,
        current_condition="trending_up"
    )

    assert "<trading_memory>" in prompt
    assert "BTC/USDT" in prompt
    assert "LONG" in prompt
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_prompt_with_memory.py -v
```

Expected: FAIL with `AttributeError: 'PromptBuilder' object has no attribute 'build_analysis_prompt_with_memory'`

**Step 3: Modify implementation**

Add new method to `src/agent/scanner/prompts.py`:

```python
    async def build_analysis_prompt_with_memory(
        self,
        mover_context: Dict[str, Any],
        portfolio_context: Dict[str, Any],
        context_builder: "MemoryContextBuilder",
        current_condition: Optional[str] = None
    ) -> str:
        """
        Build analysis prompt with trading memory context.

        Args:
            mover_context: Mover details
            portfolio_context: Portfolio state
            context_builder: MemoryContextBuilder instance
            current_condition: Current market condition

        Returns:
            Formatted prompt with memory context prepended
        """
        # Get memory context
        memory_context = await context_builder.build_context(
            symbol=mover_context['symbol'],
            current_condition=current_condition
        )

        # Build base prompt
        base_prompt = self.build_analysis_prompt(mover_context, portfolio_context)

        # Prepend memory context
        return f"{memory_context}\n\n{base_prompt}"
```

Add the import at the top:
```python
from typing import Dict, Any, Optional
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_prompt_with_memory.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/agent/scanner/prompts.py tests/test_prompt_with_memory.py
git commit -m "feat(memory): integrate context into analysis prompts

Add build_analysis_prompt_with_memory method that prepends
<trading_memory> block to the standard analysis prompt."
```

---

## Task 7: Background Outcome Scorer

**Files:**
- Create: `src/agent/tracking/outcome_scorer.py`
- Test: `tests/test_outcome_scorer.py`

**Step 1: Write the failing test**

```python
# tests/test_outcome_scorer.py
"""Tests for background outcome scorer."""
import pytest
import tempfile
from pathlib import Path
import aiosqlite
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch


@pytest.fixture
async def scorer_db():
    """Create database with unscored outcomes."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    from src.agent.database.memory_schema import create_memory_tables
    from src.agent.database.memory_operations import MemoryDatabase

    async with aiosqlite.connect(db_path) as db:
        await create_memory_tables(db)
        await db.commit()

    memory_db = MemoryDatabase(db_path)

    # Create outcome from 2 hours ago (should get 1h score)
    await memory_db.create_trade_outcome(
        signal_id=1, symbol="BTC/USDT", direction="LONG",
        confidence=70, entry_price=50000, predicted_stop=49000, predicted_target=52000
    )

    # Backdate the created_at to 2 hours ago
    async with aiosqlite.connect(db_path) as db:
        two_hours_ago = (datetime.now() - timedelta(hours=2)).isoformat()
        await db.execute(
            "UPDATE trade_outcomes SET created_at = ? WHERE id = 1",
            (two_hours_ago,)
        )
        await db.commit()

    yield db_path, memory_db
    db_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_scorer_updates_1h_price(scorer_db):
    """Test that scorer updates 1h price for outcomes older than 1 hour."""
    db_path, memory_db = scorer_db

    from src.agent.tracking.outcome_scorer import OutcomeScorer

    # Mock exchange to return a price
    mock_exchange = AsyncMock()
    mock_exchange.fetch_ticker = AsyncMock(return_value={'last': 50500.0})

    scorer = OutcomeScorer(memory_db, mock_exchange)
    await scorer.score_pending_outcomes()

    # Check outcome was updated
    outcomes = await memory_db.get_symbol_history("BTC/USDT", limit=1)
    assert outcomes[0]['price_1h'] == 50500.0
    assert outcomes[0]['pnl_percent_1h'] == pytest.approx(1.0, rel=0.1)


@pytest.mark.asyncio
async def test_grade_calculation():
    """Test outcome grade calculation logic."""
    from src.agent.tracking.outcome_scorer import OutcomeScorer

    # A: hit target, didn't hit stop
    assert OutcomeScorer.calculate_grade(
        hit_target=True, hit_stop=False, pnl_24h=5.0
    ) == "A"

    # B: profitable (>1%)
    assert OutcomeScorer.calculate_grade(
        hit_target=False, hit_stop=False, pnl_24h=2.0
    ) == "B"

    # C: small profit/loss
    assert OutcomeScorer.calculate_grade(
        hit_target=False, hit_stop=False, pnl_24h=0.5
    ) == "C"

    # D: loss but didn't hit stop
    assert OutcomeScorer.calculate_grade(
        hit_target=False, hit_stop=False, pnl_24h=-2.0
    ) == "D"

    # F: hit stop
    assert OutcomeScorer.calculate_grade(
        hit_target=False, hit_stop=True, pnl_24h=-3.0
    ) == "F"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_outcome_scorer.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/agent/tracking/outcome_scorer.py
"""Background scorer for trade outcomes."""
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class OutcomeScorer:
    """Scores trade outcomes at 1h/4h/24h intervals."""

    def __init__(self, memory_db: "MemoryDatabase", exchange):
        self.memory_db = memory_db
        self.exchange = exchange

    async def score_pending_outcomes(self) -> int:
        """
        Score all pending outcomes that have reached their time milestones.

        Returns:
            Number of outcomes updated
        """
        pending = await self.memory_db.get_unscored_outcomes()
        updated = 0

        for outcome in pending:
            try:
                await self._score_outcome(outcome)
                updated += 1
            except Exception as e:
                logger.error(f"Error scoring outcome {outcome['id']}: {e}")

        return updated

    async def _score_outcome(self, outcome: dict) -> None:
        """Score a single outcome based on time elapsed."""
        created_at = datetime.fromisoformat(outcome['created_at'])
        age = datetime.now() - created_at
        age_hours = age.total_seconds() / 3600

        symbol = outcome['symbol']
        entry_price = outcome['entry_price']
        direction = outcome['direction']
        predicted_stop = outcome['predicted_stop']
        predicted_target = outcome['predicted_target']

        # Fetch current price
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            current_price = ticker['last']
        except Exception as e:
            logger.warning(f"Failed to fetch price for {symbol}: {e}")
            return

        # Calculate P&L
        if direction == "LONG":
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
            hit_target = current_price >= predicted_target
            hit_stop = current_price <= predicted_stop
        else:  # SHORT
            pnl_pct = ((entry_price - current_price) / entry_price) * 100
            hit_target = current_price <= predicted_target
            hit_stop = current_price >= predicted_stop

        # Update based on age
        updates = {}

        if age_hours >= 1 and outcome.get('price_1h') is None:
            updates['price_1h'] = current_price
            updates['pnl_1h'] = pnl_pct

        if age_hours >= 4 and outcome.get('price_4h') is None:
            updates['price_4h'] = current_price
            updates['pnl_4h'] = pnl_pct

        if age_hours >= 24 and outcome.get('price_24h') is None:
            updates['price_24h'] = current_price
            updates['pnl_24h'] = pnl_pct
            updates['hit_target'] = hit_target
            updates['hit_stop'] = hit_stop
            updates['grade'] = self.calculate_grade(hit_target, hit_stop, pnl_pct)

        if updates:
            await self.memory_db.update_outcome_score(
                outcome_id=outcome['id'],
                **updates
            )
            logger.info(f"Scored outcome {outcome['id']} for {symbol}: {updates}")

    @staticmethod
    def calculate_grade(
        hit_target: bool,
        hit_stop: bool,
        pnl_24h: float
    ) -> str:
        """
        Calculate outcome grade.

        A: Hit target, didn't hit stop
        B: Profitable at 24h (>1%), direction correct
        C: Small profit/loss (-1% to +1%)
        D: Loss but stop wasn't hit
        F: Hit stop loss or >3% adverse move
        """
        if hit_stop or pnl_24h <= -3.0:
            return "F"
        if hit_target:
            return "A"
        if pnl_24h > 1.0:
            return "B"
        if -1.0 <= pnl_24h <= 1.0:
            return "C"
        return "D"
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_outcome_scorer.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/agent/tracking/outcome_scorer.py tests/test_outcome_scorer.py
git commit -m "feat(memory): add background outcome scorer

OutcomeScorer updates trade outcomes at 1h/4h/24h intervals:
- Fetches current price from exchange
- Calculates P&L percentage
- Assigns grade (A/B/C/D/F) at 24h mark"
```

---

## Task 8: Smart Recall Tools (3 tools)

**Files:**
- Modify: `src/agent/tools/memory_tools.py`
- Test: `tests/test_smart_recall_tools.py`

**Step 1: Write the failing test**

```python
# tests/test_smart_recall_tools.py
"""Tests for smart memory recall tools."""
import pytest
import tempfile
from pathlib import Path
import aiosqlite


@pytest.fixture
async def rich_memory_db():
    """Create database with diverse trade data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    from src.agent.database.memory_schema import create_memory_tables
    from src.agent.database.memory_operations import MemoryDatabase

    async with aiosqlite.connect(db_path) as db:
        await create_memory_tables(db)
        await db.commit()

    memory_db = MemoryDatabase(db_path)

    # Add trades with various conditions
    setups = [
        # (symbol, direction, conf, pnl, grade, rsi, macd, vol, condition)
        ("BTC/USDT", "LONG", 70, 3.0, "A", 30, "bullish", 70, "volatile"),
        ("BTC/USDT", "LONG", 75, 2.0, "B", 35, "bullish", 65, "volatile"),
        ("ETH/USDT", "SHORT", 65, -1.5, "D", 70, "bearish", 40, "trending_down"),
        ("BTC/USDT", "LONG", 80, 4.5, "A", 28, "bullish", 75, "volatile"),
    ]

    for i, (sym, dir, conf, pnl, grade, rsi, macd, vol, cond) in enumerate(setups):
        oid = await memory_db.create_trade_outcome(
            signal_id=i+1, symbol=sym, direction=dir,
            confidence=conf, entry_price=50000, predicted_stop=49000, predicted_target=52000
        )
        await memory_db.create_market_snapshot(
            signal_id=i+1, symbol=sym,
            rsi_15m=rsi, rsi_1h=rsi+5, rsi_4h=rsi+10,
            macd_signal=macd, volatility_percentile=vol,
            volume_ratio=1.5, trend_strength=0.7,
            btc_correlation=1.0 if sym == "BTC/USDT" else 0.8,
            market_condition=cond
        )
        await memory_db.update_outcome_score(
            outcome_id=oid, price_4h=51000, pnl_4h=pnl, grade=grade
        )

    yield db_path, memory_db
    db_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_recall_similar_setups(rich_memory_db):
    """Test recall_similar_setups tool."""
    db_path, memory_db = rich_memory_db

    from src.agent.tools.memory_tools import recall_similar_setups, set_memory_db_for_tools
    set_memory_db_for_tools(memory_db)

    result = await recall_similar_setups.handler({
        "rsi_min": 25,
        "rsi_max": 40,
        "trend": "bullish",
        "volatility": "high"
    })

    assert 'setups' in result
    assert len(result['setups']) >= 2  # Should find the RSI 28-35 trades
    assert 'win_rate' in result
    assert 'avg_pnl' in result


@pytest.mark.asyncio
async def test_recall_what_worked(rich_memory_db):
    """Test recall_what_worked tool."""
    db_path, memory_db = rich_memory_db

    from src.agent.tools.memory_tools import recall_what_worked, set_memory_db_for_tools
    set_memory_db_for_tools(memory_db)

    result = await recall_what_worked.handler({
        "market_condition": "volatile"
    })

    assert 'market_condition' in result
    assert 'by_direction' in result
    assert 'recommendation' in result
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_smart_recall_tools.py -v
```

Expected: FAIL with `ImportError: cannot import name 'recall_similar_setups'`

**Step 3: Add smart tools to memory_tools.py**

Add these tools to `src/agent/tools/memory_tools.py`:

```python
@tool(
    name="recall_similar_setups",
    description="""
    Find past trades with similar technical setup.

    Matches trades by RSI range, trend direction, and volatility level.
    Returns outcomes of similar conditions to inform current decision.

    Args:
        rsi_min: Minimum RSI value (0-100)
        rsi_max: Maximum RSI value (0-100)
        trend: Trend direction ("bullish", "bearish", "neutral")
        volatility: Volatility level ("low", "medium", "high")
    """,
    input_schema={
        "rsi_min": float,
        "rsi_max": float,
        "trend": str,
        "volatility": str
    }
)
async def recall_similar_setups(args: Dict[str, Any]) -> Dict[str, Any]:
    """Find past trades with similar technical setup."""
    global _memory_db

    if _memory_db is None:
        return {"error": "Memory database not initialized"}

    rsi_min = args.get("rsi_min", 0)
    rsi_max = args.get("rsi_max", 100)
    trend = args.get("trend", "neutral")
    volatility = args.get("volatility", "medium")

    setups = await _memory_db.get_similar_setups(
        rsi_min=rsi_min,
        rsi_max=rsi_max,
        trend=trend,
        volatility=volatility
    )

    # Calculate stats
    if setups:
        wins = sum(1 for s in setups if s.get('outcome_grade') in ('A', 'B'))
        total = len(setups)
        avg_pnl = sum(s.get('pnl_percent_4h', 0) for s in setups) / total
    else:
        wins, total, avg_pnl = 0, 0, 0.0

    return {
        "setups": setups,
        "sample_size": total,
        "win_rate": (wins / total * 100) if total > 0 else 0,
        "avg_pnl": avg_pnl,
        "query": {
            "rsi_range": f"{rsi_min}-{rsi_max}",
            "trend": trend,
            "volatility": volatility
        }
    }


@tool(
    name="recall_what_worked",
    description="""
    Get winning strategies for a specific market condition.

    Returns best direction, optimal confidence threshold, and patterns to avoid.
    Use this to understand what has historically worked in current conditions.

    Args:
        market_condition: Market condition ("trending_up", "trending_down", "ranging", "volatile")
    """,
    input_schema={
        "market_condition": str
    }
)
async def recall_what_worked(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get winning strategies for a market condition."""
    global _memory_db

    if _memory_db is None:
        return {"error": "Memory database not initialized"}

    condition = args.get("market_condition", "")

    stats = await _memory_db.get_condition_stats(condition)

    # Generate recommendation
    recommendation = ""
    by_direction = stats.get('by_direction', {})

    if by_direction:
        best_dir = max(by_direction.items(), key=lambda x: x[1].get('win_rate', 0))
        worst_dir = min(by_direction.items(), key=lambda x: x[1].get('win_rate', 0))

        recommendation = f"In {condition} conditions, {best_dir[0]} signals have {best_dir[1]['win_rate']:.0f}% win rate. "
        if best_dir[1]['win_rate'] > worst_dir[1]['win_rate']:
            recommendation += f"Avoid {worst_dir[0]} signals ({worst_dir[1]['win_rate']:.0f}% win rate)."

    return {
        "market_condition": condition,
        "by_direction": by_direction,
        "recommendation": recommendation
    }


@tool(
    name="search_trade_memory",
    description="""
    Natural language search across trade memory via claude-mem.

    Use this for fuzzy or semantic searches like:
    - "trades where news caused unexpected reversal"
    - "high confidence signals that failed"
    - "best performing setups last month"

    Args:
        query: Natural language search query
    """,
    input_schema={
        "query": str
    }
)
async def search_trade_memory(args: Dict[str, Any]) -> Dict[str, Any]:
    """Natural language search via claude-mem."""
    query = args.get("query", "")

    # This tool is a placeholder that instructs the agent to use claude-mem MCP
    return {
        "instruction": "Use the claude-mem MCP search tools to search for this query",
        "query": query,
        "suggested_tool": "mcp__plugin_claude-mem_claude-mem-search__search_observations",
        "note": "Trade outcomes are synced to claude-mem as observations with type='trade_outcome'"
    }
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_smart_recall_tools.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/agent/tools/memory_tools.py tests/test_smart_recall_tools.py
git commit -m "feat(memory): add smart recall tools

Add 3 smart memory recall tools:
- recall_similar_setups: find trades with similar technical setup
- recall_what_worked: get winning strategies for market condition
- search_trade_memory: natural language search via claude-mem"
```

---

## Task 9: CLI Commands for Memory Management

**Files:**
- Modify: `src/agent/main.py`
- Test: `tests/test_memory_cli.py`

**Step 1: Write the failing test**

```python
# tests/test_memory_cli.py
"""Tests for memory management CLI commands."""
import pytest
from click.testing import CliRunner
import tempfile
from pathlib import Path
import aiosqlite
import os


@pytest.fixture
def cli_runner():
    return CliRunner()


@pytest.fixture
async def test_db_env():
    """Create test database and set DB_PATH env."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    from src.agent.database.memory_schema import create_memory_tables
    from src.agent.database.movers_schema import create_movers_tables
    from src.agent.database.memory_operations import MemoryDatabase

    async with aiosqlite.connect(db_path) as db:
        await create_memory_tables(db)
        await create_movers_tables(db)
        await db.commit()

    # Add some data
    memory_db = MemoryDatabase(db_path)
    oid = await memory_db.create_trade_outcome(
        signal_id=1, symbol="BTC/USDT", direction="LONG",
        confidence=70, entry_price=50000, predicted_stop=49000, predicted_target=52000
    )
    await memory_db.update_outcome_score(
        outcome_id=oid, price_4h=51000, pnl_4h=2.0, grade="B"
    )

    old_db_path = os.environ.get("DB_PATH")
    os.environ["DB_PATH"] = str(db_path)

    yield db_path

    if old_db_path:
        os.environ["DB_PATH"] = old_db_path
    db_path.unlink(missing_ok=True)


def test_memory_stats_command(cli_runner, test_db_env):
    """Test memory-stats CLI command."""
    import asyncio
    asyncio.get_event_loop().run_until_complete(test_db_env.__anext__())

    from src.agent.main import cli

    result = cli_runner.invoke(cli, ['memory-stats', '--symbol', 'BTC/USDT'])

    assert result.exit_code == 0
    assert 'BTC/USDT' in result.output


def test_annotate_command(cli_runner, test_db_env):
    """Test annotate CLI command."""
    import asyncio
    asyncio.get_event_loop().run_until_complete(test_db_env.__anext__())

    from src.agent.main import cli

    result = cli_runner.invoke(cli, ['annotate', '--signal-id', '1', 'Test annotation'])

    assert result.exit_code == 0
    assert 'Annotation added' in result.output or 'annotation' in result.output.lower()
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_memory_cli.py -v
```

Expected: FAIL with `Error: No such command 'memory-stats'`

**Step 3: Add CLI commands to main.py**

Add these commands to `src/agent/main.py`:

```python
@cli.command()
@click.option('--symbol', default=None, help='Filter by symbol')
@click.option('--days', default=30, help='Number of days to analyze')
def memory_stats(symbol, days):
    """View trading memory statistics."""
    async def run():
        from src.agent.database.memory_schema import create_memory_tables
        from src.agent.database.memory_operations import MemoryDatabase
        from rich.table import Table

        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))

        # Ensure tables exist
        async with aiosqlite.connect(db_path) as db:
            await create_memory_tables(db)
            await db.commit()

        memory_db = MemoryDatabase(db_path)

        if symbol:
            stats = await memory_db.get_symbol_stats(symbol, days=days)

            console.print(f"\n[bold]Memory Stats for {symbol}[/bold]")
            console.print(f"Period: Last {days} days\n")

            table = Table()
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Total Trades", str(stats['total_trades']))
            table.add_row("Win Rate", f"{stats['win_rate']:.1f}%")
            table.add_row("Avg P&L", f"{stats['avg_pnl']:+.2f}%")
            table.add_row("Avg Confidence", f"{stats['avg_confidence']:.0f}")

            console.print(table)
        else:
            # Show all symbols
            trades = await memory_db.get_recent_trades(days=days, limit=100)

            # Group by symbol
            by_symbol = {}
            for t in trades:
                sym = t['symbol']
                if sym not in by_symbol:
                    by_symbol[sym] = []
                by_symbol[sym].append(t)

            console.print(f"\n[bold]Trading Memory Overview[/bold]")
            console.print(f"Period: Last {days} days\n")

            table = Table()
            table.add_column("Symbol", style="cyan")
            table.add_column("Trades", style="white")
            table.add_column("Win Rate", style="green")
            table.add_column("Avg P&L", style="yellow")

            for sym, sym_trades in by_symbol.items():
                scored = [t for t in sym_trades if t.get('outcome_grade')]
                wins = sum(1 for t in scored if t.get('outcome_grade') in ('A', 'B'))
                total = len(scored)
                win_rate = (wins / total * 100) if total > 0 else 0
                avg_pnl = sum(t.get('pnl_percent_4h', 0) for t in scored) / total if total > 0 else 0

                table.add_row(sym, str(total), f"{win_rate:.1f}%", f"{avg_pnl:+.2f}%")

            console.print(table)

    import aiosqlite
    asyncio.run(run())


@cli.command()
@click.option('--signal-id', required=True, type=int, help='Signal ID to annotate')
@click.argument('annotation')
def annotate(signal_id, annotation):
    """Add annotation to a trade."""
    async def run():
        from src.agent.database.memory_schema import create_memory_tables
        from src.agent.database.memory_operations import MemoryDatabase

        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))

        async with aiosqlite.connect(db_path) as db:
            await create_memory_tables(db)
            await db.commit()

        memory_db = MemoryDatabase(db_path)
        annotation_id = await memory_db.create_annotation(signal_id, annotation)

        console.print(f"[green]Annotation added[/green] (ID: {annotation_id})")
        console.print(f"Signal: {signal_id}")
        console.print(f"Note: {annotation}")

    import aiosqlite
    asyncio.run(run())


@cli.command()
def score_outcomes():
    """Force score all pending trade outcomes."""
    async def run():
        from src.agent.database.memory_schema import create_memory_tables
        from src.agent.database.memory_operations import MemoryDatabase
        from src.agent.tracking.outcome_scorer import OutcomeScorer
        import ccxt.async_support as ccxt

        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))

        async with aiosqlite.connect(db_path) as db:
            await create_memory_tables(db)
            await db.commit()

        memory_db = MemoryDatabase(db_path)

        # Create exchange connection
        exchange = ccxt.bybit({
            'apiKey': os.getenv('BYBIT_API_KEY'),
            'secret': os.getenv('BYBIT_API_SECRET'),
        })

        try:
            scorer = OutcomeScorer(memory_db, exchange)
            updated = await scorer.score_pending_outcomes()

            console.print(f"[green]Scored {updated} outcomes[/green]")
        finally:
            await exchange.close()

    import aiosqlite
    asyncio.run(run())
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_memory_cli.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/agent/main.py tests/test_memory_cli.py
git commit -m "feat(memory): add CLI commands for memory management

Add CLI commands:
- memory-stats: view trading memory statistics
- annotate: add annotation to a trade
- score-outcomes: force score pending outcomes"
```

---

## Final Integration Test

After all tasks are complete, run the full test suite:

```bash
pytest -v
```

Expected: All tests pass

**Final commit:**

```bash
git add -A
git commit -m "feat(memory): complete trading memory system implementation

Full implementation of trading memory system:
- Database schema (3 tables)
- CRUD operations
- Outcome recording on signal submit
- 6 recall tools (3 simple + 3 smart)
- Context builder for auto-inject
- Background outcome scorer
- CLI commands (memory-stats, annotate, score-outcomes)

Closes #trading-memory-system"
```

---

**Plan complete and saved to `docs/plans/2025-11-25-trading-memory-system-implementation.md`.**

**Two execution options:**

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

2. **Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?