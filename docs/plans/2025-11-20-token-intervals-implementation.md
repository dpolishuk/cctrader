# Token Interval Tracking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 5-minute interval tracking to show token consumption patterns during scanning sessions with real-time updates, end-of-session summaries, and historical query capabilities.

**Architecture:** Extend existing TokenTracker with interval tracking state (current/completed intervals). Add display logic for real-time updates and end-of-session tables using Rich. Add new CLI command to query historical intervals from database.

**Tech Stack:** Python 3.12, aiosqlite, Rich (console formatting), pytest

---

## Task 1: Add Interval Configuration

**Files:**
- Modify: `src/agent/config.py:30-40`

**Step 1: Add TOKEN_INTERVAL_MINUTES config**

Add after line 34 (after TOKEN_TRACKING_ENABLED):

```python
# Token interval tracking
TOKEN_INTERVAL_MINUTES: int = int(os.getenv("TOKEN_INTERVAL_MINUTES", "5"))
```

**Step 2: Verify import**

Run: `python -c "from src.agent.config import config; print(config.TOKEN_INTERVAL_MINUTES)"`
Expected: `5`

**Step 3: Commit**

```bash
git add src/agent/config.py
git commit -m "feat: add TOKEN_INTERVAL_MINUTES config for interval tracking"
```

---

## Task 2: Add Interval State to TokenTracker

**Files:**
- Modify: `src/agent/tracking/token_tracker.py:34-36`
- Test: `tests/test_token_tracker.py`

**Step 1: Write failing test for interval initialization**

Add to `tests/test_token_tracker.py` at end:

```python
@pytest.mark.asyncio
async def test_interval_tracking_initialization(tracker):
    """Test that interval tracking state initializes correctly."""
    assert hasattr(tracker, 'interval_start_time')
    assert hasattr(tracker, 'interval_number')
    assert hasattr(tracker, 'current_interval')
    assert hasattr(tracker, 'completed_intervals')

    assert tracker.interval_number == 0
    assert tracker.current_interval == {
        'tokens_input': 0,
        'tokens_output': 0,
        'cost': 0.0,
        'requests': 0
    }
    assert tracker.completed_intervals == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_token_tracker.py::test_interval_tracking_initialization -v`
Expected: FAIL with "AttributeError: 'TokenTracker' object has no attribute 'interval_start_time'"

**Step 3: Add interval state to __init__**

In `src/agent/tracking/token_tracker.py`, modify `__init__` method after line 35 (after `self.is_active = False`):

```python
        # Interval tracking state
        self.interval_start_time: Optional[float] = None
        self.interval_number: int = 0
        self.current_interval: Dict[str, Any] = {
            'tokens_input': 0,
            'tokens_output': 0,
            'cost': 0.0,
            'requests': 0
        }
        self.completed_intervals: List[Dict[str, Any]] = []
        self.INTERVAL_DURATION = config.TOKEN_INTERVAL_MINUTES * 60  # Convert to seconds
```

Add imports at top:

```python
from typing import Any, Dict, Optional, List
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_token_tracker.py::test_interval_tracking_initialization -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/agent/tracking/token_tracker.py tests/test_token_tracker.py
git commit -m "feat: add interval tracking state to TokenTracker"
```

---

## Task 3: Initialize Interval Tracking on Session Start

**Files:**
- Modify: `src/agent/tracking/token_tracker.py:45-47`
- Test: `tests/test_token_tracker.py`

**Step 1: Write failing test**

Add to `tests/test_token_tracker.py`:

```python
@pytest.mark.asyncio
async def test_interval_starts_on_session_start(tracker):
    """Test that interval tracking starts when session starts."""
    import time

    before = time.time()
    await tracker.start_session()
    after = time.time()

    assert tracker.interval_start_time is not None
    assert before <= tracker.interval_start_time <= after
    assert tracker.interval_number == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_token_tracker.py::test_interval_starts_on_session_start -v`
Expected: FAIL with "AssertionError: assert None is not None"

**Step 3: Modify start_session to initialize interval**

In `src/agent/tracking/token_tracker.py`, modify `start_session` method after line 46 (after `self.is_active = True`):

```python
        # Initialize first interval
        self.interval_start_time = time.time()
        self.interval_number = 1
```

Add import at top:

```python
import time
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_token_tracker.py::test_interval_starts_on_session_start -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/agent/tracking/token_tracker.py tests/test_token_tracker.py
git commit -m "feat: initialize interval tracking on session start"
```

