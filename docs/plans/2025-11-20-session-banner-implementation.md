# Session Information Banner Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add CLI banner showing model, API endpoint, token tracking status, and session info at command start.

**Architecture:** Create new `cli_banner.py` module with Rich-based panel display. Add config field for API URL. Integrate banner calls into main.py commands after DB initialization.

**Tech Stack:** Python 3.12, Rich (console formatting), asyncio

---

## Task 1: Add API URL to Configuration

**Files:**
- Modify: `src/agent/config.py:34-76`
- Test: Manual verification (no unit test needed for config)

**Step 1: Add ANTHROPIC_API_URL field to Config class**

In `src/agent/config.py`, add after line 38 (after BYBIT_API_SECRET):

```python
    # Anthropic Settings
    ANTHROPIC_API_URL: str = os.getenv("ANTHROPIC_API_URL", "https://api.anthropic.com")
```

**Step 2: Verify configuration loads**

Run: `python -c "from src.agent.config import config; print(config.ANTHROPIC_API_URL)"`
Expected: `https://api.anthropic.com`

**Step 3: Commit**

```bash
git add src/agent/config.py
git commit -m "feat: add ANTHROPIC_API_URL configuration field"
```

---

## Task 2: Create SessionBanner Class

**Files:**
- Create: `src/agent/cli_banner.py`
- Test: Manual verification (display-only component)

**Step 1: Create cli_banner.py with SessionBanner class**

Create `src/agent/cli_banner.py`:

```python
"""CLI banner for displaying session information."""
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel


class SessionBanner:
    """Display session information banner using Rich formatting."""

    @staticmethod
    def display(
        model: str,
        api_endpoint: str,
        token_tracking_enabled: bool,
        session_id: Optional[str],
        operation_type: str,
        session_status: str  # "resumed" or "new"
    ):
        """
        Display session information banner.

        Args:
            model: Claude model name (e.g., "claude-sonnet-4-5")
            api_endpoint: Anthropic API URL
            token_tracking_enabled: Whether token tracking is enabled
            session_id: Session ID if available
            operation_type: Operation type (scanner, analysis, etc.)
            session_status: "resumed" or "new"
        """
        console = Console()

        # Create table for aligned display
        table = Table.grid(padding=(0, 2))
        table.add_column(style="dim", justify="right")
        table.add_column(style="bright_white")

        # Add rows
        table.add_row("Model:", model)
        table.add_row("API Endpoint:", api_endpoint)

        # Token tracking status with indicator
        if token_tracking_enabled and session_id:
            # Truncate session ID to first 8 chars
            short_id = session_id[:8] + "..." if len(session_id) > 8 else session_id
            tracking_status = f"[green]✓[/green] Enabled (Session: {short_id})"
        elif token_tracking_enabled:
            tracking_status = "[yellow]⚠[/yellow] Enabled (No session)"
        else:
            tracking_status = "[red]✗[/red] Disabled"

        table.add_row("Token Tracking:", tracking_status)
        table.add_row("Operation:", operation_type)

        # Session status
        if session_status == "resumed" and session_id:
            short_session = session_id[:8] + "..." if len(session_id) > 8 else session_id
            status_text = f"Resuming {short_session}"
        elif session_status == "new":
            status_text = "New session created"
        else:
            status_text = "N/A"

        table.add_row("Session Status:", status_text)

        # Display panel
        panel = Panel(
            table,
            title="Session Information",
            border_style="cyan",
            padding=(1, 2)
        )

        console.print()
        console.print(panel)
        console.print()
```

**Step 2: Verify module imports**

Run: `python -c "from src.agent.cli_banner import SessionBanner; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/agent/cli_banner.py
git commit -m "feat: add SessionBanner class for CLI display"
```

---

## Task 3: Create Helper Function

**Files:**
- Modify: `src/agent/cli_banner.py`
- Test: Manual verification

**Step 1: Add show_session_banner helper function**

Add to end of `src/agent/cli_banner.py`:

```python


async def show_session_banner(
    operation_type: str,
    model: str = "claude-sonnet-4-5",
    session_manager: Optional['SessionManager'] = None
) -> None:
    """
    Gather session info and display banner.

    Args:
        operation_type: Type of operation (scanner, analysis, monitor, paper_trading)
        model: Claude model name
        session_manager: Optional SessionManager instance for session info
    """
    from .config import config
    import logging

    logger = logging.getLogger(__name__)

    # Gather information
    api_endpoint = config.ANTHROPIC_API_URL
    token_tracking_enabled = config.TOKEN_TRACKING_ENABLED

    # Get session info if manager provided
    session_id = None
    session_status = "new"

    if session_manager:
        try:
            # Check for existing session
            existing_session = await session_manager.get_session_id(operation_type)
            if existing_session:
                session_id = existing_session
                session_status = "resumed"
            else:
                session_status = "new"
        except Exception as e:
            logger.warning(f"Failed to get session info: {e}")
            session_status = "error"

    # Display banner (wrapped in try-catch to prevent crashes)
    try:
        SessionBanner.display(
            model=model,
            api_endpoint=api_endpoint,
            token_tracking_enabled=token_tracking_enabled,
            session_id=session_id,
            operation_type=operation_type,
            session_status=session_status
        )
    except Exception as e:
        logger.warning(f"Failed to display session banner: {e}")
```

**Step 2: Verify helper imports**

