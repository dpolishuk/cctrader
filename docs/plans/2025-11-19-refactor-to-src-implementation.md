# Refactor to src/ Directory Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move agent/ to src/agent/ and update all imports from agent.* to src.agent.*

**Architecture:** Structural refactoring with no logic changes. Uses git mv to preserve history, automated sed for bulk import updates, manual verification for critical files.

**Tech Stack:** Python 3.12, pytest, git, sed

---

## Task 1: Merge Bundled Tools Worktree

**Files:**
- Merge from: `/home/deepol/work/cctrader/.worktrees/scanner-timeout` (fix/scanner-timeout branch)
- Target: main branch

**Step 1: Switch to main branch and check status**

Run:
```bash
cd /home/deepol/work/cctrader
git checkout main
git status
```

Expected: Clean working tree on main branch

**Step 2: Merge scanner-timeout branch**

Run:
```bash
git merge fix/scanner-timeout --no-ff -m "feat: merge bundled tools from scanner-timeout branch

Includes:
- fetch_technical_snapshot and fetch_sentiment_data bundled tools
- Scanner configuration to use only bundled tools
- System prompt optimized for 3-step workflow
- Timeout increased to 120s

Merge before refactoring to consolidate changes."
```

Expected: Merge succeeds, possibly with conflicts

**Step 3: If conflicts occur, resolve them**

Common conflict locations:
- `agent/main.py` - Keep bundled tools version
- `.mcp.json` - Keep bundled tools version

Run after resolving:
```bash
git add <conflicted-files>
git merge --continue
```

**Step 4: Verify merge worked**

Run:
```bash
python -m agent.main --help
pytest tests/test_scanner_bundled_tools.py -v
```

Expected: Help displays, 4/4 bundled tools tests pass

**Step 5: Return to refactor worktree**

Run:
```bash
cd /home/deepol/work/cctrader/.worktrees/refactor-src
git pull origin main  # Pull merged changes into worktree
```

Expected: Worktree updated with merged changes

---

## Task 2: Create Backup Branch

**Files:**
- Create: New branch `backup-before-refactor`

**Step 1: Create backup branch**

Run:
```bash
git checkout -b backup-before-refactor
```

Expected: New branch created

**Step 2: Return to refactor branch**

Run:
```bash
git checkout refactor/move-to-src
```

Expected: Back on refactor branch

---

## Task 3: Move agent/ to src/agent/

**Files:**
- Move: `agent/` → `src/agent/`
- Create: `src/__init__.py`

**Step 1: Create src directory**

Run:
```bash
mkdir -p src
```

Expected: `src/` directory exists

**Step 2: Create src/__init__.py**

Run:
```bash
touch src/__init__.py
```

Expected: Empty `src/__init__.py` file created

**Step 3: Move agent directory using git**

Run:
```bash
git mv agent src/agent
```

Expected: `agent/` moved to `src/agent/`, git tracks as rename

**Step 4: Verify move**

Run:
```bash
ls -la src/agent/
git status
```

Expected:
- `src/agent/` contains all files
- Git shows `renamed: agent/... -> src/agent/...`

**Step 5: Commit directory move**

Run:
```bash
git add src/__init__.py
git commit -m "refactor: move agent/ to src/agent/

Preserves git history with git mv.
No logic changes, pure structural refactoring.

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Expected: Commit succeeds with SHA

---

## Task 4: Update Imports in Source Files (Automated)

**Files:**
- Modify: All `*.py` files in `src/`, `tests/`, `scripts/`

**Step 1: Run automated import updates**

Run:
```bash
# Update "from agent." imports
find src tests scripts -name "*.py" -type f 2>/dev/null | while read f; do
  sed -i 's/from agent\./from src.agent./g' "$f"
done

# Update "import agent." imports
find src tests scripts -name "*.py" -type f 2>/dev/null | while read f; do
  sed -i 's/import agent\./import src.agent./g' "$f"