---

## Task 4: Add Interval Check Logic

**Files:**
- Modify: `src/agent/tracking/token_tracker.py:90-110`
- Test: `tests/test_token_tracker.py`

**Step 1: Write failing test for interval accumulation**

Add to `tests/test_token_tracker.py`:

```python
@pytest.mark.asyncio
async def test_interval_accumulates_usage(tracker):
    """Test that token usage accumulates in current interval."""
    await tracker.start_session()

    # Simulate usage
    mock_result = Mock()
    mock_result.usage = {'input_tokens': 100, 'output_tokens': 50}
    mock_result.model = "claude-sonnet-4-5"

    await tracker.record_usage(result=mock_result, operation_type="test")

    assert tracker.current_interval['tokens_input'] == 100
    assert tracker.current_interval['tokens_output'] == 50
    assert tracker.current_interval['requests'] == 1
    assert tracker.current_interval['cost'] > 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_token_tracker.py::test_interval_accumulates_usage -v`
Expected: FAIL with "AssertionError: assert 0 == 100"

**Step 3: Add _accumulate_interval method**

Add new method to TokenTracker class after `record_usage`:

```python
    def _accumulate_interval(self, tokens_input: int, tokens_output: int, cost_usd: float):
        """
        Accumulate token usage to current interval.

        Args:
            tokens_input: Input tokens
            tokens_output: Output tokens
            cost_usd: Cost in USD
        """
        self.current_interval['tokens_input'] += tokens_input
        self.current_interval['tokens_output'] += tokens_output
        self.current_interval['cost'] += cost_usd
        self.current_interval['requests'] += 1
```

**Step 4: Call _accumulate_interval from record_usage**

In `record_usage` method, after the `await self.db.record_token_usage(...)` call (around line 90), add:

```python
        # Accumulate to current interval
        self._accumulate_interval(tokens_input, tokens_output, cost_usd)
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_token_tracker.py::test_interval_accumulates_usage -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/agent/tracking/token_tracker.py tests/test_token_tracker.py
git commit -m "feat: accumulate token usage to current interval"
```

---

## Task 5: Add Interval Completion Logic

**Files:**
- Modify: `src/agent/tracking/token_tracker.py:110-150`
- Test: `tests/test_token_tracker.py`

**Step 1: Write failing test for interval completion**

Add to `tests/test_token_tracker.py`:

```python
@pytest.mark.asyncio
async def test_interval_completes_after_duration(tracker):
    """Test that interval completes and resets after duration."""
    import time

    await tracker.start_session()

    # Simulate usage
    mock_result = Mock()
    mock_result.usage = {'input_tokens': 100, 'output_tokens': 50}
    mock_result.model = "claude-sonnet-4-5"

    await tracker.record_usage(result=mock_result, operation_type="test")

    # Simulate time passing (5+ minutes)
    tracker.interval_start_time = time.time() - 301  # 5 min 1 sec ago

    # Record more usage - should trigger interval completion
    await tracker.record_usage(result=mock_result, operation_type="test")

    # Should have completed one interval
    assert len(tracker.completed_intervals) == 1
    assert tracker.completed_intervals[0]['interval_number'] == 1
    assert tracker.completed_intervals[0]['tokens_input'] == 100
    assert tracker.completed_intervals[0]['tokens_output'] == 50

    # Should have started new interval
    assert tracker.interval_number == 2
    assert tracker.current_interval['tokens_input'] == 100
    assert tracker.current_interval['requests'] == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_token_tracker.py::test_interval_completes_after_duration -v`
Expected: FAIL with "AssertionError: assert [] == 1"

**Step 3: Add _check_and_complete_interval method**

Add new method to TokenTracker class:

```python
    def _check_and_complete_interval(self):
        """
        Check if interval duration elapsed and complete it if so.

        Returns:
            bool: True if interval was completed, False otherwise
        """
        if not self.interval_start_time:
            return False

        elapsed = time.time() - self.interval_start_time

        if elapsed >= self.INTERVAL_DURATION:
            # Complete current interval
            interval_data = {
                'interval_number': self.interval_number,
                'duration_seconds': elapsed,
                'tokens_input': self.current_interval['tokens_input'],
                'tokens_output': self.current_interval['tokens_output'],
                'tokens_total': self.current_interval['tokens_input'] + self.current_interval['tokens_output'],
                'cost': self.current_interval['cost'],
                'requests': self.current_interval['requests']
            }

            self.completed_intervals.append(interval_data)

            # Log interval summary
            logger.info(
                f"[+{self.interval_number * config.TOKEN_INTERVAL_MINUTES}min] "
                f"Interval {self.interval_number}: "
                f"{interval_data['tokens_total']:,} tokens "
                f"({interval_data['tokens_input']:,} in, {interval_data['tokens_output']:,} out) | "
                f"Cost: ${interval_data['cost']:.4f} | "
                f"{interval_data['requests']} requests"
            )

            # Reset for next interval
            self.interval_number += 1
            self.interval_start_time = time.time()
            self.current_interval = {
                'tokens_input': 0,
                'tokens_output': 0,
                'cost': 0.0,
                'requests': 0
            }

            return True

        return False
```

Add import at top:

```python
import logging

logger = logging.getLogger(__name__)
```

**Step 4: Call _check_and_complete_interval from record_usage**

In `record_usage` method, before calling `_accumulate_interval`, add:

```python
        # Check if interval should complete
        self._check_and_complete_interval()
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_token_tracker.py::test_interval_completes_after_duration -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/agent/tracking/token_tracker.py tests/test_token_tracker.py
git commit -m "feat: add interval completion and rotation logic"
```

---

## Task 6: Add End-of-Session Interval Summary

**Files:**
- Modify: `src/agent/tracking/token_tracker.py:100-120`
- Create: `src/agent/tracking/interval_display.py`
- Test: `tests/test_interval_display.py`

**Step 1: Create interval display utility**

Create `src/agent/tracking/interval_display.py`:

```python
"""Display utilities for token interval summaries."""
from typing import List, Dict, Any
from rich.console import Console
from rich.table import Table


def format_duration(seconds: float) -> str:
    """Format duration in seconds to MM:SS format."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


def display_interval_summary(intervals: List[Dict[str, Any]], current_interval: Dict[str, Any],
                             current_duration: float) -> None:
    """
    Display summary table of token intervals.

    Args:
        intervals: List of completed intervals
        current_interval: Current (possibly partial) interval data
        current_duration: Duration of current interval in seconds
    """
    if not intervals and current_interval['requests'] == 0:
        return  # No data to display

    console = Console()

    # Create table
    table = Table(title="Token Usage by 5-Minute Intervals")
    table.add_column("Interval", style="cyan")
    table.add_column("Duration", style="blue")
    table.add_column("Tokens (in)", justify="right", style="green")
    table.add_column("Tokens (out)", justify="right", style="green")
    table.add_column("Total", justify="right", style="bold green")
    table.add_column("Cost", justify="right", style="yellow")

    # Add completed intervals
    total_duration = 0.0
    total_input = 0
    total_output = 0
    total_cost = 0.0

    for interval in intervals:
        table.add_row(
            str(interval['interval_number']),
            format_duration(interval['duration_seconds']),
            f"{interval['tokens_input']:,}",
            f"{interval['tokens_output']:,}",
            f"{interval['tokens_total']:,}",
            f"${interval['cost']:.4f}"
        )
        total_duration += interval['duration_seconds']
        total_input += interval['tokens_input']
        total_output += interval['tokens_output']
        total_cost += interval['cost']

    # Add current (partial) interval if it has usage
    if current_interval['requests'] > 0:
        interval_num = len(intervals) + 1
        tokens_total = current_interval['tokens_input'] + current_interval['tokens_output']
        table.add_row(
            str(interval_num),
            format_duration(current_duration),
            f"{current_interval['tokens_input']:,}",
            f"{current_interval['tokens_output']:,}",
            f"{tokens_total:,}",
            f"${current_interval['cost']:.4f}"
        )
        total_duration += current_duration
        total_input += current_interval['tokens_input']
        total_output += current_interval['tokens_output']
        total_cost += current_interval['cost']

    # Add total row
    total_tokens = total_input + total_output
    table.add_section()
    table.add_row(
        "TOTAL",
        format_duration(total_duration),
        f"{total_input:,}",
        f"{total_output:,}",
        f"{total_tokens:,}",
        f"${total_cost:.4f}",
        style="bold"
    )

    console.print(table)
```

**Step 2: Write test for display utility**

Create `tests/test_interval_display.py`:

