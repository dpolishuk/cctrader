# Daily Session Grouping Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable scanner to maintain one continuous Claude session per trading day, consolidating all symbol analyses into a single conversation thread.

**Architecture:** Add daily session ID format (e.g., `scanner-2025-11-21`) to SessionManager, modify AgentWrapper to reuse Claude client across multiple analyses, and add `--daily` flag to scanner CLI command.

**Tech Stack:** Python async/await, Claude Agent SDK, aiosqlite

---

## Current State Analysis

**Problem:** Scanner creates new Claude session for each symbol analysis, causing fragmented output across multiple conversation threads.

**Current Flow:**
```
Scanner loop → Symbol 1 → new ClaudeSDKClient() → Analyze → Close
             → Symbol 2 → new ClaudeSDKClient() → Analyze → Close
             → Symbol 3 → new ClaudeSDKClient() → Analyze → Close
```

**Desired Flow:**
```
Scanner --daily → Create daily session (scanner-2025-11-21)
                → ClaudeSDKClient (persistent)
                → Symbol 1 → query() → Continue session
                → Symbol 2 → query() → Continue session
                → Symbol 3 → query() → Continue session
                → (All in one conversation)
```

**Key Files:**
- `src/agent/session_manager.py` - Manages session persistence
- `src/agent/scanner/agent_wrapper.py` - Wraps Claude Agent SDK
- `src/agent/scanner/main_loop.py` - Scanner orchestration
- `src/agent/main.py` - CLI entry point

---

## Task 1: Add Daily Session ID Support

**Files:**
- Modify: `src/agent/session_manager.py:47-72`
- Test: `tests/test_session_manager_daily.py` (create)

### Step 1: Write failing test for daily session ID generation

**Create:** `tests/test_session_manager_daily.py`

```python
"""Tests for daily session ID functionality."""
import pytest
from datetime import datetime
from pathlib import Path
from src.agent.session_manager import SessionManager


@pytest.mark.asyncio
async def test_generate_daily_session_id():
    """Test that daily session IDs include date."""
    manager = SessionManager(Path(":memory:"))

    session_id = manager.generate_daily_session_id("scanner")

    # Should be format: scanner-YYYY-MM-DD
    today = datetime.now().strftime("%Y-%m-%d")
    assert session_id == f"scanner-{today}"


@pytest.mark.asyncio
async def test_different_dates_different_session_ids():
    """Test that different dates generate different session IDs."""
    manager = SessionManager(Path(":memory:"))

    # Mock different dates
    from unittest.mock import patch

    with patch('src.agent.session_manager.datetime') as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 11, 21)
        mock_datetime.now().strftime = lambda fmt: "2025-11-21"
        session_id_1 = manager.generate_daily_session_id("scanner")

    with patch('src.agent.session_manager.datetime') as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 11, 22)
        mock_datetime.now().strftime = lambda fmt: "2025-11-22"
        session_id_2 = manager.generate_daily_session_id("scanner")

    assert session_id_1 != session_id_2
    assert session_id_1 == "scanner-2025-11-21"
    assert session_id_2 == "scanner-2025-11-22"
```

### Step 2: Run test to verify it fails

```bash
pytest tests/test_session_manager_daily.py::test_generate_daily_session_id -v
```

**Expected:** FAIL with "SessionManager has no attribute 'generate_daily_session_id'"

### Step 3: Implement generate_daily_session_id method

**Modify:** `src/agent/session_manager.py`

Add after line 31 (after `__init__`):

```python
    def generate_daily_session_id(self, operation_type: str) -> str:
        """
        Generate daily session ID with format: {operation_type}-YYYY-MM-DD.

        Args:
            operation_type: Type of operation (scanner, analysis, etc.)

        Returns:
            Daily session ID string
        """
        today = datetime.now().strftime("%Y-%m-%d")
        return f"{operation_type}-{today}"
```

### Step 4: Run test to verify it passes

```bash
pytest tests/test_session_manager_daily.py::test_generate_daily_session_id -v
```

**Expected:** PASS

### Step 5: Commit

