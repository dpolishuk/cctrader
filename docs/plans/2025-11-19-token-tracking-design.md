# Token Tracking System Design

**Date:** 2025-11-19
**Status:** Approved
**Scope:** Full agent tracking with comprehensive metrics and Claude Code rate limit monitoring

## Overview

Add comprehensive token consumption tracking across the entire trading agent application to understand input/output token usage, estimate costs, track hourly/daily consumption, and monitor proximity to Claude Code rate limits.

## Requirements

### Functional Requirements

1. **Full Agent Tracking** - Track tokens for all Claude Agent SDK agent calls across the application
2. **Comprehensive Metrics** - Token counts, costs, timestamps, operation types, model used, and rate limit proximity
3. **Dual Storage & Display** - Store in database for historical analysis AND display real-time metrics during operations
4. **Configurable Limits** - Store limits in `.env` with helper command to fetch current values from Anthropic documentation

### Non-Functional Requirements

- Non-invasive: existing code continues to work unchanged
- Async-compatible: works with asyncio-based architecture
- Performance: non-blocking database writes, batch inserts for high-frequency operations
- Backward compatible: opt-in via configuration flag
- Graceful degradation: tracking failures don't break operations

## Architecture

### Core Components

#### 1. Token Tracker Module (`agent/tracking/`)

**TokenTracker Class** - Singleton that wraps Claude Agent SDK usage
- Intercepts all agent calls to capture token metrics
- Tracks: input/output tokens, cost, timestamp, operation type, model, session ID
- Calculates rate limit proximity based on configurable thresholds
- Manages session lifecycle (start/end)

**Pricing Calculator** - Cost estimation utility
- Configurable pricing per model (per 1M tokens)
- Supports input/output token pricing differences
- Claude Sonnet 4.5: $3/1M input, $15/1M output

**Display Components** - Rich console integration
- Real-time token usage panel
- Color-coded status indicators (green/yellow/red)
- Progress bars for rate limit proximity

#### 2. Database Schema

**token_usage** - Per-request tracking
```sql
CREATE TABLE token_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT NOT NULL,
    operation_type TEXT NOT NULL,  -- 'analysis', 'scanner', 'monitor'
    model TEXT NOT NULL,
    tokens_input INTEGER NOT NULL,
    tokens_output INTEGER NOT NULL,
    tokens_total INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    duration_seconds REAL,
    metadata JSON  -- symbol, timeframe, etc.
);
```

**token_sessions** - Session aggregates
```sql
CREATE TABLE token_sessions (
    session_id TEXT PRIMARY KEY,
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    operation_mode TEXT,
    total_requests INTEGER DEFAULT 0,
    total_tokens_input INTEGER DEFAULT 0,
    total_tokens_output INTEGER DEFAULT 0,
    total_cost_usd REAL DEFAULT 0.0,
    is_active BOOLEAN DEFAULT 1
);
```

**rate_limit_tracking** - Rolling window counters
```sql
CREATE TABLE rate_limit_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT NOT NULL,  -- 'hourly', 'daily'
    window_start DATETIME NOT NULL,
    request_count INTEGER DEFAULT 0,
    token_count INTEGER DEFAULT 0,
    UNIQUE(period, window_start)
);
```

**Indexes:**
- `idx_token_usage_timestamp` on `token_usage(timestamp)`
- `idx_token_usage_session` on `token_usage(session_id)`
- `idx_rate_limit_period` on `rate_limit_tracking(period, window_start)`

#### 3. Database Operations

**TokenDatabase Class** (`agent/database/token_operations.py`)
- `record_token_usage()` - Insert usage record, update session, increment rate limit counters
- `get_hourly_usage()` - Aggregate last hour
- `get_daily_usage()` - Aggregate last 24 hours
- `get_usage_by_operation()` - Group by operation type
- `get_session_stats()` - Get statistics for specific session
- `check_rate_limit_status()` - Calculate percentage of limits used
- `cleanup_old_tracking()` - Prune records older than retention period

#### 4. Integration Points

