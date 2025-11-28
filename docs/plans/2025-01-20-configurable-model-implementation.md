# Configurable Model Name Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Claude model name configurable via CLAUDE_MODEL environment variable with default "glm-4.5".

**Architecture:** Add CLAUDE_MODEL field to config.py, update .env files, replace hardcoded model strings in main.py commands.

**Tech Stack:** Python 3.12, dotenv

---

## Task 1: Add CLAUDE_MODEL to Configuration

**Files:**
- Modify: `src/agent/config.py:52-55`
- Test: Manual verification

**Step 1: Add CLAUDE_MODEL field to Config class**

In `src/agent/config.py`, add after line 55 (after ANALYSIS_INTERVAL):

```python
# Agent Settings
MAX_TURNS: int = int(os.getenv("MAX_TURNS", "20"))
MAX_BUDGET_USD: float = float(os.getenv("MAX_BUDGET_USD", "1.0"))
ANALYSIS_INTERVAL: int = int(os.getenv("ANALYSIS_INTERVAL", "300"))
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "glm-4.5")  # NEW
```

**Step 2: Verify config loads correctly**

Run: `python -c "from src.agent.config import config; print(f'Model: {config.CLAUDE_MODEL}')"`
Expected: `Model: glm-4.5`

**Step 3: Commit**

```bash
git add src/agent/config.py
git commit -m "feat: add CLAUDE_MODEL configuration field"
```

---

## Task 2: Update .env File

**Files:**
- Modify: `.env:13`
- Test: Manual verification

**Step 1: Add CLAUDE_MODEL to .env**

In `.env`, add after ANALYSIS_INTERVAL line:

```bash
ANALYSIS_INTERVAL=900
CLAUDE_MODEL=glm-4.5
```

**Step 2: Verify environment variable**

Run: `python -c "from src.agent.config import config; print(f'Model: {config.CLAUDE_MODEL}')"`
Expected: `Model: glm-4.5`

**Step 3: Commit**

```bash
git add .env
git commit -m "config: add CLAUDE_MODEL to .env"
```

---

## Task 3: Update .env.example File

**Files:**
- Modify: `.env.example`
- Test: Manual verification

**Step 1: Add CLAUDE_MODEL to .env.example**

Find the section with MAX_TURNS, MAX_BUDGET_USD, ANALYSIS_INTERVAL and add:

```bash
MAX_TURNS=20
MAX_BUDGET_USD=1.0
ANALYSIS_INTERVAL=300
CLAUDE_MODEL=glm-4.5
```

**Step 2: Verify file structure**

Run: `grep CLAUDE_MODEL .env.example`
Expected: Shows the line with CLAUDE_MODEL=glm-4.5

**Step 3: Commit**

```bash
git add .env.example
git commit -m "config: add CLAUDE_MODEL to .env.example"
```

---

## Task 4: Update scan_movers Command

**Files:**
- Modify: `src/agent/main.py:460,477`
- Test: `python -m src.agent.main scan-movers --help`

**Step 1: Replace model in ClaudeAgentOptions**

In `src/agent/main.py`, find line 460 and change:

```python
# BEFORE (line 460):
model="claude-sonnet-4-5",

# AFTER:
model=config.CLAUDE_MODEL,
```

**Step 2: Replace model in show_session_banner call**

Find line 477 and change:

```python
# BEFORE (line 477):
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

**Step 3: Test scan_movers command**

Run: `python -m src.agent.main scan-movers --help`
Expected: Help displays without errors

**Step 4: Commit**

```bash
git add src/agent/main.py
git commit -m "feat: use config.CLAUDE_MODEL in scan_movers command"
```

---

## Task 5: Update analyze Command

**Files:**
- Modify: `src/agent/main.py:41-78`
- Test: `python -m src.agent.main analyze --help`

**Step 1: Add config import to analyze command**

In `src/agent/main.py`, in the `analyze` command async function (around line 47), after agent initialization, ensure config is imported:

```python
async def run():
    from src.agent.session_manager import SessionManager
    from src.agent.cli_banner import show_session_banner
    from src.agent.config import config  # Add if not present
```

**Step 2: Replace model in show_session_banner call**

Find the show_session_banner call in analyze command (around line 75) and change:

```python
# BEFORE:
await show_session_banner(
    operation_type=SessionManager.ANALYSIS,
    model="claude-sonnet-4-5",
    session_manager=session_manager
)