```bash
git add src/agent/session_manager.py tests/test_session_manager_daily.py
git commit -m "feat: add daily session ID generation to SessionManager"
```

---

## Task 2: Add Session Expiry Check

**Files:**
- Modify: `src/agent/session_manager.py:47-72`
- Modify: `tests/test_session_manager_daily.py`

### Step 1: Write failing test for session expiry

**Modify:** `tests/test_session_manager_daily.py`

Add test:

```python
@pytest.mark.asyncio
async def test_get_session_id_expires_old_daily_sessions(tmp_path):
    """Test that daily sessions from previous days are not returned."""
    db_path = tmp_path / "test.db"
    manager = SessionManager(db_path)
    await manager.init_db()

    # Save an old daily session (yesterday)
    from unittest.mock import patch
    with patch('src.agent.session_manager.datetime') as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 11, 20)
        mock_datetime.now().strftime = lambda fmt: "2025-11-20"
        mock_datetime.now().isoformat = lambda: "2025-11-20T10:00:00+00:00"
        old_session_id = manager.generate_daily_session_id("scanner")
        await manager.save_session_id("scanner", old_session_id)

    # Try to get session today (should return None because it's expired)
    with patch('src.agent.session_manager.datetime') as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 11, 21)
        mock_datetime.now().strftime = lambda fmt: "2025-11-21"
        session_id = await manager.get_session_id("scanner", daily=True)

    assert session_id is None  # Old session should be expired
```

### Step 2: Run test to verify it fails

```bash
pytest tests/test_session_manager_daily.py::test_get_session_id_expires_old_daily_sessions -v
```

**Expected:** FAIL with "get_session_id() got an unexpected keyword argument 'daily'"

### Step 3: Implement daily session expiry logic

**Modify:** `src/agent/session_manager.py:47-72`

Replace the `get_session_id` method:

```python
    async def get_session_id(self, operation_type: str, daily: bool = False) -> Optional[str]:
        """
        Get existing session ID for operation type.

        Args:
            operation_type: Type of operation (scanner, analysis, etc.)
            daily: If True, only return session if it matches today's date

        Returns:
            Session ID if exists and valid, None otherwise
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT session_id FROM agent_sessions WHERE operation_type = ?",
                (operation_type,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    session_id = row[0]

                    # If daily mode, check if session ID matches today's date
                    if daily:
                        expected_session_id = self.generate_daily_session_id(operation_type)
                        if session_id != expected_session_id:
                            logger.info(f"Session {session_id} is from a previous day, starting fresh")
                            return None

                    # Update last_used_at
                    await db.execute(
                        "UPDATE agent_sessions SET last_used_at = ? WHERE operation_type = ?",
                        (datetime.now(timezone.utc).isoformat(), operation_type)
                    )
                    await db.commit()
                    logger.info(f"Resuming session for {operation_type}: {session_id}")
                    return session_id
        return None
```

### Step 4: Run test to verify it passes

```bash
pytest tests/test_session_manager_daily.py::test_get_session_id_expires_old_daily_sessions -v
```

**Expected:** PASS

### Step 5: Commit

```bash
git add src/agent/session_manager.py tests/test_session_manager_daily.py
git commit -m "feat: add daily session expiry check"
```

---

## Task 3: Add Persistent Client Mode to AgentWrapper

**Files:**
- Modify: `src/agent/scanner/agent_wrapper.py:19-150`
- Test: `tests/test_agent_wrapper_persistent.py` (create)

### Step 1: Write test for persistent client mode

**Create:** `tests/test_agent_wrapper_persistent.py`

