# Design: Token Consumption Monitoring Per 5-Minute Intervals

**Date:** 2025-11-20
**Status:** Approved

## Overview & Goals

### Problem
Currently, token tracking shows overall session totals but doesn't provide visibility into consumption patterns over time. When running long scanning sessions, you can't see if token usage is steady, spiking, or decreasing without post-analysis.

### Solution
Add 5-minute interval tracking and display that shows:
1. **Real-time updates** - Simple summary every 5 minutes during scanner operation
2. **End-of-session summary** - Table showing each interval's token usage
3. **Historical query** - CLI command to view past session breakdowns

### Key Design Principle
Minimal logging overhead, no impact on scanner performance. The database already has timestamps on every token usage record, so we aggregate in-memory for real-time and query from DB for historical.

## Architecture & Components

### Component 1: IntervalTracker
Added to `token_tracker.py` to track consumption within 5-minute windows:
- Maintains current interval start time
- Accumulates tokens/costs for current interval
- Triggers display when 5 minutes elapsed
- Stores completed intervals for end-of-session summary

### Component 2: Real-Time Display
- Check elapsed time on each `record_usage()` call
- When 5 minutes pass, print simple summary and reset counters
- Format: `[+5min] Tokens: 1,234 (in: 890, out: 344) | Cost: $0.012`
- Non-intrusive INFO level logging

### Component 3: End-of-Session Summary
- When `end_session()` called, print table of all intervals
- Use Rich library for clean table formatting
- Shows: Interval #, Duration, Tokens (in/out/total), Cost

### Component 4: Historical Query CLI
- New command: `token-intervals`
- Lists recent sessions with IDs
- User can drill into specific session to see its 5-min breakdown
- Queries database directly, no in-memory state needed

## Data Flow & Implementation

### Real-Time Flow
```
Scanner running → record_usage() called
  ↓
Check: 5 minutes elapsed since last interval?
  ↓ Yes
Print interval summary to console
Reset interval counters
Start new interval
  ↓ No
Accumulate tokens/cost to current interval
Continue
```

### Database Strategy
- NO new tables needed
- Use existing `token_usage` table with timestamps
- Query aggregates: `SELECT SUM(tokens) WHERE timestamp BETWEEN start AND end`
- Group by 5-minute buckets using SQL time functions

### Implementation Details

**IntervalTracker state (in TokenTracker):**
- `interval_start_time`: When current interval began (float, time.time())
- `interval_number`: Current interval counter (1, 2, 3...)
- `current_interval`: Dict with tokens_input, tokens_output, cost, requests
- `completed_intervals`: List of interval dicts for end summary
- `INTERVAL_DURATION`: 300 seconds (5 minutes)

**Modified `record_usage()`:**
- After recording to DB, call `_check_interval()`
- If 5min elapsed: display, append to completed_intervals, reset current
- Accumulate to current_interval regardless

**New `_check_interval()` method:**
- Calculate elapsed: `time.time() - interval_start_time`
- If >= 300 seconds:
  - Log interval summary
  - Append current_interval to completed_intervals
  - Reset current_interval counters
  - Increment interval_number
  - Set new interval_start_time

**Modified `end_session()`:**
- Capture final partial interval if any usage recorded
- Generate and print interval summary table using Rich
- Call existing DB end_session logic

## Output Formats & CLI Interface

### Real-Time Console Output
```
[+5min] Interval 1: 1,234 tokens (890 in, 344 out) | Cost: $0.012 | 3 requests
[+10min] Interval 2: 2,156 tokens (1,502 in, 654 out) | Cost: $0.021 | 5 requests
[+15min] Interval 3: 987 tokens (701 in, 286 out) | Cost: $0.009 | 2 requests
```

