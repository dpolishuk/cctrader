# Design: Reduce Log Noise from StreamEvent Messages

**Date:** 2025-11-20
**Status:** Approved

## Problem

The scanner logs `INFO - 📦 Non-assistant message: StreamEvent` repeatedly during Claude Agent SDK message processing. These are internal SDK events (StreamEvent, ResultMessage, etc.) that clutter the log output during normal operation.

## Solution

Change the logging level for non-assistant message types from INFO to DEBUG. This keeps the information available for troubleshooting (when running with `--verbose` or setting log level to DEBUG) but removes it from normal output.

## Impact

- **Normal operation:** Cleaner logs showing only meaningful events (tool calls, reasoning, results)
- **Debug mode:** Full visibility into all message types including StreamEvent
- **No functionality changes:** Purely logging level adjustment

## Implementation

### File to Modify

`src/agent/scanner/agent_wrapper.py` - the `_process_messages` method around line 248-252

### Change Required

```python
# Current (line 250):
logger.info(f"📦 Non-assistant message: {message_type}")

# New:
logger.debug(f"📦 Non-assistant message: {message_type}")
```

### Logging Level Breakdown

**What Stays at INFO Level:**
- Agent reasoning text (line 172-173)
- Tool calls with parameters (line 190-193)
- Tool results (line 201-208)
- Tool call summary (line 256-259)
- Duplicate tool warnings (line 227)

**What Moves to DEBUG Level:**
- Non-assistant message types (StreamEvent, ResultMessage, etc.)
- The detailed `__dict__` content of those messages (already at DEBUG on line 252)

## Testing

- **Normal mode:** Run scanner - should not see StreamEvent messages
- **Debug mode:** Run with debug logging enabled - should see all messages including StreamEvent

## Benefits

1. **Cleaner production logs:** Easier to scan for important events
2. **Preserved debugging capability:** Full detail available when needed
3. **Minimal change:** Single line modification, low risk
4. **Follows logging best practices:** Use DEBUG for internal events, INFO for user-relevant events