done
```

Expected: All imports updated automatically

**Step 2: Check what was changed**

Run:
```bash
git diff --stat
```

Expected: Shows many files modified with import changes

**Step 3: Verify no syntax errors**

Run:
```bash
python -m py_compile src/agent/main.py
python -m py_compile src/agent/trading_agent.py
python -m py_compile tests/test_scanner_bundled_tools.py
```

Expected: No syntax errors

**Step 4: Look for any missed imports**

Run:
```bash
grep -r "from agent\." src/ tests/ scripts/ --include="*.py" 2>/dev/null || echo "None found"
grep -r "import agent\." src/ tests/ scripts/ --include="*.py" 2>/dev/null || echo "None found"
```

Expected: "None found" (or only comments)

**Step 5: Commit import updates**

Run:
```bash
git add -A
git commit -m "refactor: update all imports to src.agent.*

Automated update using sed:
- from agent.* → from src.agent.*
- import agent.* → import src.agent.*

Applied to all Python files in src/, tests/, scripts/

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Expected: Commit succeeds

---

## Task 5: Handle Dynamic Imports

**Files:**
- Modify: Any files with `importlib.import_module()` or `__import__()`

**Step 1: Search for dynamic imports**

Run:
```bash
grep -rn "importlib.import_module" src/ --include="*.py"
grep -rn "__import__" src/ --include="*.py" | grep -v "# "
```

Expected: List of files with dynamic imports (if any)

**Step 2: Update dynamic imports manually**

For each file found, update:

```python
# OLD
module = importlib.import_module("agent.tools.market_data")
pkg = __import__("agent")

# NEW
module = importlib.import_module("src.agent.tools.market_data")
pkg = __import__("src.agent")
```

**Step 3: If no dynamic imports found, skip**

If grep returns nothing, document:

Run:
```bash
echo "No dynamic imports found" > dynamic_imports_check.txt
git add dynamic_imports_check.txt
git commit -m "docs: verify no dynamic imports need updating"
```

**Step 4: If dynamic imports found and updated, commit**

Run:
```bash
git add <modified-files>
git commit -m "refactor: update dynamic imports to src.agent.*

Updated importlib.import_module() and __import__() calls.

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: Update Entry Points and Configuration

**Files:**
- Modify: `.mcp.json` (if exists)
- Modify: `setup.py` or `pyproject.toml` (if exists)
- Modify: `README.md`

**Step 1: Check for setup.py or pyproject.toml**

Run:
```bash
ls -la setup.py pyproject.toml 2>/dev/null || echo "No package config found"
```

**Step 2: If setup.py exists, update entry points**

Edit `setup.py` to change:
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

**Step 3: If pyproject.toml exists, update**

Edit `pyproject.toml` to change:
```toml
# OLD
[project.scripts]
cctrader = "agent.main:cli"

# NEW
[project.scripts]
cctrader = "src.agent.main:cli"
```

**Step 4: Update .mcp.json if it references agent**

Run:
```bash
grep -q "agent\." .mcp.json 2>/dev/null && echo "needs update" || echo "ok or not found"
```

If needs update, edit `.mcp.json` to change:
```json
{
  "command": "python",
  "args": ["-m", "src.agent.main"]
}
```

**Step 5: Update README.md usage examples**

Edit `README.md` to update all command examples:

```markdown
# OLD
python -m agent.main scan-movers --interval 60

# NEW
python -m src.agent.main scan-movers --interval 60
```

Update all occurrences in README.md

**Step 6: Commit configuration changes**

Run:
```bash
git add setup.py pyproject.toml .mcp.json README.md 2>/dev/null
git commit -m "refactor: update entry points and configuration

Changes:
- Updated setup.py/pyproject.toml entry points
- Updated .mcp.json command references
- Updated README.md usage examples

New entry point: python -m src.agent.main

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Expected: Commit succeeds

---

## Task 7: Update Documentation

**Files:**
- Modify: All `*.md` files in `docs/`

**Step 1: Find all markdown files with old imports**

