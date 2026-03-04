---
date: 2026-03-04
topic: guidance-capture-after-review
---

# Guidance Capture After Human Review Gate

## What We're Building

A new shared sub-procedure (`Sub-C: Guidance Capture`) in `core/ruleset-shared.md` that runs after the Human Review Gate completes — before the existing `Sub-C: Extraction Complete Footer` (which gets renamed to Sub-D). After the user approves a ruleset, the AI reviews all signals from the review session (corrections, rejections, score patterns, notes) and proposes guidance items to append to `ai-guidance.yaml`. The user confirms each item individually before it's written.

This closes the feedback loop: the review gate is a rich source of domain-specific extraction knowledge, and capturing it as guidance improves future extractions without requiring the user to manually run `/refine-guidance`.

## Why This Approach

**All review signals** were selected over "corrections only" or "user-driven" because the review gate contains rich signal beyond just rejections — score distributions, notes on complex rules, and patterns across uncertain items all inform what guidance would help next time. The AI is well-positioned to synthesize this into structured items; the user just approves or skips each one.

**Shared sub-procedure** (not inline in each command) avoids duplication — `extract-ruleset` Step 7 and `update-ruleset` Step 9 both culminate in the same approval state and can share identical guidance-capture logic.

**One-at-a-time confirmation** (not a batch list) keeps each item focused and avoids the user feeling overwhelmed. Short items are easy to confirm quickly; the user can skip any they disagree with.

## Key Decisions

- **Step naming**: Rename existing `Sub-C: Extraction Complete Footer` to `Sub-D`; new step becomes `Sub-C: Guidance Capture`. Both commands reference it between their post-review substeps (7c / 9d) and the footer.
- **Synthesis scope**: AI looks at everything that happened in the review — corrections made, items rejected and re-extracted, uncertain/complex bucket items, any `notes:` fields, and patterns across scores.
- **Item cap**: Propose at most 5 guidance items total across all sections to avoid overwhelming the user.
- **Section assignment**: AI pre-assigns each proposed item to the most appropriate `ai-guidance.yaml` section; user doesn't need to decide.
- **Skip condition**: If the AI finds no notable signals to surface (perfectly clean review with no corrections and all normal scores), skip the step silently — don't ask the user.
- **ai-guidance.yaml guaranteed present**: Pre-flight check 5 already halts if the file is missing, so no missing-file handling needed here.
- **Deduplication**: Before proposing an item, check if a similar item already exists in that section and skip it.

## Step Specification (Draft)

**Sub-C: Guidance Capture**

After the Human Review Gate is approved:

1. Review all signals from the review session:
   - Items that were rejected and re-extracted (what changed?)
   - Items in the Uncertain bucket (fidelity ≤2 or clarity ≤2)
   - Items in the Complex bucket with `notes:` fields
   - Any corrections the user provided to CIVIL expressions or notes

2. Synthesize candidate guidance items, grouped by `ai-guidance.yaml` section. Skip items already present in the file.

3. If zero candidates → proceed silently to Sub-D.

4. If ≥1 candidate → ask:
   ```
   Based on your review feedback, I have X suggestion(s) to improve future extractions.
   Add them to ai-guidance.yaml? [y/n]
   ```
   - **n** → proceed to Sub-D.
   - **y** → for each candidate, present and confirm:
     ```
     [guidance] "Do not assume income exclusions apply unless explicitly stated for this program."
     Add this item? [y / n / edit]
     ```
     - **y** → append to the appropriate section; update `generated_at`.
     - **n** → skip.
     - **edit** → accept user's revised text, then add.

5. If any items were added, print:
   ```
   Updated ai-guidance.yaml (+N items)
   ```

## Next Steps

→ `/workflows:plan` to implement this in `core/ruleset-shared.md`, `extract-ruleset.md`, and `update-ruleset.md`