```python
"""Tests for interval display utilities."""
from src.agent.tracking.interval_display import format_duration


def test_format_duration():
    """Test duration formatting."""
    assert format_duration(0) == "0:00"
    assert format_duration(59) == "0:59"
    assert format_duration(60) == "1:00"
    assert format_duration(300) == "5:00"
    assert format_duration(301) == "5:01"
    assert format_duration(3661) == "61:01"
```

**Step 3: Run test**

Run: `pytest tests/test_interval_display.py -v`
Expected: PASS

**Step 4: Modify end_session to display summary**

In `src/agent/tracking/token_tracker.py`, modify `end_session` method, before the `await self.db.end_session(...)` call:

```python
        # Capture final partial interval and display summary
        if self.interval_start_time and (self.completed_intervals or self.current_interval['requests'] > 0):
            from src.agent.tracking.interval_display import display_interval_summary

            current_duration = time.time() - self.interval_start_time
            display_interval_summary(self.completed_intervals, self.current_interval, current_duration)
```

**Step 5: Commit**

```bash
git add src/agent/tracking/interval_display.py src/agent/tracking/token_tracker.py tests/test_interval_display.py
git commit -m "feat: add end-of-session interval summary display"
```

---

## Task 7: Add CLI Command for Historical Intervals

**Files:**
- Modify: `src/agent/main.py:650-700`
- Modify: `src/agent/database/token_operations.py:200-250`

**Step 1: Add method to query intervals from database**

Add to `src/agent/database/token_operations.py` at end of TokenDatabase class:

```python
    async def get_session_intervals(self, session_id: str, interval_minutes: int = 5) -> List[Dict[str, Any]]:
        """
        Get token usage broken down by intervals for a session.

        Args:
            session_id: Session ID to query
            interval_minutes: Interval duration in minutes

        Returns:
            List of interval data dicts
        """
        interval_seconds = interval_minutes * 60

        async with aiosqlite.connect(self.db_path) as db:
            # Get session start time
            async with db.execute(
                "SELECT start_time FROM token_sessions WHERE session_id = ?",
                (session_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return []

                start_time = row[0]

            # Query usage grouped by intervals
            async with db.execute(
                """
                SELECT
                    CAST((strftime('%s', timestamp) - strftime('%s', ?)) / ? AS INTEGER) as interval_num,
                    SUM(tokens_input) as tokens_input,
                    SUM(tokens_output) as tokens_output,
                    SUM(cost_usd) as cost,
                    COUNT(*) as requests,
                    MIN(timestamp) as interval_start,
                    MAX(timestamp) as interval_end
                FROM token_usage
                WHERE session_id = ?
                GROUP BY interval_num
                ORDER BY interval_num
                """,
                (start_time, interval_seconds, session_id)
            ) as cursor:
                intervals = []
                async for row in cursor:
                    intervals.append({
                        'interval_number': row[0] + 1,  # 1-indexed for display
                        'tokens_input': row[1],
                        'tokens_output': row[2],
                        'tokens_total': row[1] + row[2],
                        'cost': row[3],
                        'requests': row[4],
                        'start_time': row[5],
                        'end_time': row[6]
                    })

                return intervals
```

**Step 2: Add CLI command to main.py**

Add new command after the `sessions` command (around line 650):