Run:
```bash
grep -r "python -m agent\." docs/ --include="*.md" || echo "None found"
grep -r "from agent\." docs/ --include="*.md" || echo "None found"
```

**Step 2: Update markdown files**

For each file found, update code examples:

```markdown
# OLD
python -m agent.main scan-movers

# NEW
python -m src.agent.main scan-movers
```

**Step 3: Update architecture diagrams or references**

Check for any architecture docs mentioning `agent/` structure:

Run:
```bash
grep -r "agent/" docs/ --include="*.md" | grep -v "src/agent"
```

Update any outdated references

**Step 4: Commit documentation updates**

Run:
```bash
git add docs/
git commit -m "docs: update all examples to use src.agent.main

Updated:
- Command examples in docs/
- Import examples in guides
- Architecture references

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Expected: Commit succeeds

---

## Task 8: Update Scripts

**Files:**
- Modify: All `*.sh` and `*.py` files in `scripts/`

**Step 1: Check scripts directory**

Run:
```bash
ls -la scripts/ 2>/dev/null || echo "No scripts directory"
```

**Step 2: Search for agent references in scripts**

Run:
```bash
grep -r "agent\." scripts/ 2>/dev/null || echo "None found"
grep -r "python -m agent" scripts/ 2>/dev/null || echo "None found"
```

**Step 3: Update scripts if needed**

For shell scripts using `python -m agent.main`:
```bash
# OLD
python -m agent.main scan-movers

# NEW
python -m src.agent.main scan-movers
```

For Python scripts importing agent:
```python
# Already updated by Task 4 automated sed
```

**Step 4: If scripts found and updated, commit**

Run:
```bash
git add scripts/
git commit -m "refactor: update scripts to use src.agent.main

Updated shell scripts and Python scripts to use new entry point.

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**Step 5: If no scripts found, document**

Run:
```bash
echo "No scripts needed updating" > scripts_check.txt
git add scripts_check.txt
git commit -m "docs: verify scripts updated"
```

---

## Task 9: Verification - Import Tests

**Files:**
- None (verification only)

**Step 1: Test critical module imports**

Run:
```bash
python -c "from src.agent.main import cli; print('✓ main.py')"
python -c "from src.agent.trading_agent import TradingAgent; print('✓ trading_agent.py')"
python -c "from src.agent.scanner.tools import fetch_technical_snapshot; print('✓ scanner tools')"
python -c "from src.agent.tools.market_data import fetch_market_data; print('✓ market data')"
python -c "from src.agent.database.models import Signal; print('✓ database models')"
```

Expected: All print "✓ <module>" with no errors

**Step 2: If import errors occur, investigate**

If any import fails:
1. Check the error message
2. Look for missed import updates
3. Fix manually
4. Commit fix
5. Re-run verification

**Step 3: Document import verification**

Run:
```bash
echo "✓ All module imports verified" > import_verification.txt
git add import_verification.txt
git commit -m "test: verify all imports work after refactoring"
```

---

## Task 10: Verification - Run Tests

**Files:**
- None (verification only)

**Step 1: Run full test suite**

Run:
```bash
pytest tests/ -v --tb=short
```

Expected:
- Same pass/fail as baseline (36 passing)
- Bundled tools tests pass (4/4)
- Pre-existing failures unchanged

**Step 2: If new test failures, investigate**

If tests fail that passed before:
1. Check error messages for import errors
2. Look for missed import updates in test files
3. Fix and re-run
4. Commit fix

**Step 3: Run bundled tools tests specifically**

Run:
```bash
pytest tests/test_scanner_bundled_tools.py -v
```

Expected: 4/4 PASSED

**Step 4: Document test results**

Run:
```bash
pytest tests/ -v --tb=short > test_results.txt 2>&1
git add test_results.txt
git commit -m "test: verify test suite after refactoring

Baseline: 36 passing, 1 failed, 7 errors (pre-existing)
Bundled tools: 4/4 passing

No new test failures introduced by refactoring."
```

---

## Task 11: Verification - CLI Integration Test

**Files:**
- None (verification only)

**Step 1: Test help command**

