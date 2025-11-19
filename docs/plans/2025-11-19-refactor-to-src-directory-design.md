# Refactor to src/ Directory Design

**Date:** 2025-11-19
**Status:** Approved
**Goal:** Reorganize codebase by moving `src/agent/` to `src/agent/` with updated import paths

## Overview and Strategy

**Refactoring Scope:**
- Move: `src/agent/` directory → `src/agent/`
- Update: All imports from `agent.*` → `src.agent.*`
- Update: Entry point from `python -m src.agent.main` → `python -m src.agent.main`
- Keep at root: `tests/`, `docs/`, `scripts/`, config files

**Pre-requisite Step:** Merge `fix/scanner-timeout` worktree into main before starting refactoring. This ensures we refactor the final codebase with bundled tools included.

**Why This Approach:**
- Single refactoring pass on complete codebase (more efficient)
- Tests bundled tools in refactored structure immediately
- No rebase conflicts between refactoring and feature branches
- Clean commit history (merge, then refactor)

**Final Structure:**
```
cctrader/
├── src/
│   ├── __init__.py
│   └── agent/          # All source code here
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── tools/
│       ├── scanner/
│       ├── database/
│       └── paper_trading/
├── tests/              # Test files (unchanged location)
├── docs/               # Documentation (unchanged)
├── scripts/            # Helper scripts (unchanged)
├── .mcp.json           # MCP config (unchanged)
└── requirements.txt    # Dependencies (unchanged)
```

## Step 1: Merge Worktree Before Refactoring

**Merge bundled tools from worktree:**

Before refactoring, merge the `fix/scanner-timeout` branch into main:

```bash
# In main repo
cd /home/deepol/work/cctrader
git checkout main
git merge fix/scanner-timeout
```

**Expected merge contents:**
- 11 commits from bundled tools work
- New files: `src/agent/scanner/tools.py`, `tests/test_scanner_bundled_tools.py`
- Modified: `src/agent/main.py`, `src/agent/scanner/agent_wrapper.py`
- Changes: Bundled tools + 120s timeout

**Conflict Resolution:**
If conflicts occur (likely in `src/agent/main.py` or `.mcp.json`):
- Prioritize bundled tools version (worktree changes)
- Keep both import statements if different
- Verify with: `python -m src.agent.main --help` after merge

**Verification After Merge:**
1. Run bundled tools tests: `pytest tests/test_scanner_bundled_tools.py -v` (should pass 4/4)
2. Check scanner runs: `python -m src.agent.main scan-movers --help` (should work)
3. Verify no broken imports: `python -c "from src.agent.main import cli"`

**Why merge first:**
- Ensures refactoring includes all latest code
- Tests both bundled tools AND refactoring together
- Avoids rebase conflicts later

## Step 2: Directory Move

**Create src directory structure:**

```bash
# Create src directory
mkdir -p src

# Move agent directory
git mv agent src/agent

# Create src/__init__.py
touch src/__init__.py
```

**Git operations:**
- Use `git mv` to preserve history
- Commit immediately after move: `git commit -m "refactor: move agent/ to src/agent/"`
- This creates a clean history for the directory move

## Step 3: Update All Import Statements

**Files that need import updates (estimated 20-30 files):**

### Category 1: Source files (src/agent/)

Files to update:
- `src/agent/main.py` - imports from tools, scanner, database
- `src/agent/trading_agent.py` - imports from tools, database
- `src/agent/scanner/*.py` - imports from tools, parent modules
- `src/agent/tools/*.py` - internal imports
- `src/agent/database/*.py` - internal imports
- `src/agent/paper_trading/*.py` - imports from database, tools

**Import pattern changes:**
```python
# OLD
from src.agent.tools.market_data import fetch_market_data
from src.agent.scanner.agent_wrapper import AgentWrapper
from src.agent.database.models import Signal

# NEW
from src.agent.tools.market_data import fetch_market_data
from src.agent.scanner.agent_wrapper import AgentWrapper
from src.agent.database.models import Signal
```

### Category 2: Test files (tests/)