```python
"""Tests for persistent client mode in AgentWrapper."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.agent.scanner.agent_wrapper import AgentWrapper
from claude_agent_sdk import ClaudeAgentOptions


@pytest.mark.asyncio
async def test_persistent_client_multiple_analyses():
    """Test that persistent mode reuses same client for multiple analyses."""
    options = ClaudeAgentOptions(
        tools=[],
        system_prompt="Test",
        model="claude-sonnet-4"
    )

    wrapper = AgentWrapper(
        agent_options=options,
        persistent_client=True
    )

    # Mock the client
    with patch('src.agent.scanner.agent_wrapper.ClaudeSDKClient') as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__.return_value = mock_client

        # Run multiple analyses
        await wrapper.run("Analysis 1")
        await wrapper.run("Analysis 2")

        # Client should be created only once in persistent mode
        assert MockClient.call_count == 1


@pytest.mark.asyncio
async def test_non_persistent_client_creates_new_each_time():
    """Test that non-persistent mode creates new client for each analysis."""
    options = ClaudeAgentOptions(
        tools=[],
        system_prompt="Test",
        model="claude-sonnet-4"
    )

    wrapper = AgentWrapper(
        agent_options=options,
        persistent_client=False
    )

    with patch('src.agent.scanner.agent_wrapper.ClaudeSDKClient') as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__.return_value = mock_client

        await wrapper.run("Analysis 1")
        await wrapper.run("Analysis 2")

        # Client should be created twice in non-persistent mode
        assert MockClient.call_count == 2
```

### Step 2: Run test to verify it fails

```bash
pytest tests/test_agent_wrapper_persistent.py -v
```

**Expected:** FAIL with "__init__() got an unexpected keyword argument 'persistent_client'"

### Step 3: Implement persistent client mode

**Modify:** `src/agent/scanner/agent_wrapper.py`

Update `__init__` method (lines 22-41):

```python
    def __init__(
        self,
        agent_options: ClaudeAgentOptions,
        token_tracker: Optional[Any] = None,
        session_manager: Optional[Any] = None,
        operation_type: str = "scanner",
        persistent_client: bool = False
    ):
        """
        Initialize wrapper.

        Args:
            agent_options: ClaudeAgentOptions with tools, system prompt, etc.
            token_tracker: Optional TokenTracker instance for tracking usage
            session_manager: Optional SessionManager for session persistence
            operation_type: Type of operation for session isolation (default: scanner)
            persistent_client: If True, reuse same Claude client across multiple run() calls
        """
        self.agent_options = agent_options
        self.token_tracker = token_tracker
        self.session_manager = session_manager
        self.operation_type = operation_type
        self.persistent_client = persistent_client

        # Store persistent client and session if enabled
        self._client = None
        self._session_id = None
```

Update `run` method (lines 43-150) to support persistent client:

