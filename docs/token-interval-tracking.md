# Token Interval Tracking

Track Claude API token consumption in 5-minute intervals during scanning sessions.

## Overview

The token interval tracking feature provides three levels of visibility:

1. **Real-time updates** - Console output every 5 minutes during operation
2. **End-of-session summary** - Table showing all intervals when session ends
3. **Historical query** - CLI command to review past sessions

## Real-Time Monitoring

When running the scanner with token tracking enabled, you'll see interval updates every 5 minutes:

```
[+5min] Interval 1: 1,234 tokens (890 in, 344 out) | Cost: $0.012 | 3 requests
[+10min] Interval 2: 2,156 tokens (1,502 in, 654 out) | Cost: $0.021 | 5 requests
[+15min] Interval 3: 987 tokens (701 in, 286 out) | Cost: $0.009 | 2 requests
```

These updates show:
- **Time elapsed** from session start (e.g., +5min, +10min)
- **Interval number** (1, 2, 3...)
- **Token counts** broken down by input and output
- **Cost** in USD for that 5-minute interval
- **Request count** for that interval

## End-of-Session Summary

When a scanning session ends, you'll see a detailed table:

```
Token Usage by 5-Minute Intervals
┌──────────┬──────────┬─────────────┬──────────────┬───────────┬──────────┐
│ Interval │ Duration │ Tokens (in) │ Tokens (out) │ Total     │ Cost     │
├──────────┼──────────┼─────────────┼──────────────┼───────────┼──────────┤
│ 1        │ 5:00     │ 890         │ 344          │ 1,234     │ $0.0120  │
│ 2        │ 5:00     │ 1,502       │ 654          │ 2,156     │ $0.0210  │
│ 3        │ 3:42     │ 701         │ 286          │ 987       │ $0.0090  │
├──────────┼──────────┼─────────────┼──────────────┼───────────┼──────────┤
│ TOTAL    │ 13:42    │ 3,093       │ 1,284        │ 4,377     │ $0.0420  │
└──────────┴──────────┴─────────────┴──────────────┴───────────┴──────────┘
```

The summary includes:
- All completed 5-minute intervals
- Final partial interval (e.g., 3:42 in the example)
- Total row with aggregated statistics

## Historical Query

### List Recent Sessions

View recently completed scanning sessions:

```bash
python -m src.agent.main token-intervals
```

Output:
```
Recent Token Tracking Sessions
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Session ID          Started              Duration  Tokens   Cost
sess_abc123...      2025-11-20 10:30:15  13:42    4,377    $0.0420
sess_def456...      2025-11-20 09:15:22  8:30     2,891    $0.0280

Use --session-id to see 5-minute interval breakdown
```

### View Specific Session Intervals

Drill into a specific session to see its 5-minute breakdown:

```bash
python -m src.agent.main token-intervals --session-id sess_abc123
```

This displays the same interval table format as the end-of-session summary.

### Adjust Number of Sessions Shown

```bash
python -m src.agent.main token-intervals --limit 20
```

Shows up to 20 recent sessions (default is 10).

## Configuration

### Interval Duration

The default interval is 5 minutes. You can customize this via environment variable:

```bash
export TOKEN_INTERVAL_MINUTES=10  # 10-minute intervals
python -m src.agent.main scan-movers --interval 300 --portfolio "Market Movers"
```

Valid values: Any positive integer (minutes)

### Enabling/Disabling

Token tracking (including intervals) is controlled by:

```bash
export TOKEN_TRACKING_ENABLED=true   # Enable (default)
export TOKEN_TRACKING_ENABLED=false  # Disable
```

When disabled, no interval tracking occurs.

## Use Cases

### 1. Cost Monitoring

Monitor token costs in real-time to:
- Catch expensive operations immediately
- Adjust scanning parameters if costs spike
- Budget for long-running sessions

### 2. Performance Analysis

Identify patterns in token usage:
- Which time periods have high activity
- When market conditions drive more analysis
- Optimize scanning intervals based on token usage

### 3. Debugging

Track down issues:
- When did token usage spike?
- Which interval had the error?
- Compare normal vs. problematic sessions

## Troubleshooting

### No Interval Updates During Scan

**Symptom:** Scanner runs but no `[+5min]` messages appear

**Causes:**
1. Session shorter than interval duration (5 minutes by default)
2. Token tracking disabled (`TOKEN_TRACKING_ENABLED=false`)
3. No market movers detected (no API calls made)

**Solution:** Check configuration and ensure scanner runs for at least one full interval.

### "Session not found" Error

**Symptom:** `python -m src.agent.main token-intervals --session-id sess_xyz` shows "Session sess_xyz not found"

**Causes:**
1. Invalid session ID
2. Session not yet completed
3. Database file missing or corrupted

**Solution:**
1. Run `token-intervals` without `--session-id` to see valid session IDs
2. Ensure session has ended before querying intervals
3. Check that `TOKEN_TRACKING_DB_PATH` points to correct database

### Interval Summary Not Showing at End

**Symptom:** Session ends but no interval table displayed

**Causes:**
1. No token usage recorded (no API calls made)
2. Token tracking disabled
3. Error during session end

**Solution:** Check logs for errors and verify token tracking is enabled.

## Implementation Details

- Intervals are tracked in-memory during session
- Completed intervals stored in database via `token_usage` table aggregation
- No new database tables required
- Minimal performance overhead (single time check per API call)
- Uses Rich library for table formatting

## Related Documentation

- [Token Tracking Design](./plans/2025-11-20-token-interval-tracking-design.md)
- [Implementation Plan](./plans/2025-11-20-token-intervals-implementation.md)