```python
@cli.command()
@click.option('--session-id', default=None, help='Show intervals for specific session')
def token_intervals(session_id):
    """View token usage by 5-minute intervals."""
    async def run():
        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))
        from src.agent.database.token_operations import TokenDatabase
        from src.agent.tracking.interval_display import display_interval_summary
        from src.agent.config import config

        db = TokenDatabase(db_path)

        if session_id:
            # Show intervals for specific session
            intervals = await db.get_session_intervals(session_id, config.TOKEN_INTERVAL_MINUTES)

            if not intervals:
                console.print(f"[yellow]Session {session_id} not found or has no data[/yellow]")
                return

            # Convert to display format
            completed = []
            for interval in intervals:
                # Calculate duration from start/end times
                from datetime import datetime
                start = datetime.fromisoformat(interval['start_time'])
                end = datetime.fromisoformat(interval['end_time'])
                duration = (end - start).total_seconds()

                completed.append({
                    'interval_number': interval['interval_number'],
                    'duration_seconds': duration,
                    'tokens_input': interval['tokens_input'],
                    'tokens_output': interval['tokens_output'],
                    'tokens_total': interval['tokens_total'],
                    'cost': interval['cost']
                })

            display_interval_summary(completed, {'tokens_input': 0, 'tokens_output': 0, 'cost': 0.0, 'requests': 0}, 0)
        else:
            # List recent sessions
            sessions = await db.get_recent_sessions(limit=10)

            if not sessions:
                console.print("[yellow]No token tracking sessions found[/yellow]")
                return

            from rich.table import Table
            table = Table(title="Recent Token Tracking Sessions")
            table.add_column("Session ID", style="cyan")
            table.add_column("Started", style="blue")
            table.add_column("Duration", style="green")
            table.add_column("Tokens", justify="right", style="green")
            table.add_column("Cost", justify="right", style="yellow")

            for session in sessions:
                duration = ""
                if session.get('end_time'):
                    from datetime import datetime
                    start = datetime.fromisoformat(session['start_time'])
                    end = datetime.fromisoformat(session['end_time'])
                    mins = int((end - start).total_seconds() / 60)
                    duration = f"{mins}m"

                tokens = session.get('total_tokens_input', 0) + session.get('total_tokens_output', 0)

                table.add_row(
                    session['session_id'][:16] + '...',
                    session['start_time'][:19],
                    duration,
                    f"{tokens:,}",
                    f"${session.get('total_cost_usd', 0):.4f}"
                )

            console.print(table)
            console.print("\n[dim]Use --session-id to see 5-minute interval breakdown[/dim]")

    asyncio.run(run())
```

**Step 3: Add get_recent_sessions method to TokenDatabase**

Add to TokenDatabase class:

```python
    async def get_recent_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent token tracking sessions."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT session_id, start_time, end_time, total_tokens_input,
                       total_tokens_output, total_cost_usd
                FROM token_sessions
                ORDER BY start_time DESC
                LIMIT ?
                """,
                (limit,)
            ) as cursor:
                sessions = []
                async for row in cursor:
                    sessions.append({
                        'session_id': row[0],
                        'start_time': row[1],
                        'end_time': row[2],
                        'total_tokens_input': row[3],
                        'total_tokens_output': row[4],
                        'total_cost_usd': row[5]
                    })
                return sessions
```

**Step 4: Test CLI command**

Run: `python -m src.agent.main token-intervals --help`
Expected: Shows help text

**Step 5: Commit**

```bash
git add src/agent/main.py src/agent/database/token_operations.py
git commit -m "feat: add token-intervals CLI command for historical analysis"
```

---

## Task 8: Integration Testing

**Files:**
- Create: `tests/test_interval_integration.py`

**Step 1: Write integration test**

Create `tests/test_interval_integration.py`:

```python
"""Integration tests for interval tracking."""
import pytest
import pytest_asyncio
import tempfile
import os
import time
from pathlib import Path
from unittest.mock import Mock
from src.agent.tracking.token_tracker import TokenTracker
from src.agent.database.token_schema import create_token_tracking_tables
import aiosqlite


@pytest_asyncio.fixture
async def integration_tracker():
    """Set up tracker for integration testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    async with aiosqlite.connect(db_path) as db:
        await create_token_tracking_tables(db)
        await db.commit()

    tracker = TokenTracker(db_path=db_path, operation_mode="test")
    yield tracker

    os.unlink(db_path)


@pytest.mark.asyncio
async def test_full_interval_workflow(integration_tracker):
    """Test complete interval tracking workflow."""
    tracker = integration_tracker

    # Start session
    await tracker.start_session()
    assert tracker.interval_number == 1

    # Simulate usage in first interval
    for i in range(3):
        mock_result = Mock()
        mock_result.usage = {'input_tokens': 100, 'output_tokens': 50}
        mock_result.model = "claude-sonnet-4-5"
        await tracker.record_usage(result=mock_result, operation_type="test")

    # Verify accumulation
    assert tracker.current_interval['requests'] == 3
    assert tracker.current_interval['tokens_input'] == 300

    # Simulate time passing to trigger interval completion
    tracker.interval_start_time = time.time() - 301

    # Record usage to trigger check
    mock_result = Mock()
    mock_result.usage = {'input_tokens': 200, 'output_tokens': 100}
    mock_result.model = "claude-sonnet-4-5"
    await tracker.record_usage(result=mock_result, operation_type="test")

    # Verify interval completed
    assert len(tracker.completed_intervals) == 1
    assert tracker.completed_intervals[0]['tokens_input'] == 300
    assert tracker.completed_intervals[0]['tokens_output'] == 150
    assert tracker.completed_intervals[0]['requests'] == 3

    # Verify new interval started
    assert tracker.interval_number == 2
    assert tracker.current_interval['tokens_input'] == 200
    assert tracker.current_interval['requests'] == 1

    # End session (should capture partial interval)
    await tracker.end_session()

    # Session should be ended
    assert not tracker.is_active


@pytest.mark.asyncio
async def test_short_session_intervals(integration_tracker):
    """Test session shorter than one interval."""
    tracker = integration_tracker

    await tracker.start_session()

    # Record some usage
    mock_result = Mock()
    mock_result.usage = {'input_tokens': 100, 'output_tokens': 50}
    mock_result.model = "claude-sonnet-4-5"
    await tracker.record_usage(result=mock_result, operation_type="test")

    # End immediately (no completed intervals)
    await tracker.end_session()

    assert len(tracker.completed_intervals) == 0
    # But current interval should have the data
    assert tracker.current_interval['requests'] == 1
```