```python
    async def run(self, prompt: str, symbol: str = None) -> Dict[str, Any]:
        """
        Run analysis and return structured response.

        Uses Claude Agent SDK with tool-based output pattern:
        1. Creates signal queue for communication
        2. Sets queue in context for submit_trading_signal tool
        3. Sends prompt to agent via ClaudeSDKClient
        4. Waits for agent to call submit_trading_signal (max 120s)
        5. Returns signal dict or confidence=0 on timeout/error

        Args:
            prompt: Analysis prompt
            symbol: Optional symbol for metadata tracking

        Returns:
            Dict with confidence, entry_price, stop_loss, tp1, scoring components, analysis
        """
        # Create queue for signal communication
        signal_queue = asyncio.Queue()

        # Set queue in module-level storage so submit_trading_signal tool can access it
        set_signal_queue(signal_queue)

        # Track timing for token tracking
        start_time = time.time()
        final_message = None

        try:
            # In persistent mode, reuse existing client and session
            if self.persistent_client and self._client is not None:
                client = self._client
                session_id = self._session_id
                logger.info(f"Reusing persistent client (session: {session_id})")
            else:
                # Get existing session ID if session manager is available
                session_id = None
                if self.session_manager:
                    session_id = await self.session_manager.get_session_id(
                        self.operation_type,
                        daily=self.persistent_client  # Use daily sessions in persistent mode
                    )
                    if session_id:
                        logger.info(f"Resuming {self.operation_type} session: {session_id}")
                    else:
                        logger.info(f"Starting new {self.operation_type} session")

                # Create agent client with configured options
                if self.persistent_client:
                    # In persistent mode, store the client
                    self._client = ClaudeSDKClient(options=self.agent_options)
                    await self._client.__aenter__()
                    client = self._client
                else:
                    # In non-persistent mode, use context manager (will auto-close)
                    client = ClaudeSDKClient(options=self.agent_options)
                    await client.__aenter__()

            logger.info("Starting agent analysis")

            # Send analysis prompt (with session resumption if available)
            query_options = {}
            if session_id:
                query_options['resume'] = session_id

            await client.query(prompt, **query_options)

            # Process agent messages (log for debugging and capture final message)
            message_task = asyncio.create_task(
                self._process_messages(client)
            )

            # Wait for signal with 120-second timeout
            try:
                signal = await asyncio.wait_for(
                    signal_queue.get(),
                    timeout=120.0
                )

                logger.info(
                    f"Agent analysis complete: confidence={signal['confidence']}, "
                    f"symbol={signal['symbol']}"
                )

                # Cancel message processing task
                message_task.cancel()
                try:
                    await message_task
                except asyncio.CancelledError:
                    pass

                # Record token usage if tracker is available
                if self.token_tracker and hasattr(self, '_result_message'):
                    duration = time.time() - start_time
                    await self.token_tracker.record_usage(
                        result=self._result_message,
                        operation_type="mover_analysis",
                        duration_seconds=duration,
                        metadata={"symbol": symbol or signal.get('symbol', 'unknown')}
                    )

                # Save session ID if session manager is available
                if self.session_manager and hasattr(client, 'session_id') and client.session_id:
                    # In persistent mode, generate daily session ID
                    if self.persistent_client and not session_id:
                        session_id = self.session_manager.generate_daily_session_id(self.operation_type)
                        logger.info(f"Generated daily session ID: {session_id}")

                    # Store session ID for persistent mode
                    if self.persistent_client:
                        self._session_id = client.session_id

                    await self.session_manager.save_session_id(
                        self.operation_type,
                        session_id or client.session_id,
                        metadata=f'{{"symbol": "{symbol or signal.get("symbol", "unknown")}"}}'
                    )

                return signal

            except asyncio.TimeoutError:
                logger.warning(
                    "Agent analysis timeout after 120 seconds - "
                    "agent did not call submit_trading_signal"
                )

                # Cancel message processing
                message_task.cancel()
                try:
                    await message_task
                except asyncio.CancelledError:
                    pass

                return self._timeout_response()

        except Exception as e:
            logger.error(f"Error in agent analysis: {e}", exc_info=True)
            return self._error_response(str(e))

        finally:
            # Clean up queue
            clear_signal_queue()

            # Only close client if NOT in persistent mode
            if not self.persistent_client and client:
                await client.__aexit__(None, None, None)
```

Add cleanup method at end of class:

```python
    async def cleanup(self):
        """Clean up persistent client if exists."""
        if self._client:
            await self._client.__aexit__(None, None, None)
            self._client = None
            self._session_id = None
            logger.info("Persistent client cleaned up")
```

### Step 4: Run test to verify it passes

```bash
pytest tests/test_agent_wrapper_persistent.py -v
```

**Expected:** PASS (both tests)

### Step 5: Commit

```bash
git add src/agent/scanner/agent_wrapper.py tests/test_agent_wrapper_persistent.py
git commit -m "feat: add persistent client mode to AgentWrapper"
```

---

## Task 4: Update MarketMoversScanner to Support Daily Mode

**Files:**
- Modify: `src/agent/scanner/main_loop.py:17-87`
- Test: Integration test with actual scanner

### Step 1: Add daily_mode flag to scanner init

**Modify:** `src/agent/scanner/main_loop.py`

Update `__init__` method (lines 20-61):

