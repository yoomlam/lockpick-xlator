---
title: chore: Migrate setup instructions to use uv
type: chore
status: active
date: 2026-02-23
---

# Migrate Setup Instructions to Use `uv`

Update all developer-facing instructions and scripts to use `uv` (Astral's fast Python package manager) instead of bare `pip`, and add an explicit virtual environment creation and activation step.

## Context

The project currently instructs developers to run `pip install -r demo/requirements.txt` with no virtual environment setup, which pollutes the system or user Python environment. `uv` is a modern, significantly faster replacement for `pip`/`virtualenv` that provides unified venv + package management. Migrating to it improves onboarding reproducibility and aligns with current Python tooling best practices.

## Acceptance Criteria

- [ ] `docs/snap-demo-script.md` Prerequisites section replaced with `uv`-based workflow (`uv venv`, `source .venv/bin/activate`, `uv pip install`)
- [ ] `demo/start.sh` prerequisite comment updated to reference `uv`
- [ ] `.claude/settings.local.json` updated: `uv` command added to allow-list, `pip install` entry replaced
- [ ] `.gitignore` already excludes `.venv/` — verify and add if missing

## Files to Change

| File | Change |
|---|---|
| [`docs/snap-demo-script.md`](docs/snap-demo-script.md) | Replace Prerequisites block (lines 21–41) with `uv` workflow |
| [`demo/start.sh`](demo/start.sh) | Update prerequisite comment (line 10) |
| [`.claude/settings.local.json`](.claude/settings.local.json) | Add `Bash(uv:*)`, replace `Bash(pip install:*)` |
| [`.gitignore`](.gitignore) | Add `.venv/` if not already present |

## Implementation

### 1. `docs/snap-demo-script.md` — Prerequisites section

Replace:
```bash
# Python 3.11+
python --version

# Demo Python packages
pip install -r demo/requirements.txt
```

With:
```bash
# Python 3.11+ and uv
python --version
brew install uv   # or: curl -LsSf https://astral.sh/uv/install.sh | sh

# Create and activate virtual environment
uv venv
source .venv/bin/activate

# Install demo Python packages
uv pip install -r demo/requirements.txt
```

Also update the Optional section from:
```bash
pip install pyyaml   # already included in demo/requirements.txt
```
To:
```bash
uv pip install pyyaml   # already included in demo/requirements.txt
```

### 2. `demo/start.sh` — Prerequisite comment

Replace line 10:
```bash
#   - Python deps installed (pip install -r demo/requirements.txt)
```
With:
```bash
#   - Python deps installed (uv venv && source .venv/bin/activate && uv pip install -r demo/requirements.txt)
```

### 3. `.claude/settings.local.json` — Allow-list

Replace `"Bash(pip install:*)"` with `"Bash(uv:*)"`.

### 4. `.gitignore` — Verify `.venv/` exclusion

Check whether `.venv/` is already excluded. If not, add it.

## Verification

After implementing:
1. `grep -r "pip install" docs/ demo/` should return no results
2. `grep -r "uv" docs/snap-demo-script.md` should show the new commands
3. Follow the updated Prerequisites section manually: `uv venv && source .venv/bin/activate && uv pip install -r demo/requirements.txt` — should succeed
4. `bash demo/start.sh` should work with the activated venv (uvicorn must be in PATH via venv)

## Notes

- The `.venv/` directory should be created at repo root (default `uv venv` location), not inside `demo/`
- `source .venv/bin/activate` is macOS/Linux syntax; Windows users would use `.venv\Scripts\activate`
- No need for a `pyproject.toml` — keeping `requirements.txt` is fine since `uv pip install -r` supports it directly
