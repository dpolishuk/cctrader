# Daily Session Mode - Integration Test Report

## Test Overview

Manual integration testing checklist for daily session mode functionality (Tasks 4-6).

## Test Environment

- **Working Directory**: `/home/deepol/work/cctrader`
- **Database**: `trading_data.db`
- **Command**: `python -m src.agent.main scan-movers`

## Test Cases

### Test 1: Daily Mode Creates Single Session

**Purpose**: Verify that --daily flag creates a single session with daily ID format.

**Steps**:
1. Clear any existing scanner sessions:
   ```bash
   python -m src.agent.main sessions --clear-type scanner
   ```

2. Start scanner in daily mode:
   ```bash
   python -m src.agent.main scan-movers --daily --interval 60
   ```

3. Let it run through 2-3 scan cycles (wait ~3-5 minutes)

4. Check database for session ID:
   ```bash
   sqlite3 trading_data.db "SELECT operation_type, session_id, created_at FROM agent_sessions WHERE operation_type='scanner';"
   ```

**Expected Results**:
- ✓ Console shows: "Daily mode enabled - maintaining single session per day"
- ✓ First symbol analysis creates session ID: `scanner-2025-11-21` (or current date)
- ✓ Subsequent symbols show: "Reusing persistent client (session: scanner-2025-11-21)"
- ✓ Database shows single scanner session with daily ID format
- ✓ All analyses appear in same conversation thread

**Status**: [ ] PASS / [ ] FAIL

**Notes**:
```
(Record observations here)
```

---

### Test 2: Session Persistence Across Restarts

**Purpose**: Verify that restarting scanner on same day resumes the session.

**Steps**:
1. With scanner running from Test 1, stop it (Ctrl+C)

2. Verify session is saved:
   ```bash
   sqlite3 trading_data.db "SELECT operation_type, session_id FROM agent_sessions WHERE operation_type='scanner';"
   ```

3. Restart scanner immediately (same day):
   ```bash
   python -m src.agent.main scan-movers --daily --interval 60
   ```

4. Observe startup logs

**Expected Results**:
- ✓ Console shows: "Resuming scanner session: scanner-2025-11-21"
- ✓ Scanner continues in same conversation thread
- ✓ No new session created in database
- ✓ Cleanup is called on stop (check logs for "Persistent client cleaned up")

**Status**: [ ] PASS / [ ] FAIL

**Notes**:
```
(Record observations here)
```

---

### Test 3: Regular Mode Still Works

**Purpose**: Verify that scanner without --daily flag works as before.

**Steps**:
1. Stop any running scanner

2. Clear scanner session:
   ```bash
   python -m src.agent.main sessions --clear-type scanner
   ```

3. Run scanner WITHOUT --daily flag:
   ```bash
   python -m src.agent.main scan-movers --interval 60
   ```

4. Let it analyze 2-3 symbols

**Expected Results**:
- ✓ No "Daily mode enabled" message in console
- ✓ Each symbol creates separate session (check logs)
- ✓ No "Reusing persistent client" messages
- ✓ Scanner functions normally

**Status**: [ ] PASS / [ ] FAIL

**Notes**:
```
(Record observations here)
```

---

### Test 4: Daily Session Expiry on New Day

**Purpose**: Verify that old daily sessions are not resumed on new day.

**Steps**:
1. Manually update session timestamp to simulate old session:
   ```bash
   sqlite3 trading_data.db "UPDATE agent_sessions SET session_id='scanner-2025-11-20', created_at='2025-11-20T10:00:00Z' WHERE operation_type='scanner';"
   ```

2. Start scanner in daily mode:
   ```bash
   python -m src.agent.main scan-movers --daily --interval 60
   ```

**Expected Results**:
- ✓ Scanner creates new session with today's date
- ✓ Old session is not resumed (logs show "starting new scanner session")
- ✓ New session ID matches current date format

**Status**: [ ] PASS / [ ] FAIL

**Notes**:
```
(Record observations here)
```

---

### Test 5: Cleanup on Scanner Stop

**Purpose**: Verify that persistent client is properly cleaned up on stop.

**Steps**:
1. Start scanner in daily mode:
   ```bash
   python -m src.agent.main scan-movers --daily --interval 60
   ```

2. Wait for at least one analysis to complete

3. Stop scanner with Ctrl+C

4. Check logs for cleanup message

**Expected Results**:
- ✓ Logs show: "Stopping scanner..."
- ✓ Logs show: "Persistent client cleaned up" (if cleanup method exists)
- ✓ No error messages or exceptions
- ✓ Session is saved to database

**Status**: [ ] PASS / [ ] FAIL

**Notes**:
```
(Record observations here)
```

---

### Test 6: Error Handling

**Purpose**: Verify graceful error handling in daily mode.

**Steps**:
1. Start scanner in daily mode with very short interval:
   ```bash
   python -m src.agent.main scan-movers --daily --interval 10
   ```

2. Observe behavior if no movers are found

3. Check logs for any errors or exceptions

**Expected Results**:
- ✓ Scanner handles no movers gracefully
- ✓ Persistent client remains stable across cycles
- ✓ No crashes or exceptions
- ✓ Session remains valid

**Status**: [ ] PASS / [ ] FAIL

**Notes**:
```
(Record observations here)
```

---

## Summary

**Total Tests**: 6
**Passed**: ___ / 6
**Failed**: ___ / 6

**Overall Status**: [ ] ALL TESTS PASSED / [ ] SOME TESTS FAILED

## Issues Found

(Document any issues discovered during testing)

```
1.
2.
3.
```

## Recommendations

(Any improvements or follow-up work identified)

```
1.
2.
3.
```

## Sign-off

**Tested By**: _______________
**Date**: _______________
**Environment**: Linux 6.8.0-86-generic
**Git Commit**: 7ac6190