```python
    def __init__(
        self,
        exchange,
        agent,
        portfolio,
        db,
        config: Optional[ScannerConfig] = None,
        risk_config: Optional[RiskConfig] = None,
        daily_mode: bool = False
    ):
        """
        Initialize market movers scanner.

        Args:
            exchange: CCXT exchange instance
            agent: Claude Agent instance (AgentWrapper)
            portfolio: Portfolio manager
            db: Database operations instance
            config: Scanner configuration (optional)
            risk_config: Risk configuration (optional)
            daily_mode: If True, maintain single session per day (optional)
        """
        self.exchange = exchange
        self.agent = agent
        self.portfolio = portfolio
        self.db = db
        self.daily_mode = daily_mode

        self.config = config or ScannerConfig()
        self.risk_config = risk_config or RiskConfig()

        # Initialize components
        self.symbol_manager = FuturesSymbolManager(
            exchange,
            min_volume_usd=self.config.min_volume_usd
        )
        self.momentum_scanner = MomentumScanner(
            exchange,
            threshold_pct=self.config.mover_threshold_pct
        )
        self.confidence_calculator = ConfidenceCalculator()
        self.risk_validator = RiskValidator(self.risk_config, portfolio)
        self.prompt_builder = PromptBuilder()

        self.running = False
```

### Step 2: Add cleanup call in stop method

**Modify:** `src/agent/scanner/main_loop.py`

Update `stop` method (lines 83-86):

```python
    async def stop(self):
        """Stop the scanning loop."""
        logger.info("Stopping scanner...")
        self.running = False

        # Clean up agent persistent client if in daily mode
        if self.daily_mode and hasattr(self.agent, 'cleanup'):
            await self.agent.cleanup()
```

### Step 3: Manual integration test

**No automated test** - this will be tested manually in next task with CLI.

### Step 4: Commit

```bash
git add src/agent/scanner/main_loop.py
git commit -m "feat: add daily mode support to MarketMoversScanner"
```

---

## Task 5: Add --daily Flag to CLI Scanner Command

**Files:**
- Modify: `src/agent/main.py:311-556`
- Test: Manual CLI test

### Step 1: Add --daily flag to scanner command

**Modify:** `src/agent/main.py`

Find the `@cli.command()` for scanner (around line 308) and add the flag:

```python
@cli.command()
@click.option('--interval', default=300, help='Scan interval in seconds')
@click.option('--movers', default=3, help='Max movers to analyze per scan')
@click.option('--daily', is_flag=True, help='Maintain single session per day (all analyses in one conversation)')
def scanner(interval, movers, daily):
    """Run market movers scanner - detects and analyzes 5%+ movers."""
```

### Step 2: Pass daily flag to AgentWrapper

**Modify:** `src/agent/main.py`

Find where AgentWrapper is created (around line 367) and add `persistent_client=daily`:

```python
        # Create agent wrapper with session management
        agent_wrapper = AgentWrapper(
            agent_options=agent_options,
            token_tracker=token_tracker if show_tokens else None,
            session_manager=session_manager,
            operation_type="scanner",
            persistent_client=daily  # Enable persistent client in daily mode
        )
```

### Step 3: Pass daily flag to scanner initialization

**Modify:** `src/agent/main.py`

Find where MarketMoversScanner is created (around line 533) and add `daily_mode=daily`:

```python
        # Create and start scanner
        scanner = MarketMoversScanner(
            exchange=exchange,
            agent=agent_wrapper,
            portfolio=portfolio,
            db=db,
            config=scanner_config,
            risk_config=risk_config,
            daily_mode=daily  # Pass daily mode flag
        )
```

### Step 4: Add startup log message for daily mode

**Modify:** `src/agent/main.py`

After scanner creation, add log message:

```python
        scanner.config.scan_interval_seconds = interval
        scanner.config.max_movers_per_scan = movers

        # Log daily mode status
        if daily:
            console.print("[green]✓[/green] Daily mode enabled - maintaining single session per day")
            console.print(f"[dim]  All symbol analyses will be in one continuous conversation[/dim]\n")

        try:
            await scanner.start()
```

### Step 5: Manual CLI test

**Test command:**

```bash
# Start scanner in daily mode
python -m src.agent.main scanner --daily --interval 60 --movers 2

# Expected output:
# ✓ Daily mode enabled - maintaining single session per day
#   All symbol analyses will be in one continuous conversation
#
# [Scanner should analyze multiple symbols in same conversation]
# [Check logs for "Reusing persistent client (session: scanner-2025-11-21)"]
```