```python
# OLD
from src.agent.scanner.tools import fetch_technical_snapshot
import src.agent.main

# NEW
from src.agent.scanner.tools import fetch_technical_snapshot
import src.agent.main
```

### Category 3: Scripts (scripts/)

Any Python scripts that import agent modules need updating.

**Automation approach:**

Use find + sed to update imports systematically:
```bash
# Find all Python files and update imports
find src tests scripts -name "*.py" -type f -exec sed -i 's/from agent\./from src.agent./g' {} \;
find src tests scripts -name "*.py" -type f -exec sed -i 's/import agent\./import src.agent./g' {} \;
```

**Manual verification after automation:**
- Check critical files manually: `src/agent/main.py`, `tests/test_scanner_bundled_tools.py`
- Look for multiline imports that sed might miss
- Verify relative imports within src/agent/ still work

## Step 4: Update Entry Points

**Main entry point change:**

```bash
# OLD
python -m src.agent.main scan-movers --interval 60

# NEW
python -m src.agent.main scan-movers --interval 60
```

**Files to update with new entry point:**

### 1. Documentation (README.md, docs/)

Update all command examples:
- Quick start guide
- Usage examples
- Deployment instructions
- API documentation

### 2. Scripts (scripts/)

Update any shell scripts that invoke the agent:
- `scripts/websearch-daemon.sh` - check if it runs the agent
- Any deployment or automation scripts

### 3. Configuration files

**`.mcp.json`** - check for any hardcoded paths to agent modules:
```json
{
  "mcpServers": {
    "trading": {
      "command": "python",
      "args": ["-m", "src.agent.main"]  // Updated from src.agent.main
    }
  }
}
```

## Step 5: Update Package Configuration (if exists)

**Check for package configuration:**

```bash
ls setup.py pyproject.toml 2>/dev/null
```

**If setup.py exists, update entry points:**

```python
# OLD
entry_points={
    'console_scripts': [
        'cctrader=agent.main:cli',
    ],
}

# NEW
entry_points={
    'console_scripts': [
        'cctrader=src.agent.main:cli',
    ],
}
```

**If pyproject.toml exists, update:**

```toml
# OLD
[project.scripts]
cctrader = "agent.main:cli"

# NEW
[project.scripts]
cctrader = "src.agent.main:cli"
```

## Step 6: Relative Imports Strategy

**Within src/agent/, two import styles are valid:**

### Option 1: Absolute imports (recommended)
```python
# In src/agent/scanner/agent_wrapper.py
from src.agent.tools.market_data import fetch_market_data
from src.agent.database.models import Signal
```

**Pros:**
- Consistent with imports from tests/ and scripts/
- Clear where module is located
- Works everywhere

### Option 2: Relative imports
```python
# In src/agent/scanner/agent_wrapper.py
from ..tools.market_data import fetch_market_data
from ..database.models import Signal
```

**Pros:**
- Shorter
- Independent of src/ directory name

**Recommendation:** Use absolute imports (`src.agent.*`) for consistency and clarity throughout the codebase.

## Step 7: Verification and Testing

### Test 1: Import verification

```bash
# Verify all modules can be imported
python -c "from src.agent.main import cli; print('✓ main.py')"
python -c "from src.agent.scanner.tools import fetch_technical_snapshot; print('✓ scanner tools')"
python -c "from src.agent.tools.market_data import fetch_market_data; print('✓ market data')"
python -c "from src.agent.database.models import Signal; print('✓ database')"
```

### Test 2: Run unit tests

```bash
pytest tests/ -v
```

**Expected results:**
- All tests pass
- Especially: `tests/test_scanner_bundled_tools.py` (4/4)
- No import errors

### Test 3: CLI functionality

```bash
# Test help command
python -m src.agent.main --help

# Test each command works
python -m src.agent.main scan-movers --help
python -m src.agent.main analyze --help
python -m src.agent.main monitor --help

# Run quick integration test (1 scan cycle)
python -m src.agent.main scan-movers --interval 120
# Let it complete 1 analysis, then Ctrl+C
```

### Test 4: Check for missed imports

