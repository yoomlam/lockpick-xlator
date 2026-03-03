---
title: Fix slash command flow — audit findings
type: fix
status: completed
date: 2026-03-03
brainstorm: docs/brainstorms/2026-03-03-slash-command-flow-audit.md
---

# Fix Slash Command Flow — Audit Findings

## Overview

Nine targeted edits across five command files, fixing UX gaps, logic bugs, cross-command inconsistencies, and stale documentation. No new commands, no structural changes — just making the pipeline work as documented.

## Changes by File

### 1. `.claude/commands/new-domain.md`

#### 1a. Extend next-steps output (Step 2)

**Problem:** "Next steps" shows only 4 of 6 pipeline steps. A new user following the output believes they're done after `/extract-ruleset` when they still need to create tests and transpile.

**Fix:** Add steps 5 and 6 to the printed block:

```
Next steps:
  1. Add .md policy documents to domains/<domain>/input/policy_docs/
  2. Run /index-inputs <domain> to build a document index
  3. Run /refine-guidance <domain> to set extraction goals
  4. Run /extract-ruleset <domain> to extract the CIVIL ruleset
  5. Run /create-tests <domain> to draft the test suite
  6. Run /transpile-and-test <domain> to compile to Rego and validate
```

#### 1b. Create stub `demo/start.sh` (Step 1)

**Problem:** Step 1 creates `domains/<domain>/demo/` but no `start.sh`. The `<domain>-demo` Makefile target (scaffolded by `/transpile-and-test`) runs `bash domains/<domain>/demo/start.sh` — which fails immediately on a fresh domain. The stub is placed in `/new-domain` (domain setup time) rather than `/transpile-and-test` (Makefile scaffold time) so that `demo/` always contains a runnable, if placeholder, script regardless of pipeline stage.

**Fix:** In Step 1's "Create folder structure" block, also write a stub file:

```bash
domains/<domain>/demo/start.sh
```

Content of the stub:
```bash
#!/usr/bin/env bash
# Demo script for <domain>
# TODO: implement a sample OPA query against the running server
# Example: curl -s http://localhost:8181/v1/data/<domain>/eligibility/decision -d @- <<'EOF'
# { "input": { "household_size": 3, "gross_monthly_income": 1800 } }
# EOF
echo "No demo implemented yet for <domain>."
```

Update the printed structure output to include the new file:
```
Created domains/<domain>/
  input/policy_docs/    ← add .md policy documents here
  specs/
  output/
  demo/
    start.sh            ← stub demo script (edit to add sample queries)
```

---

### 2. `.claude/commands/index-inputs.md`

#### 2a. Fix "prompt then stop" → interactive domain selection (Pre-flight check 1)

**Problem:** Pre-flight check 1 says "List all directories... and prompt: 'Which domain?' Then stop." Prompting and stopping is contradictory.

**Fix:** Remove "Then stop." Change to interactive handling — list domains, await user selection, continue. Match the behavior of `/extract-ruleset`. Also update the Input section header (line 13) from `"prompt the user to choose"` to `"list available domains and prompt the user to choose; await response and continue"` so it stays consistent with the pre-flight.

Replace:
```
1. **Domain argument provided?**
   - NO → List all directories matching `domains/*/input/policy_docs/` and prompt: "Which domain? (provide as argument)" Then stop.
```

With:
```
1. **Domain argument provided?**
   - NO → List all directories matching `domains/*/input/policy_docs/` as a numbered menu and prompt:
     ```
     Available domains:
       1. snap
       2. example_domain
     Which domain? Enter a number or domain name:
     ```
     Await the user's response and use it as `<domain>`. Then continue.
```

---

### 3. `.claude/commands/refine-guidance.md`

#### 3a. Fix "prompt then stop" → interactive domain selection (Pre-flight check 1)

**Problem:** Same as `index-inputs` — pre-flight check 1 says "prompt... Then stop."

**Fix:** Same treatment — interactive numbered menu, await response, continue.

Replace:
```
1. **Domain argument provided?**
   - NO → List all directories matching `domains/*/` and prompt: "Which domain? (provide as argument)" Then stop.
```

With:
```
1. **Domain argument provided?**
   - NO → List all directories matching `domains/*/` as a numbered menu and prompt:
     ```
     Available domains:
       1. snap
       2. example_domain
     Which domain? Enter a number or domain name:
     ```
     Await the user's response and use it as `<domain>`. Then continue.
```

#### 3b. Unify inline `/index-inputs` prompt wording (Step 2)

**Problem:** The prompt to run `/index-inputs` inline uses `[index / continue]` option labels, which are non-obvious. `/extract-ruleset` uses the clearer `[y (recommended) / n — continue without index]`.

**Fix:** This wording appears twice — once in CREATE Step 2 and once in UPDATE Step 2. Replace both instances:

