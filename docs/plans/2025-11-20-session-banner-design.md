# Session Information Banner Design

**Date:** 2025-11-20
**Status:** Design Complete

## Overview

Add a CLI banner that displays session information (model, API endpoint, token tracking status, session info) at the start of each command, after database initialization but before main operations begin.

## Architecture

### Component Structure
- **New module**: `src/agent/cli_banner.py`
- **SessionBanner class**: Uses Rich library to create formatted panels
- **Helper function**: `show_session_banner()` to gather and display info
- **Integration**: Called from main.py commands after DB init, before operations

### Information Sources
- **Model name**: From agent options (e.g., "claude-sonnet-4-5")
- **Anthropic API URL**: From `ANTHROPIC_API_URL` env var (default: "https://api.anthropic.com")
- **Token tracking status**: From `config.TOKEN_TRACKING_ENABLED`
- **Session info**: From `SessionManager` (existing/new session)

### Integration Points
Commands that show banner:
- `scan_movers`
- `paper_monitor`
- `monitor`
- `analyze`

Timing: After `init_db()` but before agent initialization

## Banner Layout

```
╭─── Session Information ────────────────────────────╮
│ Model:          claude-sonnet-4-5                  │
│ API Endpoint:   https://api.anthropic.com          │
│ Token Tracking: ✓ Enabled (Session: abc123...)    │
│ Operation:      scanner                            │
│ Session Status: Resuming existing / New session    │
╰────────────────────────────────────────────────────╯
```

### Display Details
- **Model**: Exact model being used
- **API Endpoint**: Base URL (identifies custom endpoints)
- **Token Tracking**: Status with session ID (truncated)
- **Operation**: Operation type (scanner, analysis, monitor, paper_trading)
- **Session Status**: "Resuming [session_id]" or "New session created"

### Color Scheme
- Panel border: cyan
- Labels: dim/gray
- Values: white/bright
- Status indicators: green (✓), yellow (⚠), red (✗)

## Implementation

### SessionBanner Class API

```python
class SessionBanner:
    @staticmethod
    def display(
        model: str,
        api_endpoint: str,
        token_tracking_enabled: bool,
        session_id: Optional[str],
        operation_type: str,
        session_status: str  # "resumed" or "new"
    ):
        """Display session information banner."""
```

### Helper Function

```python
async def show_session_banner(
    operation_type: str,
    model: str = "claude-sonnet-4-5",
    session_manager: Optional[SessionManager] = None
):
    """Gather session info and display banner."""
```

### Integration Example (scan_movers)

1. After `init_paper_trading_db()` and `create_movers_tables()`
2. Before portfolio initialization
3. Call: `await show_session_banner(operation_type="scanner", model="claude-sonnet-4-5", session_manager=session_manager)`

### Configuration

Add to `src/agent/config.py`:
```python
ANTHROPIC_API_URL: str = os.getenv("ANTHROPIC_API_URL", "https://api.anthropic.com")
```

### Error Handling
- If session_manager is None: Show "N/A" for session info
- If API URL not in env: Use default
- Banner failures: Log warning, don't crash command

## Testing

### Manual Testing
1. Test each command type (scan_movers, analyze, monitor, paper_monitor)
2. Verify timing (after DB init, before agent start)
3. Test with token tracking enabled/disabled
4. Test new session vs. resuming existing session
5. Test with custom ANTHROPIC_API_URL

### Edge Cases
- **No session manager**: Show "Session tracking: Not available"
- **Session manager init fails**: Catch exception, show warning
- **Long session IDs**: Truncate to 8 chars + "..."
- **Missing env vars**: Use defaults
- **Narrow terminals**: Rich Panel auto-wraps

## Files to Modify

1. **NEW**: `src/agent/cli_banner.py` - SessionBanner class and helper
2. **UPDATE**: `src/agent/config.py` - Add ANTHROPIC_API_URL field
3. **UPDATE**: `src/agent/main.py` - Add banner calls to commands

## Backward Compatibility

- No breaking changes - purely additive
- Commands work if banner fails
- No API or schema changes
