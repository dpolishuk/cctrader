# Configurable Model Name Design

**Date:** 2025-01-20
**Status:** Design Complete

## Problem Statement

Model name is currently hardcoded as `"claude-sonnet-4-5"` in multiple places:
- In `main.py` when creating `ClaudeAgentOptions` (line 460)
- In `show_session_banner()` calls (lines 477 and other commands)
- Cannot change model without code modification

## Solution

Add `CLAUDE_MODEL` configuration parameter that:
1. Reads from environment variable with default `"glm-4.5"`
2. Is used in all commands (scanner, analyze, monitor, paper_monitor)
3. Automatically displays in session banner

## Configuration Changes

### File: `src/agent/config.py`

**Add after Agent Settings (after line 55):**

```python
# Agent Settings
MAX_TURNS: int = int(os.getenv("MAX_TURNS", "20"))
MAX_BUDGET_USD: float = float(os.getenv("MAX_BUDGET_USD", "1.0"))
ANALYSIS_INTERVAL: int = int(os.getenv("ANALYSIS_INTERVAL", "300"))
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "glm-4.5")  # NEW
```

**Rationale:**
- Logically belongs with Agent Settings
- Placed near MAX_TURNS and MAX_BUDGET_USD (other agent parameters)
- Simple string type like other URL/path parameters
- Default `"glm-4.5"` as specified

### File: `.env`

**Add after ANALYSIS_INTERVAL:**

```bash
MAX_TURNS=20
MAX_BUDGET_USD=1.0
ANALYSIS_INTERVAL=900
CLAUDE_MODEL=glm-4.5
```

### File: `.env.example`

**Add in same location:**

```bash
MAX_TURNS=20
MAX_BUDGET_USD=1.0
ANALYSIS_INTERVAL=300
CLAUDE_MODEL=glm-4.5
```

## Usage in Commands

### File: `src/agent/main.py`

Replace hardcoded `"claude-sonnet-4-5"` in 5 locations:

**1. scan_movers command (line 460):**
```python
# BEFORE:
agent_options = ClaudeAgentOptions(
    ...
    model="claude-sonnet-4-5",
    ...
)

# AFTER:
agent_options = ClaudeAgentOptions(
    ...
    model=config.CLAUDE_MODEL,
    ...
)
```

**2. scan_movers banner (line 477):**
```python
# BEFORE:
await show_session_banner(
    operation_type=SessionManager.SCANNER,
    model="claude-sonnet-4-5",
    session_manager=session_manager
)

# AFTER:
await show_session_banner(
    operation_type=SessionManager.SCANNER,
    model=config.CLAUDE_MODEL,
    session_manager=session_manager
)
```

**3-5. Similar changes for commands:**
- `analyze` (line ~75)
- `monitor` (line ~40)
- `paper_monitor` (line ~243)

All banner calls should use `model=config.CLAUDE_MODEL`.

**Import Note:** `config` is already imported in scan_movers (line 291), but need to add import in other commands.

## Testing Strategy

### Unit Tests (`tests/test_cli_banner.py`)
- Tests already accept `model` as parameter
- Can add test with custom model (optional)
- No mandatory changes required

### Integration Tests (`tests/test_main_banner_integration.py`)
- Tests use `ANY` for model parameter
- No changes required

### Manual Validation

1. **Verify config loads:**
   ```bash
   python -c "from src.agent.config import config; print(f'Model: {config.CLAUDE_MODEL}')"
   ```
   Expected: `Model: glm-4.5`

2. **Verify commands work:**
   - `scan-movers --help` - should work
   - Banner should show: `Model: glm-4.5`

3. **Test with custom model:**
   ```bash
   CLAUDE_MODEL=custom-model python -m src.agent.main scan-movers --help
   ```
   Expected: Banner shows `Model: custom-model`

4. **Run test suite:**
   ```bash
   pytest tests/ -q
   ```
   Expected: All tests pass

## Expected Banner Output

```
╭─── Session Information ────────────────────────────╮
│ Model:          glm-4.5                            │
│ API Endpoint:   https://api.z.ai/api/anthropic     │
│ Auth Token:     deffa90c...LfzE                    │
│ Token Tracking: ✓ Enabled (Session: abc123...)    │
│ Operation:      scanner                            │
│ Session Status: New session created                │
╰────────────────────────────────────────────────────╯
```

## Files to Modify

1. **UPDATE**: `src/agent/config.py` - Add CLAUDE_MODEL field
2. **UPDATE**: `.env` - Add CLAUDE_MODEL=glm-4.5
3. **UPDATE**: `.env.example` - Add CLAUDE_MODEL=glm-4.5
4. **UPDATE**: `src/agent/main.py` - Replace hardcoded model in 5 places

## Backward Compatibility

- Fully backward compatible
- If CLAUDE_MODEL not set, uses default "glm-4.5"
- No breaking changes to existing functionality
- Existing tests continue to pass
