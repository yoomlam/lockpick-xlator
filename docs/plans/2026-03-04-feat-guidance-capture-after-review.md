---
title: "feat: Add Sub-C Guidance Capture After Human Review Gate"
type: feat
status: completed
date: 2026-03-04
---

# feat: Add Sub-C Guidance Capture After Human Review Gate

## Overview

After the Human Review Gate is approved in both `extract-ruleset` and `update-ruleset`, add a shared sub-procedure that synthesizes candidate guidance items from review signals and offers them to the user for confirmation before appending to `ai-guidance.yaml`.

This closes the feedback loop between the review gate (where domain-specific extraction challenges surface) and the guidance file (which shapes future extractions).

## Proposed Solution

Add `Sub-C: Guidance Capture` to `core/ruleset-shared.md`. Rename the existing `Sub-C: Extraction Complete Footer` to `Sub-D`. Both commands invoke Sub-C after their final post-review step and before Sub-D.

## Files to Change

| File | Change |
|---|---|
| `core/ruleset-shared.md` | Add Sub-C; rename Sub-C footer → Sub-D |
| `.claude/commands/extract-ruleset.md` | Add `Run **Sub-C: Guidance Capture**.` after Step 7c; rename Sub-C call → Sub-D |
| `.claude/commands/update-ruleset.md` | Add `Run **Sub-C: Guidance Capture**.` after Step 9d; rename Sub-C call → Sub-D |

## Sub-C Specification

Add the following section to `core/ruleset-shared.md` between Sub-B and the renamed Sub-D:

---

### Sub-C: Guidance Capture

After the Human Review Gate is approved, synthesize candidate guidance items from the review session to improve future extractions.

**Step 1 — Collect signals.**

Gather everything that occurred during the Human Review Gate:
- Items that were rejected and re-extracted (original vs. accepted: what changed, and why?)
- Items in the Uncertain bucket (fidelity ≤2 or source_clarity ≤2) — even if ultimately accepted
- Items in the Complex bucket that had `notes:` fields
- Any corrections the user provided to CIVIL expressions, values, or notes

If none of these signals are present (all items verified, no corrections, no notes), proceed silently to Sub-D — no synthesis needed.

**Step 2 — Synthesize candidates.**

From the collected signals, draft up to 5 candidate guidance items total across all sections. For each item:
- Assign it to the most appropriate section (`constraints`, `standards`, `guidance`, or `edge_cases`)
- Write it as a concise, actionable statement (1–2 sentences)
- Check the corresponding section in `domains/<domain>/specs/ai-guidance.yaml` — if a semantically equivalent item already exists, skip this candidate

If zero candidates remain after deduplication, proceed silently to Sub-D.

**Step 3 — Offer to user.**

Print:
```
Based on your review, I have X suggestion(s) to add as AI guidance to improve future extractions.
Review them? [y/n]
```

- **n** → proceed to Sub-D.
- **Unrecognized input** → re-display and re-prompt.
- **y** → for each candidate in sequence, print:
  ```
  [<section>] "<candidate text>"
  Add this item? [y / n / edit]
  ```
  - **y** → record item for appending.
  - **n** → skip.
  - **edit** → print `Enter revised text (current: "<candidate text>"):` — accept the user's replacement text, then record it for appending.
  - **Unrecognized input** → re-display the per-item prompt and re-prompt.

**Step 4 — Write to file.**

After all candidates have been reviewed:
- Append each accepted item to its assigned section in `domains/<domain>/specs/ai-guidance.yaml`
- Update `generated_at` to today's date (write once, after all appends, not after each individual item)
- Preserve `source_template` and all other sections verbatim

If 1 or more items were added, print (use "item" for N=1, "items" for N>1):
```
Updated ai-guidance.yaml (+1 item)
Updated ai-guidance.yaml (+3 items)
```

Then proceed to Sub-D.

> **Note:** Items added by Sub-C are indistinguishable from items created by `/refine-guidance`. A subsequent run of `/refine-guidance <domain>` (UPDATE mode) will present them as existing content, allow refinement, and preserve them if not changed.

---

## Placement in Each Command

### extract-ruleset.md

Current order at the end of the flow:
```
Step 7c: Run **Sub-B: Generate Computation Graph**.
Run **Sub-C: Extraction Complete Footer**.
```

Updated order (literal text to add/change):
```
Step 7c: Run **Sub-B: Generate Computation Graph**.
Run **Sub-C: Guidance Capture**.
Run **Sub-D: Extraction Complete Footer**.
```

### update-ruleset.md

Current order at the end of the flow:
```
Step 9d: Run **Sub-B: Generate Computation Graph**.
Run **Sub-C: Extraction Complete Footer**.
```

Updated order (literal text to add/change):
```
Step 9d: Run **Sub-B: Generate Computation Graph**.
Run **Sub-C: Guidance Capture**.
Run **Sub-D: Extraction Complete Footer**.
```

## Acceptance Criteria

- [x] `core/ruleset-shared.md` contains `Sub-C: Guidance Capture` and `Sub-D: Extraction Complete Footer`
- [x] `extract-ruleset.md` calls Sub-C after Step 7c and Sub-D (not Sub-C) for the footer
- [x] `update-ruleset.md` calls Sub-C after Step 9d and Sub-D (not Sub-C) for the footer
- [x] Step 1: procedure is skipped (no synthesis attempted) when signals are absent
- [x] Step 2: cap of 5 candidates total; semantic deduplication drops existing-equivalent items
- [x] Step 3: bulk prompt says "Review them?" with [y/n]; unrecognized input re-prompts
- [x] Step 3: per-item prompt shows `[section]` prefix and `[y/n/edit]`; unrecognized input re-prompts
- [x] Step 3: `edit` pre-fills candidate text as editable starting point
- [x] Step 4: `generated_at` updated once at end (after all appends), not per-item
- [x] Step 4: `source_template` and unchanged sections preserved verbatim
- [x] Step 4: confirmation print uses correct singular/plural ("item" vs "items")
- [x] Zero candidates after dedup → silent skip, no prompt shown

## References

- Brainstorm: [docs/brainstorms/2026-03-04-guidance-capture-after-review.md](../brainstorms/2026-03-04-guidance-capture-after-review.md)
- Shared procedures pattern: [core/ruleset-shared.md](../../core/ruleset-shared.md)
- ai-guidance.yaml write pattern: [.claude/commands/refine-guidance.md](../../.claude/commands/refine-guidance.md) (Step 4)
- Sub-procedure invocation: `Run **Sub-X: Name**.` (see extract-ruleset.md line 280, 409, 413)