**TokenTrackingAgent Wrapper**
```python
class TokenTrackingAgent:
    def __init__(self, agent, tracker, operation_type):
        self.agent = agent
        self.tracker = tracker
        self.operation_type = operation_type

    async def run(self, prompt):
        start_time = time.time()
        result = await self.agent.run(prompt)

        # Extract token usage from result.usage
        tokens_in = result.usage.input_tokens
        tokens_out = result.usage.output_tokens

        # Calculate cost
        cost = calculate_cost(tokens_in, tokens_out, result.model)

        # Track in database
        await self.tracker.record_usage(
            operation=self.operation_type,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            duration=time.time() - start_time,
            model=result.model
        )

        return result
```

**Apply wrapper to:**
- `TradingAgent` in `agent/trading_agent.py`
- `AgentWrapper` in `agent/scanner/agent_wrapper.py`
- Any new agent instantiations

## User Interface

### Real-Time Display

**Console Panel (using Rich library):**
```
╭─────────────────── Token Usage ───────────────────╮
│ Current Request: 1,245 in / 892 out ($0.032)     │
│ Session Total:   15,420 in / 12,305 out ($0.41)  │
│ Hourly Usage:    45,230 tokens (23% of limit)    │
│ Daily Usage:     156,890 tokens (12% of limit)   │
│ Est. Cost/Hour:  $0.85                            │
╰───────────────────────────────────────────────────╯
```

**Status Indicators:**
- 🟢 Green: < 50% of limit
- 🟡 Yellow: 50-80% of limit
- 🔴 Red: > 80% of limit
- ⚠️ Warning when approaching limits

**Update Frequency:**
- After each agent call (immediate)
- Summary at end of operation
- No polling overhead (event-driven)

### CLI Commands

#### 1. `token-stats` - Usage reports
```bash
python -m agent.main token-stats --period hourly
python -m agent.main token-stats --period daily --operation scanner
python -m agent.main token-stats --session <session-id>
```

**Output:**
- Tabular report with Rich formatting
- Breakdown by operation type
- Cost analysis
- Token distribution (input vs output)

#### 2. `token-limits` - Rate limit status
```bash
python -m agent.main token-limits
```

**Output:**
- Current usage vs configured limits
- Percentage used
- Time until hourly/daily reset
- Projected usage based on recent rate

#### 3. `fetch-limits` - Get latest Claude Code limits
```bash
python -m agent.main fetch-limits
```

**Behavior:**
- Uses Perplexity/Context7 MCP to query Anthropic documentation
- Searches for "Claude Code rate limits 2025 Anthropic documentation"
- Parses results for hourly/daily message limits
- Compares with current `.env` values
- Suggests updates if limits changed
- Fallback: keeps existing config if search fails

#### 4. Enhanced existing commands
```bash
python -m agent.main analyze --symbol BTC/USDT --show-tokens
python -m agent.main monitor --symbol BTC/USDT --show-tokens
python -m agent.main scan-movers --show-tokens
```

Adds token usage panel to existing command output.

## Configuration

### Environment Variables (`.env` additions)

```env
# Token Tracking Configuration
TOKEN_TRACKING_ENABLED=true

# Claude Code Rate Limits (messages/requests)
CLAUDE_HOURLY_LIMIT=500
CLAUDE_DAILY_LIMIT=5000

# Claude Sonnet 4.5 Pricing (per 1M tokens)
CLAUDE_COST_PER_1M_INPUT=3.00
CLAUDE_COST_PER_1M_OUTPUT=15.00

# Alert Thresholds (percentage)
TOKEN_WARNING_THRESHOLD=50
TOKEN_CRITICAL_THRESHOLD=80

# Tracking Retention
TOKEN_HISTORY_DAYS=90  # How long to keep detailed records
```

### Config Class Updates (`agent/config.py`)

```python
@dataclass
class Config:
    # ... existing fields ...

    # Token Tracking
    TOKEN_TRACKING_ENABLED: bool = os.getenv("TOKEN_TRACKING_ENABLED", "true").lower() == "true"
    CLAUDE_HOURLY_LIMIT: int = int(os.getenv("CLAUDE_HOURLY_LIMIT", "500"))
    CLAUDE_DAILY_LIMIT: int = int(os.getenv("CLAUDE_DAILY_LIMIT", "5000"))
    CLAUDE_COST_PER_1M_INPUT: float = float(os.getenv("CLAUDE_COST_PER_1M_INPUT", "3.00"))
    CLAUDE_COST_PER_1M_OUTPUT: float = float(os.getenv("CLAUDE_COST_PER_1M_OUTPUT", "15.00"))
    TOKEN_WARNING_THRESHOLD: int = int(os.getenv("TOKEN_WARNING_THRESHOLD", "50"))
    TOKEN_CRITICAL_THRESHOLD: int = int(os.getenv("TOKEN_CRITICAL_THRESHOLD", "80"))
    TOKEN_HISTORY_DAYS: int = int(os.getenv("TOKEN_HISTORY_DAYS", "90"))
```

