# Trading Memory System Design

**Date:** 2025-11-25
**Status:** Approved

## Overview

A persistent memory system for CCTrader that learns from past trades and improves future decisions. The bot gains awareness of trade outcomes, market patterns, and signal accuracy across sessions.

### Storage Architecture

Two layers work together:

1. **Local trading DB** (`trading_data.db`) - Structured trade outcomes, pattern snapshots, signal accuracy metrics with fast queries
2. **claude-mem** - Cross-session search, timeline context, natural language queries via MCP

### Data Flow

```
Trade Signal Generated
    ↓
Execute (paper) → Store outcome locally
    ↓
Background job: Score outcome (1h/4h/24h price vs prediction)
    ↓
Push summary to claude-mem as observation
    ↓
Next analysis: Auto-inject relevant memories + agent can query more
```

### Memory Types

- Trade outcomes (entry, exit, P&L, predicted vs actual)
- Market condition snapshots (volatility, trend strength, volume profile)
- Signal accuracy stats (per symbol, per condition, per confidence level)
- Manual annotations (qualitative notes on why a trade worked/failed)

---

## Database Schema

New tables in `trading_data.db`:

### `trade_outcomes` - Core trade tracking

```sql
CREATE TABLE trade_outcomes (
    id INTEGER PRIMARY KEY,
    signal_id INTEGER,           -- FK to movers_signals
    symbol TEXT NOT NULL,
    direction TEXT,              -- LONG/SHORT
    confidence INTEGER,
    entry_price REAL,
    predicted_stop REAL,
    predicted_target REAL,

    -- Actual outcomes (filled by background scorer)
    price_1h REAL,
    price_4h REAL,
    price_24h REAL,
    hit_target BOOLEAN,
    hit_stop BOOLEAN,
    max_favorable REAL,          -- Best price in our direction
    max_adverse REAL,            -- Worst price against us

    -- Scoring
    pnl_percent_1h REAL,
    pnl_percent_4h REAL,
    pnl_percent_24h REAL,
    outcome_grade TEXT,          -- A/B/C/D/F based on prediction accuracy

    -- Metadata
    created_at TEXT,
    scored_at TEXT
);
```

### `market_snapshots` - Conditions at signal time

```sql
CREATE TABLE market_snapshots (
    id INTEGER PRIMARY KEY,
    signal_id INTEGER,
    symbol TEXT,

    -- Indicators at signal time
    rsi_15m REAL, rsi_1h REAL, rsi_4h REAL,
    macd_signal TEXT,            -- bullish/bearish/neutral
    volatility_percentile REAL,  -- 0-100, where current vol ranks historically
    volume_ratio REAL,           -- vs 20-period average
    trend_strength REAL,         -- ADX or similar
    btc_correlation REAL,        -- how correlated to BTC

    market_condition TEXT,       -- trending_up/trending_down/ranging/volatile
    created_at TEXT
);
```

### `trade_annotations` - Manual notes

```sql
CREATE TABLE trade_annotations (
    id INTEGER PRIMARY KEY,
    signal_id INTEGER,
    annotation TEXT,             -- "News-driven, ignore pattern"
    tags TEXT,                   -- JSON array: ["news", "ignore"]
    created_at TEXT
);
```

---

## Auto-Injected Context

Before each analysis, the system builds a memory context block and injects it into the agent prompt.

### Trigger: Symbol-specific history

When analyzing `{SYMBOL}`:
- Last 5 trades on this symbol (direction, confidence, outcome grade, P&L)
- Win rate on this symbol (last 30 days)
- Best/worst performing setups for this symbol

### Trigger: Market condition matching

When current conditions detected as `{CONDITION}`:
- Query past trades where market_condition = `{CONDITION}`
- Show win rate under these conditions
- Note any patterns ("ranging markets: your LONG signals underperform")

### Injected Format

```
<trading_memory>
## Recent {SYMBOL} History (Last 5 trades)
| Date | Direction | Conf | Outcome | P&L 4h |
|------|-----------|------|---------|--------|
| 11/24 | LONG | 72 | B | +2.1% |
| 11/22 | SHORT | 65 | D | -1.8% |
...

## {SYMBOL} Stats (30 days)
Win rate: 58% | Avg P&L: +0.8% | Best setup: RSI oversold + volume spike

## Similar Market Conditions (volatile + trending_up)
Past 10 trades in these conditions: 70% win rate
Note: HIGH confidence (>75) signals performed best here
</trading_memory>
```

---

## Active Recall Tools

The agent gets tools to query memories when it wants deeper context.

### Simple Queries

```python
@tool
def recall_symbol_history(symbol: str, limit: int = 10) -> dict:
    """Get recent trade outcomes for a specific symbol."""
    # Returns: trades, win_rate, avg_pnl, best/worst outcomes

@tool
def recall_recent_trades(days: int = 7) -> dict:
    """Get all recent trades across all symbols."""
    # Returns: trades list, overall stats, top performers

@tool
def recall_signal_accuracy(confidence_min: int, confidence_max: int) -> dict:
    """Check how accurate signals in a confidence range have been."""
    # Returns: win_rate, avg_pnl, sample_size for that confidence band
```

### Smart Queries