```bash
# Search for any remaining old imports
grep -r "from agent\." src/ tests/ scripts/ --include="*.py"
grep -r "import agent\." src/ tests/ scripts/ --include="*.py"

# Should return no results (or only comments)
```

## Edge Cases to Handle

### 1. Dynamic imports

If code uses dynamic imports, update them:

```python
# OLD
module = importlib.import_module("agent.tools.market_data")
pkg = __import__("agent")

# NEW
module = importlib.import_module("src.agent.tools.market_data")
pkg = __import__("src.agent")
```

**Find dynamic imports:**
```bash
grep -r "importlib.import_module" src/ --include="*.py"
grep -r "__import__" src/ --include="*.py"
```

### 2. String references to modules

Check for module paths referenced as strings:

- Config files with module paths
- Logging that references `__name__` (should still work)
- MCP server configurations
- Test fixtures that reference module names

### 3. IDE/Editor configurations

**VSCode** - `.vscode/settings.json`:
```json
{
  "python.analysis.extraPaths": ["src"]
}
```

**PyCharm** - mark `src/` as Sources Root:
- Right-click `src/` → Mark Directory as → Sources Root

## Rollback Plan

**Create backup before starting:**

```bash
# Before any refactoring
git checkout -b backup-before-refactor
git checkout main
```

**If refactoring fails:**

```bash
# Option 1: Reset to backup
git reset --hard backup-before-refactor

# Option 2: Revert specific commits
git revert <refactor-commit-sha>

# Option 3: Restore from backup branch
git checkout main
git reset --hard backup-before-refactor
git push -f origin main  # Only if pushed broken code
```

**When to rollback:**
- Import errors that can't be quickly fixed
- Tests failing due to import issues
- Scanner agent doesn't run
- More than 2 hours spent debugging imports

## Success Criteria

**Must pass all of these:**
- ✅ All imports resolve without errors
- ✅ All unit tests pass (especially bundled tools: 4/4)
- ✅ CLI runs: `python -m src.agent.main --help` works
- ✅ Scanner completes at least 1 full analysis cycle
- ✅ No old `agent.*` imports remain in codebase (grep returns empty)
- ✅ Documentation updated with new entry point
- ✅ Scripts updated and functional

**Quality checks:**
- ✅ Git history is clean (directory move in one commit, imports in another)
- ✅ All files formatted consistently
- ✅ No broken relative imports
- ✅ IDE recognizes src/ directory structure

## Implementation Order

**Phase 1: Preparation**
1. Merge `fix/scanner-timeout` worktree → main
2. Run all tests to confirm baseline works
3. Create backup branch

**Phase 2: Directory Move**
4. Create `src/` directory
5. `git mv agent src/agent`
6. Create `src/__init__.py`
7. Commit: "refactor: move agent/ to src/agent/"

**Phase 3: Import Updates**
8. Run automated sed commands on all Python files
9. Manually verify critical files
10. Fix any multiline imports missed by sed
11. Commit: "refactor: update all imports to src.agent.*"

**Phase 4: Configuration**
12. Update entry points in setup.py/pyproject.toml (if exists)
13. Update .mcp.json
14. Update documentation (README, docs/)
15. Update scripts/
16. Commit: "refactor: update entry points and configuration"

**Phase 5: Verification**
17. Run import verification commands
18. Run full test suite
19. Run CLI integration test (1 scan cycle)
20. Search for missed old imports

**Phase 6: Cleanup**
21. Remove backup branch if successful
22. Update any remaining documentation
23. Final commit: "docs: update refactoring documentation"

## Estimated Time

- Merge worktree: 5 minutes
- Directory move: 2 minutes
- Import updates (automated + manual verification): 15-20 minutes
- Configuration updates: 10 minutes
- Testing and verification: 15-20 minutes
- Documentation updates: 10 minutes

**Total: 60-75 minutes**

## Notes

- This is a **structural refactoring** - no logic changes
- Git history preserved with `git mv`
- All functionality remains identical
- Bundled tools from worktree included
- Entry point changes from `agent.main` → `src.agent.main`
