# Fix Environment Variables Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix config to load correct environment variable names (ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN) and display them in session banner.

**Architecture:** Update Config class to match .env variable names, update SessionBanner to display masked auth token, update all existing tests to pass new parameter.

**Tech Stack:** Python 3.12, Rich (console formatting), pytest

---

## Task 1: Update Configuration Fields

**Files:**
- Modify: `src/agent/config.py:36-37`
- Test: Manual verification

**Step 1: Update config fields**

In `src/agent/config.py`, replace lines 36-37:

```python
# BEFORE:
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_API_URL: str = os.getenv("ANTHROPIC_API_URL", "https://api.anthropic.com")

# AFTER:
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_AUTH_TOKEN: str = os.getenv("ANTHROPIC_AUTH_TOKEN", "")
ANTHROPIC_BASE_URL: str = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
```

**Step 2: Verify config loads correctly**

Run: `python -c "from src.agent.config import config; print(f'URL: {config.ANTHROPIC_BASE_URL}'); print(f'Token: {config.ANTHROPIC_AUTH_TOKEN[:8]}...')"`
Expected: Shows values from .env file

**Step 3: Commit**

```bash
git add src/agent/config.py
git commit -m "fix: rename ANTHROPIC_API_URL to ANTHROPIC_BASE_URL and add ANTHROPIC_AUTH_TOKEN"
```

---

## Task 2: Update SessionBanner Display Method

**Files:**
- Modify: `src/agent/cli_banner.py:18-28` (function signature)
- Modify: `src/agent/cli_banner.py:50-55` (add auth token row)
- Test: Will update tests in Task 3

**Step 1: Add auth_token parameter to display() method**

In `src/agent/cli_banner.py`, update the `display()` method signature (around line 18):

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
    """
    Display session information banner.

    Args:
        model: Claude model name (e.g., "claude-sonnet-4-5")
        api_endpoint: Anthropic API URL
        auth_token: Anthropic auth token (will be masked)  # NEW
        token_tracking_enabled: Whether token tracking is enabled
        session_id: Session ID if available
        operation_type: Operation type (scanner, analysis, etc.)
        session_status: "resumed" or "new"
    """
```

**Step 2: Add auth token display row**

In the same file, after the API Endpoint row (around line 50), add:

```python
# Add rows
table.add_row("Model:", model)
table.add_row("API Endpoint:", api_endpoint)

# NEW: Add auth token row with masking
if auth_token and len(auth_token) >= 12:
    # Mask token: show first 8 and last 4 chars
    masked_token = f"{auth_token[:8]}...{auth_token[-4:]}"
    table.add_row("Auth Token:", masked_token)
elif auth_token:
    # Short token: just mask middle
    masked_token = f"{auth_token[:4]}...{auth_token[-2:]}"
    table.add_row("Auth Token:", masked_token)
else:
    table.add_row("Auth Token:", "[dim]Not configured[/dim]")

# Continue with token tracking row...
```

**Step 3: Verify import still works**

Run: `python -c "from src.agent.cli_banner import SessionBanner; print('OK')"`
Expected: No errors, prints "OK"

**Step 4: Commit**

```bash
git add src/agent/cli_banner.py
git commit -m "feat: add auth_token parameter to SessionBanner.display()"
```

---

## Task 3: Update show_session_banner Helper

**Files:**
- Modify: `src/agent/cli_banner.py:107-145` (helper function)
- Test: Will update tests in Task 4

**Step 1: Update helper to read ANTHROPIC_BASE_URL and ANTHROPIC_AUTH_TOKEN**

In `src/agent/cli_banner.py`, update the `show_session_banner()` function (around line 113-120):

```python
# BEFORE:
api_endpoint = os.getenv("ANTHROPIC_API_URL", "https://api.anthropic.com")
token_tracking_enabled = config.TOKEN_TRACKING_ENABLED

# AFTER:
api_endpoint = config.ANTHROPIC_BASE_URL
auth_token = config.ANTHROPIC_AUTH_TOKEN
token_tracking_enabled = config.TOKEN_TRACKING_ENABLED
```

**Step 2: Update display() call to pass auth_token**

In the same function (around line 139-145), update the call:

```python
# BEFORE:
SessionBanner.display(
    model=model,
    api_endpoint=api_endpoint,
    token_tracking_enabled=token_tracking_enabled,
    session_id=session_id,
    operation_type=operation_type,
    session_status=session_status
)