**Step 2: Run integration tests**

Run: `pytest tests/test_interval_integration.py -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add tests/test_interval_integration.py
git commit -m "test: add integration tests for interval tracking"
```

---

## Task 9: Update Documentation

**Files:**
- Create: `docs/TOKEN_INTERVAL_TRACKING.md`

**Step 1: Create user documentation**

Create `docs/TOKEN_INTERVAL_TRACKING.md`:

```markdown
# Token Interval Tracking

## Overview

Track Claude API token consumption in 5-minute intervals during scanning sessions to understand usage patterns and costs.

## Features

1. **Real-Time Updates**: See token usage every 5 minutes while scanner runs
2. **End-of-Session Summary**: Table showing all intervals when session completes
3. **Historical Analysis**: Query past sessions to review their interval breakdowns

## Configuration

Set interval duration (default: 5 minutes):

\```bash
export TOKEN_INTERVAL_MINUTES=5
\```

## Real-Time Display

During scanner operation, you'll see periodic updates:

\```
[+5min] Interval 1: 1,234 tokens (890 in, 344 out) | Cost: $0.012 | 3 requests
[+10min] Interval 2: 2,156 tokens (1,502 in, 654 out) | Cost: $0.021 | 5 requests
\```

## End-of-Session Summary

When the scanner stops, you'll see a complete breakdown:

\```
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
\```

## Historical Analysis

### List Recent Sessions

\```bash
python -m src.agent.main token-intervals
\```

Shows recent sessions with totals:

\```
Recent Token Tracking Sessions
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Session ID          Started              Duration  Tokens   Cost
sess_abc123...      2025-11-20 10:30:15  13m      4,377    $0.042
sess_def456...      2025-11-20 09:15:22  8m       2,891    $0.028
\```

### View Session Intervals

\```bash
python -m src.agent.main token-intervals --session-id sess_abc123...
\```

Shows 5-minute interval breakdown for that session.

## Use Cases

- **Cost Monitoring**: Track spending in real-time
- **Performance Analysis**: Identify which periods have high token usage
- **Optimization**: Compare intervals to find opportunities to reduce costs
- **Debugging**: Correlate token spikes with specific market events or symbols

## Technical Details

- Intervals are relative to session start time
- Database queries use existing `token_usage` table with SQL aggregation
- No additional database tables required
- Minimal performance overhead
\```

**Step 2: Commit documentation**

\```bash
git add docs/TOKEN_INTERVAL_TRACKING.md
git commit -m "docs: add user documentation for interval tracking"
\```

---

## Task 10: Run Full Test Suite

**Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS (including new interval tracking tests)

**Step 2: Verify CLI commands work**

Run: `python -m src.agent.main --help | grep token-intervals`
Expected: Shows token-intervals command

**Step 3: Final commit**

\```bash
git add .
git commit -m "feat: complete token interval tracking implementation

- Real-time 5-minute interval updates during scanning
- End-of-session summary table with Rich formatting
- CLI command for historical session analysis
- Full test coverage
- User documentation"
\```

---

## Verification Checklist

- [ ] All tests pass (75+ tests)
- [ ] token-intervals CLI command available
- [ ] Real-time interval logging works
- [ ] End-of-session summary displays
- [ ] Historical query returns data
- [ ] Documentation complete
- [ ] No breaking changes to existing code

## Next Steps

After implementation complete:
1. Merge feature branch to main
2. Test with live scanner run
3. Monitor for any edge cases
4. Consider adding alerts for high-cost intervals (future enhancement)