# AFTER:
await show_session_banner(
    operation_type=SessionManager.ANALYSIS,
    model=config.CLAUDE_MODEL,
    session_manager=session_manager
)
```

**Step 3: Test analyze command**

Run: `python -m src.agent.main analyze --help`
Expected: Help displays without errors

**Step 4: Commit**

```bash
git add src/agent/main.py
git commit -m "feat: use config.CLAUDE_MODEL in analyze command"
```

---

## Task 6: Update monitor Command

**Files:**
- Modify: `src/agent/main.py:23-43`
- Test: `python -m src.agent.main monitor --help`

**Step 1: Add config import to monitor command**

In `src/agent/main.py`, in the `monitor` command async function (around line 28), ensure config is imported:

```python
async def run():
    from src.agent.session_manager import SessionManager
    from src.agent.cli_banner import show_session_banner
    from src.agent.config import config  # Add if not present
```

**Step 2: Replace model in show_session_banner call**

Find the show_session_banner call in monitor command (around line 40) and change:

```python
# BEFORE:
await show_session_banner(
    operation_type=SessionManager.MONITOR,
    model="claude-sonnet-4-5",
    session_manager=session_manager
)

# AFTER:
await show_session_banner(
    operation_type=SessionManager.MONITOR,
    model=config.CLAUDE_MODEL,
    session_manager=session_manager
)
```

**Step 3: Test monitor command**

Run: `python -m src.agent.main monitor --help`
Expected: Help displays without errors

**Step 4: Commit**

```bash
git add src/agent/main.py
git commit -m "feat: use config.CLAUDE_MODEL in monitor command"
```

---

## Task 7: Update paper_monitor Command

**Files:**
- Modify: `src/agent/main.py:193-246`
- Test: `python -m src.agent.main paper-monitor --help`

**Step 1: Add config import to paper_monitor command**

In `src/agent/main.py`, in the `paper_monitor` command async function (around line 199), ensure config is imported:

```python
async def run():
    from src.agent.session_manager import SessionManager
    from src.agent.cli_banner import show_session_banner
    from src.agent.config import config  # Add if not present
```

**Step 2: Replace model in show_session_banner call**

Find the show_session_banner call in paper_monitor command (around line 243) and change:

```python
# BEFORE:
await show_session_banner(
    operation_type=SessionManager.PAPER_TRADING,
    model="claude-sonnet-4-5",
    session_manager=session_manager
)

# AFTER:
await show_session_banner(
    operation_type=SessionManager.PAPER_TRADING,
    model=config.CLAUDE_MODEL,
    session_manager=session_manager
)
```

**Step 3: Test paper_monitor command**

Run: `python -m src.agent.main paper-monitor --help`
Expected: Help displays without errors

**Step 4: Commit**

```bash
git add src/agent/main.py
git commit -m "feat: use config.CLAUDE_MODEL in paper_monitor command"
```

---

## Task 8: End-to-End Testing

**Files:**
- Test: All commands
- Verify: Configuration and banner display

**Step 1: Run all automated tests**

Run: `pytest tests/ -q`
Expected: All 237 tests pass

**Step 2: Test default model value**

Run: `python -c "from src.agent.config import config; print(f'Model: {config.CLAUDE_MODEL}')"`
Expected: `Model: glm-4.5`

**Step 3: Test custom model value**

Run: `CLAUDE_MODEL=custom-model python -c "from src.agent.config import config; print(f'Model: {config.CLAUDE_MODEL}')"`
Expected: `Model: custom-model`

**Step 4: Verify all commands work**

Run each command's help:
- `python -m src.agent.main scan-movers --help`
- `python -m src.agent.main analyze --help`
- `python -m src.agent.main monitor --help`
- `python -m src.agent.main paper-monitor --help`

Expected: All display help without errors

**Step 5: Final commit (if needed)**

```bash
git add -A
git commit -m "test: verify configurable model implementation"
```

---

## Completion Checklist

- [ ] CLAUDE_MODEL field added to config.py
- [ ] CLAUDE_MODEL added to .env
- [ ] CLAUDE_MODEL added to .env.example
- [ ] scan_movers command uses config.CLAUDE_MODEL
- [ ] analyze command uses config.CLAUDE_MODEL
- [ ] monitor command uses config.CLAUDE_MODEL
- [ ] paper_monitor command uses config.CLAUDE_MODEL
- [ ] All tests pass (237 tests)
- [ ] Config loads with default "glm-4.5"
- [ ] Banner displays correct model name

**Total commits:** 7-8
**Estimated time:** 20-30 minutes