# AFTER:
SessionBanner.display(
    model=model,
    api_endpoint=api_endpoint,
    auth_token=auth_token,  # NEW
    token_tracking_enabled=token_tracking_enabled,
    session_id=session_id,
    operation_type=operation_type,
    session_status=session_status
)
```

**Step 3: Verify helper still imports**

Run: `python -c "from src.agent.cli_banner import show_session_banner; print('OK')"`
Expected: No errors, prints "OK"

**Step 4: Commit**

```bash
git add src/agent/cli_banner.py
git commit -m "feat: update show_session_banner to use ANTHROPIC_BASE_URL and pass auth_token"
```

---

## Task 4: Update Unit Tests for SessionBanner

**Files:**
- Modify: `tests/test_cli_banner.py:22-90` (all SessionBanner tests)
- Test: `pytest tests/test_cli_banner.py::TestSessionBanner -v`

**Step 1: Update test_display_with_full_info**

In `tests/test_cli_banner.py`, update the first test (around line 22):

```python
def test_display_with_full_info(self):
    """Test banner displays all information correctly."""
    SessionBanner.display(
        model="claude-sonnet-4-5",
        api_endpoint="https://api.anthropic.com",
        auth_token="deffa90ca00e4a7f8aa2fe432a318fde.tqOx4JHVOTtMLfzE",  # NEW
        token_tracking_enabled=True,
        session_id="abc123def456",
        operation_type="scanner",
        session_status="new"
    )
    # Banner displays without errors
    assert True
```

**Step 2: Update remaining SessionBanner tests**

Update all 6 tests in `TestSessionBanner` class to include `auth_token` parameter:
- `test_display_with_new_session`: add `auth_token="test_token_12345"`
- `test_display_without_token_tracking`: add `auth_token="test_token"`
- `test_display_with_no_session_id`: add `auth_token=None`
- `test_display_truncates_long_session_id`: add `auth_token="a" * 50`
- `test_display_with_custom_api_endpoint`: add `auth_token="custom_token"`

**Step 3: Run SessionBanner tests**

Run: `pytest tests/test_cli_banner.py::TestSessionBanner -v`
Expected: All 6 tests pass

**Step 4: Commit**

```bash
git add tests/test_cli_banner.py
git commit -m "test: update SessionBanner tests to include auth_token parameter"
```

---

## Task 5: Add Auth Token Masking Tests

**Files:**
- Modify: `tests/test_cli_banner.py` (add new tests after TestSessionBanner)
- Test: `pytest tests/test_cli_banner.py -v -k "auth_token"`

**Step 1: Add test for masked token display**

Add new test to `TestSessionBanner` class:

```python
def test_display_with_masked_auth_token(self):
    """Test that auth token is properly masked."""
    SessionBanner.display(
        model="claude-sonnet-4-5",
        api_endpoint="https://api.anthropic.com",
        auth_token="deffa90ca00e4a7f8aa2fe432a318fde.tqOx4JHVOTtMLfzE",
        token_tracking_enabled=True,
        session_id="test123",
        operation_type="scanner",
        session_status="new"
    )
    # Should display as: deffa90c...LfzE
    assert True
```

**Step 2: Add test for missing auth token**

Add another test:

```python
def test_display_with_missing_auth_token(self):
    """Test that missing auth token shows 'Not configured'."""
    SessionBanner.display(
        model="claude-sonnet-4-5",
        api_endpoint="https://api.anthropic.com",
        auth_token=None,
        token_tracking_enabled=True,
        session_id="test123",
        operation_type="scanner",
        session_status="new"
    )
    # Should display as: Not configured
    assert True
```

**Step 3: Add test for short auth token**

Add edge case test:

```python
def test_display_with_short_auth_token(self):
    """Test that short auth token (< 12 chars) is handled."""
    SessionBanner.display(
        model="claude-sonnet-4-5",
        api_endpoint="https://api.anthropic.com",
        auth_token="short123",
        token_tracking_enabled=True,
        session_id="test123",
        operation_type="scanner",
        session_status="new"
    )
    # Should display as: shor...23
    assert True