**Verify:**
1. First symbol creates new session with ID `scanner-2025-11-21`
2. Subsequent symbols show "Reusing persistent client"
3. All analyses appear in single conversation thread

### Step 6: Commit

```bash
git add src/agent/main.py
git commit -m "feat: add --daily flag to scanner CLI command"
```

---

## Task 6: Add Documentation and Usage Guide

**Files:**
- Create: `docs/daily-session-mode.md`
- Modify: `README.md`

### Step 1: Create documentation file

**Create:** `docs/daily-session-mode.md`

```markdown
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
python -m src.agent.main scanner --daily
```

### With Custom Settings

```bash
# Daily mode with 60s interval and max 5 movers per scan
python -m src.agent.main scanner --daily --interval 60 --movers 5
```

### Without Daily Mode (Default)

```bash
# Each symbol gets its own session
python -m src.agent.main scanner
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
python -m src.agent.main session-stats

# Clear old sessions
python -m src.agent.main clear-sessions --clear-type scanner
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
python -m src.agent.main clear-sessions --clear-type scanner
```
```

### Step 2: Update README.md

**Modify:** `README.md`

Add section after scanner documentation:

```markdown
### Daily Session Mode

Maintain a single continuous conversation per trading day:

```bash
# All analyses in one session per day
python -m src.agent.main scanner --daily
```

**Benefits:**
- Consolidated view of all trading decisions
- Better context across analyses
- Easier review and debugging

See [Daily Session Mode Documentation](docs/daily-session-mode.md) for details.
```

### Step 3: Commit

```bash
git add docs/daily-session-mode.md README.md
git commit -m "docs: add daily session mode documentation"
```

---

## Task 7: Integration Testing

**Files:**
- Test: Manual integration test with real scanner

### Step 1: Test daily mode with mock movers

```bash
# Terminal 1: Start scanner in daily mode
python -m src.agent.main scanner --daily --interval 60 --movers 2

# Let it run through 2-3 scan cycles
# Watch for:
# - "Generated daily session ID: scanner-YYYY-MM-DD"
# - "Reusing persistent client (session: scanner-YYYY-MM-DD)"
```

### Step 2: Verify session persistence across restarts

```bash
# Stop scanner (Ctrl+C)

# Restart scanner (same day)
python -m src.agent.main scanner --daily --interval 60

# Should see:
# - "Resuming scanner session: scanner-YYYY-MM-DD"
# - Continues same conversation
```

### Step 3: Test regular mode still works

```bash
# Run scanner without --daily flag
python -m src.agent.main scanner --interval 60 --movers 2

# Should see:
# - No daily mode message
# - Each symbol gets separate session
```

### Step 4: Verify database state

```bash
sqlite3 trading_data.db "SELECT operation_type, session_id, created_at FROM agent_sessions WHERE operation_type='scanner';"

# Should show daily session ID for scanner
```

### Step 5: Document test results

Create test report noting:
- Daily mode successfully creates single session
- Session persists across scanner restarts
- Regular mode still works as before
- No errors in logs

No commit (manual testing).

---

## Summary

**Changes Made:**

1. **SessionManager**: Added daily session ID generation and expiry
2. **AgentWrapper**: Added persistent client mode for reusing same Claude client
3. **MarketMoversScanner**: Added daily mode support with cleanup
4. **CLI**: Added `--daily` flag to scanner command
5. **Documentation**: Created usage guide and updated README

**Testing:**

- Unit tests for daily session ID logic
- Unit tests for persistent client mode
- Integration tests for full daily mode workflow

**DRY, YAGNI, TDD Applied:**

- Minimal changes to existing code
- No over-engineering of session management
- TDD approach with failing tests first
- Frequent, small commits

---

## Execution Options

Plan complete and saved to `docs/plans/2025-11-21-daily-session-grouping.md`.

**Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration with quality gates

**2. Parallel Session (separate)** - Open new session with executing-plans skill, batch execution with review checkpoints

**Which approach?**