```python
@tool
def recall_similar_setups(
    rsi_range: tuple,
    trend: str,
    volatility: str  # low/medium/high
) -> dict:
    """Find past trades with similar technical setup."""
    # Matches market_snapshots, returns outcomes of similar conditions

@tool
def recall_what_worked(market_condition: str) -> dict:
    """Get winning strategies for a market condition."""
    # Returns: best direction, optimal confidence threshold, patterns to avoid

@tool
def search_trade_memory(query: str) -> dict:
    """Natural language search via claude-mem."""
    # Proxies to claude-mem MCP for fuzzy/semantic search
    # e.g., "trades where news caused unexpected reversal"
```

### Usage Example

```
Agent reasoning: "RSI is 28 on 1h, let me check similar setups..."
→ Agent calls recall_similar_setups(rsi_range=(25,35), trend="down", volatility="high")
→ Gets back: "12 similar setups, 75% resulted in bounce, avg +3.2% in 4h"
→ Agent increases confidence in LONG signal
```

---

## Outcome Scoring

### Background Scorer

A scheduled job runs after each trade to score outcomes:

```python
async def score_pending_outcomes():
    """Run every 15 minutes to score trades at 1h/4h/24h marks."""

    pending = await db.get_unscored_outcomes()

    for outcome in pending:
        age_hours = hours_since(outcome.created_at)
        current_price = await exchange.fetch_price(outcome.symbol)

        # Update price snapshots at each interval
        if age_hours >= 1 and not outcome.price_1h:
            outcome.price_1h = current_price
            outcome.pnl_percent_1h = calc_pnl(outcome, current_price)

        if age_hours >= 4 and not outcome.price_4h:
            outcome.price_4h = current_price
            outcome.pnl_percent_4h = calc_pnl(outcome, current_price)

        if age_hours >= 24 and not outcome.price_24h:
            outcome.price_24h = current_price
            outcome.pnl_percent_24h = calc_pnl(outcome, current_price)
            outcome.outcome_grade = calculate_grade(outcome)
            outcome.scored_at = now()

            # Push to claude-mem once fully scored
            await sync_to_claude_mem(outcome)
```

### Grade Calculation

| Grade | Criteria |
|-------|----------|
| A | Hit target, didn't hit stop |
| B | Profitable at 24h (>1%), direction correct |
| C | Small profit/loss (-1% to +1%) |
| D | Loss but stop wasn't hit |
| F | Hit stop loss or >3% adverse move |

### Claude-mem Sync

```python
async def sync_to_claude_mem(outcome):
    """Push scored trade as observation to claude-mem."""

    observation = {
        "type": "trade_outcome",
        "title": f"{outcome.symbol} {outcome.direction} - Grade {outcome.grade}",
        "narrative": f"""
            Signal: {outcome.direction} at {outcome.entry_price} (conf: {outcome.confidence})
            Predicted: TP {outcome.predicted_target}, SL {outcome.predicted_stop}
            Actual 24h: {outcome.price_24h} ({outcome.pnl_percent_24h:+.1f}%)
            Grade: {outcome.grade}
            Conditions: {outcome.market_condition}
        """,
        "concepts": ["trade-outcome", outcome.symbol.lower(), outcome.grade.lower()],
        "files": []
    }

    # Call claude-mem MCP to store
    await mcp_call("claude-mem", "add_observation", observation)
```

---

## Integration Points

### Existing Code Modifications

| File | Change |
|------|--------|
| `src/agent/scanner/tools.py` | After `submit_trading_signal()`, create `trade_outcomes` + `market_snapshots` records |
| `src/agent/scanner/prompts.py` | Inject `<trading_memory>` block before analysis prompt |
| `src/agent/scanner/main_loop.py` | Trigger scorer check at end of each scan cycle |

### New Modules

| File | Purpose |
|------|---------|
| `src/agent/database/memory_schema.py` | Schema for 3 new tables |
| `src/agent/database/memory_operations.py` | CRUD for trade outcomes, snapshots, annotations |
| `src/agent/tools/memory_tools.py` | All 6 recall tools |
| `src/agent/tracking/outcome_scorer.py` | Background scoring logic |
| `src/agent/memory/context_builder.py` | Build auto-inject context block |

### New CLI Commands

```bash
# Add annotation to a trade
python -m src.agent.main annotate --signal-id 123 "News-driven pump, ignore"

# View trade memory stats
python -m src.agent.main memory-stats --symbol BTC/USDT --days 30

# Force score pending outcomes
python -m src.agent.main score-outcomes
```

---

## Implementation Order

| Task | Description | Complexity |
|------|-------------|------------|
| 1 | Database schema (3 tables) | Low |
| 2 | Outcome recording on signal submit | Low |
| 3 | Market snapshot capture | Medium |
| 4 | Simple recall tools (3 tools) | Medium |
| 5 | Auto-inject context builder | Medium |
| 6 | Background scorer | Medium |
| 7 | Smart recall tools (3 tools) | Medium |
| 8 | Claude-mem sync | Medium |
| 9 | Manual annotation CLI command | Low |

---

## Success Criteria

1. Every trade signal creates an outcome record
2. Outcomes are automatically scored at 1h/4h/24h intervals
3. Agent sees relevant history before each analysis
4. Agent can query past trades and patterns on demand
5. Scored trades sync to claude-mem for cross-session search
6. Manual annotations can be added via CLI