Run: `python -c "from src.agent.cli_banner import show_session_banner; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/agent/cli_banner.py
git commit -m "feat: add show_session_banner helper function"
```

---

## Task 4: Integrate Banner into scan_movers Command

**Files:**
- Modify: `src/agent/main.py:232-476`
- Test: Manual run of scan_movers command

**Step 1: Import banner helper in main.py**

Add to imports at top of `src/agent/main.py` (after line 12):

```python
from .cli_banner import show_session_banner
```

**Step 2: Add banner call to scan_movers**

In `scan_movers` command, after line 423 (after `await session_manager.init_db()`), add:

```python
        # Display session banner
        await show_session_banner(
            operation_type=SessionManager.SCANNER,
            model="claude-sonnet-4-5",
            session_manager=session_manager
        )
```

**Step 3: Test scan_movers command manually**

Run: `python -m src.agent.main scan-movers --help`
Expected: Help text displays without errors

**Step 4: Commit**

```bash
git add src/agent/main.py
git commit -m "feat: integrate session banner into scan_movers command"
```

---

## Task 5: Integrate Banner into analyze Command

**Files:**
- Modify: `src/agent/main.py:41-73`
- Test: Manual run of analyze command

**Step 1: Add session manager to analyze command**

In `analyze` command function (starting line 45), after agent initialization (line 49), add:

```python
        # Initialize session manager for banner
        from src.agent.session_manager import SessionManager
        from pathlib import Path
        import os

        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))
        session_manager = SessionManager(db_path)
        await session_manager.init_db()

        # Display session banner
        await show_session_banner(
            operation_type=SessionManager.ANALYSIS,
            model="claude-sonnet-4-5",
            session_manager=session_manager
        )
```

**Step 2: Test analyze command**

Run: `python -m src.agent.main analyze --help`
Expected: Help text displays without errors

**Step 3: Commit**

```bash
git add src/agent/main.py
git commit -m "feat: integrate session banner into analyze command"
```

---

## Task 6: Integrate Banner into monitor Command

**Files:**
- Modify: `src/agent/main.py:23-39`
- Test: Manual run of monitor command

**Step 1: Add session manager to monitor command**

In `monitor` command function (starting line 26), after agent initialization (line 30), add:

```python
        # Initialize session manager for banner
        from src.agent.session_manager import SessionManager
        from pathlib import Path
        import os

        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))
        session_manager = SessionManager(db_path)
        await session_manager.init_db()

        # Display session banner
        await show_session_banner(
            operation_type=SessionManager.MONITOR,
            model="claude-sonnet-4-5",
            session_manager=session_manager
        )
```

**Step 2: Test monitor command**

Run: `python -m src.agent.main monitor --help`
Expected: Help text displays without errors

**Step 3: Commit**

```bash
git add src/agent/main.py
git commit -m "feat: integrate session banner into monitor command"
```

---

## Task 7: Integrate Banner into paper_monitor Command

**Files:**
- Modify: `src/agent/main.py:193-211`
- Test: Manual run of paper_monitor command

**Step 1: Add session manager to paper_monitor command**

In `paper_monitor` command function (starting line 197), after agent initialization (line 205), add:

```python
        # Initialize session manager for banner
        from src.agent.session_manager import SessionManager
        from pathlib import Path
        import os

        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))
        session_manager = SessionManager(db_path)
        await session_manager.init_db()

        # Display session banner
        await show_session_banner(
            operation_type=SessionManager.PAPER_TRADING,
            model="claude-sonnet-4-5",
            session_manager=session_manager
        )
```

**Step 2: Test paper_monitor command**

Run: `python -m src.agent.main paper-monitor --help`
Expected: Help text displays without errors

**Step 3: Commit**

```bash
git add src/agent/main.py
git commit -m "feat: integrate session banner into paper_monitor command"
```

---

## Task 8: End-to-End Testing

**Files:**
- Test: All modified commands
- Document: Update if needed

**Step 1: Test scan_movers with banner display**

Run: `python -m src.agent.main scan-movers --interval 300 --portfolio "Test"`
Press Ctrl+C after banner displays
Expected: Session banner appears before "Scanner initialized" message

**Step 2: Test with TOKEN_TRACKING_ENABLED=false**

Run: `TOKEN_TRACKING_ENABLED=false python -m src.agent.main scan-movers --help`
Expected: Help displays, banner would show "✗ Disabled" (if command ran)

**Step 3: Test with custom ANTHROPIC_API_URL**

Run: `ANTHROPIC_API_URL=https://custom.api.com python -m src.agent.main analyze --help`
Expected: Help displays, banner would show custom URL (if command ran)

**Step 4: Verify all tests still pass**

Run: `pytest tests/ -q`
Expected: All tests pass (212 tests)

**Step 5: Final commit**

```bash
git add -A
git commit -m "test: verify session banner integration across all commands"
```

---

## Completion Checklist

- [ ] Config field added (ANTHROPIC_API_URL)
- [ ] SessionBanner class created with Rich formatting
- [ ] Helper function show_session_banner() created
- [ ] Banner integrated into scan_movers
- [ ] Banner integrated into analyze
- [ ] Banner integrated into monitor
- [ ] Banner integrated into paper_monitor
- [ ] End-to-end testing completed
- [ ] All existing tests pass
- [ ] Feature ready for merge

**Total commits:** 8
**Estimated time:** 30-40 minutes
