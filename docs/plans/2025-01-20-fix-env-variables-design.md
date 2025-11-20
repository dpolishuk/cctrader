# Fix Environment Variables in Session Banner Design

**Date:** 2025-01-20
**Status:** Design Complete

## Problem Statement

The session banner displays incorrect API endpoint (`https://api.anthropic.com`) because:
- Config.py looks for `ANTHROPIC_API_URL` (doesn't exist in .env)
- The .env file uses `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN`
- Config.py is missing `ANTHROPIC_AUTH_TOKEN` field entirely

## Solution

Update configuration management and banner display to:
1. Read `ANTHROPIC_BASE_URL` from .env (rename from `ANTHROPIC_API_URL`)
2. Add `ANTHROPIC_AUTH_TOKEN` field to config
3. Update banner to display both base URL and masked auth token

## Configuration Changes

### File: `src/agent/config.py`

**Current (lines 36-37):**
```python
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_API_URL: str = os.getenv("ANTHROPIC_API_URL", "https://api.anthropic.com")
```

**Updated:**
```python
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_AUTH_TOKEN: str = os.getenv("ANTHROPIC_AUTH_TOKEN", "")
ANTHROPIC_BASE_URL: str = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
```

**Rationale:**
- Matches actual .env variable names
- Adds missing auth token field
- Keeps same default URL for backward compatibility
- No breaking changes to other code

## Banner Display Updates

### File: `src/agent/cli_banner.py`

**Changes to `SessionBanner.display()` method:**

Add `auth_token` parameter:
```python
@staticmethod
def display(
    model: str,
    api_endpoint: str,
    auth_token: Optional[str],  # NEW parameter
    token_tracking_enabled: bool,
    session_id: Optional[str],
    operation_type: str,
    session_status: str
):
```

Add auth token row with masking (after API Endpoint row):
```python
# Current API Endpoint row
table.add_row("API Endpoint:", api_endpoint)

# NEW: Add auth token row with masking
if auth_token:
    # Mask token: show first 8 and last 4 chars
    masked_token = f"{auth_token[:8]}...{auth_token[-4:]}"
    table.add_row("Auth Token:", masked_token)
else:
    table.add_row("Auth Token:", "[dim]Not configured[/dim]")
```

**Changes to `show_session_banner()` helper:**

Update to read and pass auth token:
```python
# Get configuration
api_endpoint = config.ANTHROPIC_BASE_URL  # Changed from ANTHROPIC_API_URL
auth_token = config.ANTHROPIC_AUTH_TOKEN   # NEW

# Pass to display
SessionBanner.display(
    model=model,
    api_endpoint=api_endpoint,
    auth_token=auth_token,  # NEW parameter
    token_tracking_enabled=token_tracking_enabled,
    session_id=session_id,
    operation_type=operation_type,
    session_status=session_status
)
```

## Security Consideration

Token masked as `deffa90c...LfzE` format:
- Shows first 8 characters
- Shows last 4 characters
- Hides middle portion with "..."
- Enough to verify correct token loaded
- Doesn't expose full token value in logs/screenshots

## Testing Strategy

### Unit Tests (`tests/test_cli_banner.py`)
1. Update existing tests to pass `auth_token` parameter
2. Add test for masked token display (verify masking format)
3. Add test for missing auth token (shows "Not configured")
4. Add test for short tokens (edge case: token < 12 chars)

### Integration Tests (`tests/test_main_banner_integration.py`)
1. Update mocked config to include `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN`
2. Verify banner displays both fields correctly

### Manual Validation
1. Run `scan-movers --help` to see banner with actual .env values
2. Verify displays: `https://api.z.ai/api/anthropic` and `deffa90c...LfzE`
3. Test with missing .env values (should show defaults)

## Expected Banner Output

```
╭─── Session Information ────────────────────────────╮
│ Model:          claude-sonnet-4-5                  │
│ API Endpoint:   https://api.z.ai/api/anthropic     │
│ Auth Token:     deffa90c...LfzE                    │
│ Token Tracking: ✓ Enabled (Session: abc123...)    │
│ Operation:      scanner                            │
│ Session Status: New session created                │
╰────────────────────────────────────────────────────╯
```

## Files to Modify

1. **UPDATE**: `src/agent/config.py` - Rename API_URL field, add AUTH_TOKEN field
2. **UPDATE**: `src/agent/cli_banner.py` - Add auth token parameter and display
3. **UPDATE**: `tests/test_cli_banner.py` - Add auth token test coverage
4. **UPDATE**: `tests/test_main_banner_integration.py` - Update mocked config

## Backward Compatibility

- Falls back to default URL if `ANTHROPIC_BASE_URL` not set
- Falls back to empty string if `ANTHROPIC_AUTH_TOKEN` not set
- No breaking changes to existing functionality
- Banner gracefully handles missing auth token