### End-of-Session Summary Table
```
Token Usage by 5-Minute Intervals
┌──────────┬──────────┬─────────────┬──────────────┬───────────┬──────────┐
│ Interval │ Duration │ Tokens (in) │ Tokens (out) │ Total     │ Cost     │
├──────────┼──────────┼─────────────┼──────────────┼───────────┼──────────┤
│ 1        │ 5:00     │ 890         │ 344          │ 1,234     │ $0.012   │
│ 2        │ 5:00     │ 1,502       │ 654          │ 2,156     │ $0.021   │
│ 3        │ 3:42     │ 701         │ 286          │ 987       │ $0.009   │
├──────────┼──────────┼─────────────┼──────────────┼───────────┼──────────┤
│ TOTAL    │ 13:42    │ 3,093       │ 1,284        │ 4,377     │ $0.042   │
└──────────┴──────────┴─────────────┴──────────────┴───────────┴──────────┘
```

### New CLI Command

**Usage:**
```bash
# List recent sessions
python -m src.agent.main token-intervals

# Show specific session breakdown
python -m src.agent.main token-intervals --session-id sess_abc123
```

**Output for `token-intervals` (list mode):**
```
Recent Token Tracking Sessions
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Session ID          Started              Duration  Tokens   Cost
sess_abc123         2025-11-20 10:30:15  13:42    4,377    $0.042
sess_def456         2025-11-20 09:15:22  8:30     2,891    $0.028

Use --session-id to see 5-minute interval breakdown
```

**Output for specific session:**
Shows same table format as end-of-session summary, but queries from database.

## Error Handling & Edge Cases

### Edge Case 1: Session shorter than 5 minutes
- Don't print any interval updates during session
- End-of-session summary shows single partial interval
- Example: 3:42 duration → shows "Interval 1 (3:42)" in summary

### Edge Case 2: Session ends mid-interval
- Capture partial interval in end-of-session summary
- Last row shows actual duration (e.g., "3:42" not "5:00")

### Edge Case 3: No token usage in an interval
- Still display interval marker: `[+5min] Interval 1: 0 tokens | Cost: $0.00 | 0 requests`
- Shows scanner is running but idle (no movers detected)

### Edge Case 4: Token tracking disabled
- IntervalTracker not initialized if `TOKEN_TRACKING_ENABLED=false`
- No real-time updates, no end-of-session summary
- Graceful degradation

### Error Scenarios

**1. Database query fails for historical intervals:**
- Catch exception, show error message
- Don't crash CLI command
- Example: "Error retrieving session data: [error details]"

**2. Session ID not found:**
- Show friendly message: "Session sess_xyz not found"
- List 5 most recent session IDs as suggestions

**3. Rich library formatting fails:**
- Fallback to plain text table format using simple string formatting
- Still readable, just less pretty

### Configuration

Add to `config.py`:
```python
TOKEN_INTERVAL_MINUTES: int = int(os.getenv("TOKEN_INTERVAL_MINUTES", "5"))
```

Allows user to adjust interval duration via environment variable if needed.

## Implementation Files

### Files to Modify
1. `src/agent/tracking/token_tracker.py` - Add IntervalTracker logic
2. `src/agent/main.py` - Add `token-intervals` CLI command
3. `src/agent/config.py` - Add TOKEN_INTERVAL_MINUTES config
4. `src/agent/database/token_operations.py` - Add method to query intervals from DB

### Files to Create
1. `src/agent/tracking/interval_display.py` - Rich table formatting utilities (optional, can inline)

### Tests to Add
1. `tests/test_interval_tracker.py` - Test interval accumulation and reset logic
2. Update `tests/test_token_tracker.py` - Test interval tracking integration
3. Update `tests/test_integration_token_tracking.py` - Test end-to-end with intervals

## Benefits

1. **Real-time visibility:** See token consumption patterns as they happen
2. **Cost monitoring:** Catch expensive operations immediately
3. **Performance insights:** Identify which time periods have high token usage
4. **Historical analysis:** Review past sessions to optimize costs
5. **Simple interface:** Clean output that doesn't clutter logs
6. **No schema changes:** Uses existing database structure
7. **Configurable:** Adjust interval duration via environment variable

## Non-Goals

- Real-time graphing (would require additional dependencies)
- Predictive analysis (out of scope, can be added later)
- Alerts/notifications (can be added later if needed)
- Per-symbol breakdown within intervals (too granular, use metadata for this)
