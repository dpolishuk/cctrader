# Daily Session Mode

## Overview

Daily session mode maintains a single Claude Code conversation per trading day, consolidating all symbol analyses into one continuous thread instead of creating separate sessions for each analysis.

## Benefits

- **Consolidated view**: All analyses from a trading day in one scrollable conversation
- **Better context**: Claude remembers previous analyses within the same day
- **Easier review**: Review all trading decisions in chronological order
- **Session persistence**: Resume the same session across scanner restarts

## Usage

### Basic Daily Mode

```bash
python -m src.agent.main scan-movers --daily
```

### With Custom Settings

```bash
# Daily mode with 60s interval
python -m src.agent.main scan-movers --daily --interval 60

# Daily mode with custom portfolio
python -m src.agent.main scan-movers --daily --portfolio "Production"
```

### Without Daily Mode (Default)

```bash
# Each symbol gets its own session
python -m src.agent.main scan-movers
```

## How It Works

### Session ID Format

Daily sessions use the format: `scanner-YYYY-MM-DD`

Examples:
- `scanner-2025-11-21`
- `scanner-2025-11-22`

### Session Lifecycle

1. **First analysis of the day**: Creates new session with daily ID
2. **Subsequent analyses**: Reuses same Claude client and session
3. **Next day**: Automatically creates fresh session with new date
4. **Scanner restart**: Resumes existing daily session if same day

### Conversation Flow

**Without --daily:**
```
[Session 1] Analyze BTC/USDT
[Session 2] Analyze ETH/USDT
[Session 3] Analyze SOL/USDT
```

**With --daily:**
```
[Session scanner-2025-11-21]
  Analyze BTC/USDT
  Analyze ETH/USDT
  Analyze SOL/USDT
  [All in one conversation]
```

## Database Storage

Daily sessions are stored in `agent_sessions` table:

```sql
SELECT * FROM agent_sessions WHERE operation_type = 'scanner';
-- operation_type | session_id           | created_at  | last_used_at
-- scanner        | scanner-2025-11-21   | 2025-11-21  | 2025-11-21
```

## Viewing Session History

```bash
# View session stats
python -m src.agent.main sessions

# Clear old sessions
python -m src.agent.main sessions --clear-type scanner
```

## Best Practices

1. **Use daily mode for production trading**: Easier to review all decisions
2. **Use regular mode for testing**: Isolate test analyses from production
3. **Monitor session length**: Very long trading days may hit token limits
4. **Review daily summaries**: Check consolidated conversation at end of day

## Troubleshooting

### Session not resuming

Check database for existing session:
```bash
sqlite3 trading_data.db "SELECT * FROM agent_sessions WHERE operation_type='scanner';"
```

### Session from wrong day

Daily sessions auto-expire. Old sessions are ignored when new day starts.

### Token limits

If hitting context limits, clear old session:
```bash
python -m src.agent.main sessions --clear-type scanner
```