Replace (CREATE Step 2, and UPDATE Step 2 — same text in both):
```
Run /index-inputs <domain> first, or continue without doc analysis? [index / continue]:
```

With (in both locations):
```
Run /index-inputs <domain> now? [y (recommended) / n — continue without index]:
```

Also update the option handlers in both locations: replace `- \`index\` →` with `- **y** →` and `- \`continue\` →` with `- **n** →`.

---

### 4. `.claude/commands/extract-ruleset.md`

#### 4a. Move `ai-guidance.yaml` check before file selection (Pre-flight reorder)

**Problem:** Pre-flight step 5 (`ai-guidance.yaml` required check, hard stop if absent) comes *after* step 4 (expensive multi-file selection dialog). A user who hasn't run `/refine-guidance` goes through file selection, then hits a hard stop and must re-run `/refine-guidance` before returning.

**Fix:** Swap steps 4 and 5. New pre-flight order:

1. Domain folder exists?
2. Input docs present?
3. `<filename>` valid (if given)?
4. **Load `ai-guidance.yaml`** ← moved up (was step 5)
5. **Multiple input docs + no `<filename>`?** ← moved down (was step 4)

Renumber old step 5 as "4." and old step 4 as "5." in the file. No other text changes within either step — only the order and numbering change. The ai-guidance check now halts early before the selection dialog runs.

#### 4b. Remove `--force` reference (UPDATE Step 3)

**Problem:** UPDATE Step 3 ("No Changes — Exit Early") says `"Run with --force to re-extract regardless."` No `--force` flag is defined in the command signature.

**Fix:** Remove the sentence. Replace:
```
All input docs are up to date. Nothing to extract.
Run with --force to re-extract regardless.
```

With:
```
All input docs are up to date. Nothing to extract.
To re-extract anyway, delete or rename domains/<domain>/specs/extraction-manifest.yaml and re-run.
```

#### 4c. Fix output table — remove stale Makefile row

**Problem:** The output table at the bottom says:
```
| Makefile | Appended in pre-flight if no target existed | Not touched |
```

But `/extract-ruleset` has no Makefile-scaffolding steps. That logic is entirely in `/transpile-and-test`. The row is stale.

**Fix:** Remove the Makefile row from the output table.

---

### 5. `.claude/commands/transpile-and-test.md`

#### 5a. Fix package derivation example (Pre-flight check 2)

**Problem:** The example `"eligibility.snap_federal"` → `snap.eligibility` silently drops `_federal` without explanation. The CIVIL schema uses `module: "eligibility.<domain>"` (e.g., `"eligibility.snap"`) and the Makefile package is `<domain>.<program>` — a simple reversal of the two segments, no truncation.

**Fix:** Replace the full sentence (include enough context to locate it unambiguously):

Replace:
```
derive from its `module:` field (e.g., `"eligibility.snap_federal"` → `snap.eligibility`). Otherwise use `<domain>.<program>` as a placeholder.
```

With:
```
derive from its `module:` field by reversing the two dot-separated segments (e.g., `module: "eligibility.snap"` in domain `snap` → package `snap.eligibility`). Otherwise use `<domain>.<program>` as a placeholder.
```

---

## Acceptance Criteria

- [x] `/new-domain` next-steps output includes all 6 pipeline steps
- [x] `/new-domain` creates `domains/<domain>/demo/start.sh`
- [x] After running `/transpile-and-test <domain>`, `make <domain>-demo` exits 0 (prints the placeholder message, no error)
- [x] `/index-inputs` with no `<domain>` arg lists available domains interactively and continues (does not stop)
- [x] `/refine-guidance` with no `<domain>` arg does the same
- [x] `/refine-guidance` inline `/index-inputs` prompt uses `[y (recommended) / n — continue without index]` wording
- [x] `/extract-ruleset` pre-flight halts on missing `ai-guidance.yaml` *before* displaying the file selection dialog
- [x] `/extract-ruleset` UPDATE Step 3 no longer references `--force`
- [x] `/extract-ruleset` output table has no Makefile row
- [x] `/transpile-and-test` package derivation example is accurate and explains the reversal logic

## Files Changed

| File | Changes |
|------|---------|
| `.claude/commands/new-domain.md` | Extend next-steps; add demo/start.sh creation |
| `.claude/commands/index-inputs.md` | Interactive domain selection |
| `.claude/commands/refine-guidance.md` | Interactive domain selection; unify inline prompt wording |
| `.claude/commands/extract-ruleset.md` | Reorder pre-flight; remove --force; fix output table |
| `.claude/commands/transpile-and-test.md` | Fix package derivation example |

## Notes

- All changes are confined to `.claude/commands/*.md` files — no code changes
- No new commands, no structural changes to existing commands
- Test by manually tracing through each command's flow after edits