### Validation

On startup, validate:
- Pricing values are positive numbers
- Limits are reasonable (hourly < daily)
- Thresholds are between 0-100
- Warning threshold < critical threshold

## Implementation Plan

### Phase 1: Core Infrastructure
- Create `agent/tracking/` module structure
- Implement `TokenTracker` class
- Implement pricing calculator utility
- Add database schema migration
- Create `TokenDatabase` operations class

### Phase 2: Agent Integration
- Wrap `TradingAgent` with token tracking
- Wrap `AgentWrapper` (scanner) with token tracking
- Add session management (start/end tracking)
- Test with single operations
- Verify token capture accuracy

### Phase 3: Display & Reporting
- Implement Rich console panel components
- Add real-time display to monitor/scan commands
- Create `token-stats` CLI command with report generation
- Create `token-limits` CLI command
- Add `--show-tokens` flag to existing commands

### Phase 4: Rate Limit Management
- Implement rolling window counters
- Add limit checking before operations
- Create `fetch-limits` command with MCP integration
- Add configuration validation
- Implement cleanup job for old data

### Phase 5: Testing & Documentation
- Unit tests for tracker, pricing, rate limit logic
- Integration tests with mock agent responses
- Update README with token tracking features
- Add usage examples
- Add troubleshooting guide

## Rollout Strategy

### Backward Compatibility
- Token tracking is opt-in via `TOKEN_TRACKING_ENABLED` flag
- Existing operations work unchanged if tracking disabled
- Graceful degradation if database migration fails
- No breaking changes to existing APIs

### Performance Considerations
- Async database writes (non-blocking)
- Batch inserts for high-frequency operations (scanner)
- Index on timestamp and session_id for fast queries
- Automatic cleanup of old data (90-day retention default)
- In-memory queuing if database temporarily unavailable

### Error Handling
- If tracking fails, log error but don't break operation
- Missing usage info from agent? Log warning, estimate tokens
- Database connection issues? Queue records in memory, flush later
- MCP search failures in `fetch-limits`? Keep existing config
- Validation errors? Use defaults with warning

## Files to Create/Modify

### New Files
- `agent/tracking/__init__.py`
- `agent/tracking/token_tracker.py` - Core tracker class
- `agent/tracking/pricing.py` - Cost calculations
- `agent/tracking/display.py` - Rich console components
- `agent/database/token_schema.py` - Database schema
- `agent/database/token_operations.py` - Database operations
- `tests/test_token_tracking.py` - Unit tests
- `tests/test_token_pricing.py` - Pricing tests

### Modified Files
- `agent/trading_agent.py` - Add token tracking wrapper
- `agent/scanner/agent_wrapper.py` - Add token tracking
- `agent/main.py` - Add new CLI commands
- `agent/config.py` - Add token tracking config
- `.env.example` - Add token tracking variables
- `README.md` - Document token tracking features

## Success Criteria

1. All agent calls automatically tracked without code changes to existing logic
2. Real-time token usage visible during operations
3. Historical token usage queryable via CLI and database
4. Accurate cost estimation within 1% of actual Anthropic billing
5. Rate limit proximity warnings prevent quota exhaustion
6. Zero performance impact on agent operations (< 5ms overhead per call)
7. 90-day token history available for trend analysis

## Future Enhancements

- Token budget alerts (email/webhook when approaching thresholds)
- Per-symbol token consumption analysis
- Token efficiency metrics (tokens per trading signal)
- Integration with Anthropic API for real-time quota checking
- Export reports to CSV/JSON
- Grafana/Prometheus metrics integration
- Token consumption forecasting based on historical patterns