Run:
```bash
python -m src.agent.main --help
```

Expected: Help text displays with all commands

**Step 2: Test each command's help**

Run:
```bash
python -m src.agent.main scan-movers --help
python -m src.agent.main analyze --help
python -m src.agent.main monitor --help
python -m src.agent.main signals --help
python -m src.agent.main status --help
```

Expected: Each command's help displays

**Step 3: Run quick integration test (scan 1 cycle)**

Run:
```bash
timeout 180 python -m src.agent.main scan-movers --interval 120 2>&1 | tee integration_test.log
```

Expected:
- Scanner starts
- Completes at least 1 analysis
- No import errors
- Signals submitted (if movers found)

**Step 4: Check integration test logs**

Run:
```bash
grep -i "error\|exception\|traceback" integration_test.log && echo "Errors found!" || echo "Clean run"
```

Expected: "Clean run" (no unexpected errors)

**Step 5: Document integration test**

Run:
```bash
git add integration_test.log
git commit -m "test: verify CLI integration after refactoring

Ran scanner for 1 cycle, no import errors detected.
Entry point python -m src.agent.main works correctly.

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 12: Final Cleanup and Documentation

**Files:**
- Modify: `docs/plans/2025-11-19-refactor-to-src-directory-design.md`
- Remove: Temporary verification files

**Step 1: Remove temporary verification files**

Run:
```bash
rm -f dynamic_imports_check.txt scripts_check.txt import_verification.txt test_results.txt integration_test.log
```

Expected: Temporary files removed

**Step 2: Update design doc with results**

Add to end of `docs/plans/2025-11-19-refactor-to-src-directory-design.md`:

```markdown
## Implementation Results

**Implementation Date:** 2025-11-19

**Status:** ✅ COMPLETE

**Changes:**
- Moved: `agent/` → `src/agent/`
- Updated: 30+ files with import changes
- Entry point: `python -m agent.main` → `python -m src.agent.main`

**Verification:**
- ✅ All module imports work
- ✅ Test suite: 36 passing (baseline maintained)
- ✅ Bundled tools tests: 4/4 passing
- ✅ CLI integration test: Clean run
- ✅ No import errors detected

**Git History:**
- 11 commits from bundled tools merge
- 8 commits for refactoring
- Clean history with `git mv` preserving file history
```

**Step 3: Commit documentation update**

Run:
```bash
git add docs/plans/2025-11-19-refactor-to-src-directory-design.md
git commit -m "docs: add implementation results to refactor design

Refactoring complete:
- All imports updated to src.agent.*
- Tests passing
- CLI working
- No errors detected

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**Step 4: Create final summary commit**

Run:
```bash
git commit --allow-empty -m "refactor: complete move to src/ directory

Summary:
- Merged bundled tools from scanner-timeout branch
- Moved agent/ to src/agent/
- Updated all imports: agent.* → src.agent.*
- Updated entry points and documentation
- All tests passing (36 passing, 4/4 bundled tools)

New usage: python -m src.agent.main scan-movers

Ready for merge to main.

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Summary

**Total Tasks:** 12

**Implementation Flow:**
1. Merge bundled tools worktree → Prepare codebase
2. Create backup branch → Safety net
3. Move directory with git mv → Preserve history
4. Automated import updates → Bulk changes
5. Handle dynamic imports → Edge cases
6. Update configurations → Entry points
7. Update documentation → User-facing changes
8. Update scripts → Automation
9-11. Three-phase verification → Import, tests, integration
12. Cleanup and document → Finalize

**Estimated Time:** 60-75 minutes

**Success Criteria:**
- ✅ All imports resolve without errors
- ✅ Test suite maintains baseline (36 passing)
- ✅ Bundled tools tests pass (4/4)
- ✅ CLI runs successfully (python -m src.agent.main)
- ✅ Integration test completes 1 scan cycle
- ✅ No old `agent.*` imports remain
- ✅ Documentation updated

**Rollback:** Backup branch `backup-before-refactor` available if needed
