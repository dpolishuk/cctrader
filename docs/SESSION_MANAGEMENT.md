# Claude Agent SDK Session Management

## Problem Solved

Previously, every scanner run or analysis created a **new Claude Agent SDK session**, losing all conversation context. This caused:
- No memory between runs
- Inability to maintain context for ongoing operations
- Mixed context between different operation types (scanner, analysis, monitoring)

## Solution

The `SessionManager` provides:
1. **Session Persistence**: Sessions are stored in the database and resumed on next run
2. **Session Isolation**: Separate sessions for different operation types
3. **Automatic Resumption**: Sessions automatically resume with full conversation history

## Architecture

### Session Types

Sessions are isolated by operation type:
- `scanner`: Market movers scanner operations
- `analysis`: Single-shot market analysis
- `monitor`: Continuous monitoring
- `paper_trading`: Paper trading operations

Each operation type maintains its own independent session with separate context.

### How It Works

```python
# 1. Initialize SessionManager
from src.agent.session_manager import SessionManager

session_manager = SessionManager(db_path)
await session_manager.init_db()

# 2. Create AgentWrapper with session management
agent = AgentWrapper(
    agent_options,
    session_manager=session_manager,
    operation_type=SessionManager.SCANNER  # or ANALYSIS, MONITOR, etc.
)

# 3. Run analysis - automatically resumes session if exists
result = await agent.run(prompt, symbol="BTCUSDT")
```

**What happens:**
1. On first run: New session is created, session ID is saved to database
2. On subsequent runs: Session ID is retrieved, passed to `client.query(resume=session_id)`
3. Claude Agent SDK loads full conversation history
4. Context is maintained across runs

## CLI Commands

### List Active Sessions

```bash
python -m src.agent.main sessions
```

Output:
```
Claude Agent SDK Sessions
┌────────────────┬──────────────────┬────────────────────┬────────────────────┐
│ Operation Type │ Session ID       │ Created            │ Last Used          │
├────────────────┼──────────────────┼────────────────────┼────────────────────┤
│ scanner        │ sess_abc123...   │ 2025-11-19 10:30   │ 2025-11-19 14:22   │
│ analysis       │ sess_def456...   │ 2025-11-19 11:15   │ 2025-11-19 12:00   │
└────────────────┴──────────────────┴────────────────────┴────────────────────┘
```

### Clear Specific Session

Force a fresh start for scanner (clears conversation history):
```bash
python -m src.agent.main sessions --clear-type scanner
```

### Clear All Sessions

Reset all sessions (start fresh for all operation types):
```bash
python -m src.agent.main sessions --clear
```

## Use Cases

### 1. Long-Running Scanner

The scanner maintains context across multiple scans:
```bash
# First scan - creates new session
python -m src.agent.main scan-movers --interval 60

# Stop and restart - resumes same session
python -m src.agent.main scan-movers --interval 60
```

**Benefits:**
- Agent remembers symbols it analyzed recently
- Can reference previous signals in new analysis
- Builds understanding of market patterns over time

### 2. Interactive Analysis

Run multiple analyses while maintaining context:
```bash
# Analyze BTC
python -m src.agent.main analyze --symbol BTC/USDT

# Analyze ETH - agent remembers BTC analysis
python -m src.agent.main analyze --symbol ETH/USDT

# Agent can now compare: "ETH looks similar to the BTC pattern I saw earlier"
```

### 3. Session Isolation

Scanner and analysis sessions don't interfere:
```bash
# Scanner builds context about high-volatility moves
python -m src.agent.main scan-movers

# Analysis maintains separate context for detailed research
python -m src.agent.main analyze --symbol SOL/USDT
```

## Database Schema

```sql
CREATE TABLE agent_sessions (
    operation_type TEXT PRIMARY KEY,  -- scanner, analysis, monitor, paper_trading
    session_id TEXT NOT NULL,         -- Claude SDK session ID
    created_at TEXT NOT NULL,         -- ISO timestamp
    last_used_at TEXT NOT NULL,       -- ISO timestamp
    metadata TEXT                     -- Optional JSON metadata
)
```

## Advanced: Session Forking

To experiment with alternatives while preserving the main session:

```python
# In your code (not currently exposed in CLI)
from src.agent.scanner.agent_wrapper import AgentWrapper

# Fork the scanner session to try alternative analysis
agent_options['fork_session'] = True
agent = AgentWrapper(agent_options, session_manager, operation_type="scanner_fork")
```

This creates a new session ID starting from the scanner's current state.

## When to Clear Sessions

Clear sessions when:
- **Agent behavior becomes stale**: "Agent seems stuck in old patterns"
- **Major strategy change**: Switching from momentum to mean reversion
- **Testing new prompts**: Ensure clean slate for prompt experiments
- **Context pollution**: Mixed signals from unrelated analyses

Don't clear sessions during:
- **Normal operation**: Let context build naturally
- **Temporary issues**: Network errors, API rate limits
- **Symbol switches**: Same strategy, different symbols benefits from context

## Implementation Details

### Session ID Format

Claude Agent SDK generates session IDs like: `sess_01JCXXXXXXXXXXXXXXXXXXXXX`

### Session Resumption

When resuming, Claude Agent SDK:
1. Loads full conversation history from the session ID
2. Reconstructs agent state (tools, prompts, context)
3. Continues as if no interruption occurred

### Performance

- Session lookup: ~1ms (SQLite indexed query)
- Session save: ~2ms (SQLite upsert)
- Session resumption: ~50-200ms (Claude API overhead)

### Error Handling

If session resumption fails:
- SDK falls back to creating a new session
- New session ID is saved automatically
- No manual intervention required

## Troubleshooting

### "Session ID not found"

Session IDs are only valid for a limited time (typically 24-48 hours). If you see this:
```bash
# Clear the stale session
python -m src.agent.main sessions --clear-type scanner
```

### "Session context seems wrong"

Sessions may accumulate context that's no longer relevant:
```bash
# Start fresh
python -m src.agent.main sessions --clear-type scanner
```

### "Different operation types sharing context"

Verify operation_type is set correctly in AgentWrapper initialization.
Each type should have its own independent session.

## Future Enhancements

Potential improvements:
- Session forking via CLI
- Session export/import for backup
- Session branching for A/B testing different strategies
- Session analytics (context length, tool usage patterns)
- Automatic session rotation after N runs