```

**Step 4: Run auth token tests**

Run: `pytest tests/test_cli_banner.py -v -k "auth_token"`
Expected: All 3 new tests pass

**Step 5: Commit**

```bash
git add tests/test_cli_banner.py
git commit -m "test: add auth token masking tests"
```

---

## Task 6: Update show_session_banner Tests

**Files:**
- Modify: `tests/test_cli_banner.py:90-220` (all TestShowSessionBanner tests)
- Test: `pytest tests/test_cli_banner.py::TestShowSessionBanner -v`

**Step 1: Update all show_session_banner tests to expect auth_token parameter**

In `tests/test_cli_banner.py`, find all `mock_display.assert_called_once_with()` calls and add `auth_token` parameter.

Example for `test_show_banner_with_new_session`:

```python
@patch('src.agent.cli_banner.SessionBanner.display')
async def test_show_banner_with_new_session(self, mock_display, temp_db):
    """Test banner with new session."""
    session_manager = SessionManager(temp_db)
    await session_manager.init_db()

    await show_session_banner(
        operation_type="scanner",
        model="claude-sonnet-4-5",
        session_manager=session_manager
    )

    mock_display.assert_called_once_with(
        model="claude-sonnet-4-5",
        api_endpoint=ANY,  # Will be ANTHROPIC_BASE_URL from config
        auth_token=ANY,     # NEW - will be ANTHROPIC_AUTH_TOKEN from config
        token_tracking_enabled=ANY,
        session_id=None,
        operation_type="scanner",
        session_status="new"
    )
```

**Step 2: Update all 10 tests in TestShowSessionBanner class**

Add `auth_token=ANY` to all `mock_display.assert_called_once_with()` assertions.

**Step 3: Run show_session_banner tests**

Run: `pytest tests/test_cli_banner.py::TestShowSessionBanner -v`
Expected: All 10 tests pass

**Step 4: Commit**

```bash
git add tests/test_cli_banner.py
git commit -m "test: update show_session_banner tests to expect auth_token parameter"
```

---

## Task 7: Update Integration Tests

**Files:**
- Modify: `tests/test_main_banner_integration.py` (all 5 tests)
- Test: `pytest tests/test_main_banner_integration.py -v`

**Step 1: Update all integration test mocks to include auth_token**

In `tests/test_main_banner_integration.py`, update all `mock_display.assert_called_once_with()` to add `auth_token=ANY`.

Example for `test_analyze_command_shows_banner`:

```python
@patch('src.agent.cli_banner.SessionBanner.display')
@patch('src.agent.main.TradingAgent')
async def test_analyze_command_shows_banner(self, mock_agent, mock_display, cli_runner, temp_db):
    """Test that analyze command displays session banner."""
    # ... setup code ...

    mock_display.assert_called_once_with(
        model="claude-sonnet-4-5",
        api_endpoint=ANY,
        auth_token=ANY,  # NEW
        token_tracking_enabled=ANY,
        session_id=ANY,
        operation_type=SessionManager.ANALYSIS,
        session_status=ANY
    )
```

**Step 2: Update all 5 integration tests**

Add `auth_token=ANY` parameter to all integration tests:
- `test_analyze_command_shows_banner`
- `test_monitor_command_shows_banner`
- `test_paper_monitor_command_shows_banner`
- `test_scan_movers_command_shows_banner`
- `test_banner_timing_in_analyze`

**Step 3: Run integration tests**

Run: `pytest tests/test_main_banner_integration.py -v`
Expected: All 5 tests pass

**Step 4: Commit**

```bash
git add tests/test_main_banner_integration.py
git commit -m "test: update integration tests to expect auth_token parameter"
```

---

## Task 8: End-to-End Manual Testing

**Files:**
- Test: Manual validation with actual .env values
- Document: Verify banner output

**Step 1: Run all automated tests**

Run: `pytest tests/ -q`
Expected: All 234 tests pass

**Step 2: Test scan_movers command with actual .env**

Run: `python -m src.agent.main scan-movers --help`
Expected: Help displays, no errors

**Step 3: Verify banner displays correct values (visual check)**

Run scanner briefly and check banner shows:
- API Endpoint: `https://api.z.ai/api/anthropic` (from .env)
- Auth Token: `deffa90c...LfzE` (masked from .env)

Note: This requires actually running the command, so just verify --help works without errors

**Step 4: Test with missing env vars**

Run: `ANTHROPIC_BASE_URL="" ANTHROPIC_AUTH_TOKEN="" python -m src.agent.main scan-movers --help`
Expected: Command works, would show defaults if banner ran

**Step 5: Final commit**

```bash
git add -A
git commit -m "test: verify end-to-end functionality with actual .env values"
```

---

## Completion Checklist

- [ ] Config fields updated (ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN)
- [ ] SessionBanner.display() adds auth_token parameter
- [ ] SessionBanner displays masked auth token
- [ ] show_session_banner() reads new config fields
- [ ] All SessionBanner unit tests updated (6 tests)
- [ ] Auth token masking tests added (3 tests)
- [ ] show_session_banner tests updated (10 tests)
- [ ] Integration tests updated (5 tests)
- [ ] End-to-end manual testing completed
- [ ] All 234 tests passing
- [ ] Banner displays correct .env values

**Total commits:** 8
**Estimated time:** 30-40 minutes
