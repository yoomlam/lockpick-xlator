---
title: "feat: Add naming manifest and algorithmic naming to extract-ruleset"
type: feat
status: completed
date: 2026-02-25
brainstorm: docs/brainstorms/2026-02-25-extract-ruleset-determinism-brainstorm.md
---

# feat: Add Naming Manifest and Algorithmic Naming to extract-ruleset

## Overview

The `/extract-ruleset` command is LLM-driven and produces different fact and computed field names (e.g., `gross_income` vs `monthly_gross_income` vs `household_gross_income`) when run multiple times on the same input document. This plan adds a determinism layer so that:

- The **first run** uses a rigid naming algorithm to reduce LLM ambiguity
- **All subsequent runs** use a `.naming-manifest.yaml` to freeze names as ground truth

The only file changed is `.claude/commands/extract-ruleset.md`.

---

## Problem Statement

Running `/extract-ruleset snap` twice on an unchanged policy document yields different CIVIL field names. This breaks:
- Reproducibility expectations when re-running extraction after deleting the CIVIL file
- UPDATE mode, where re-extracted sections can silently rename fields that existing test cases reference

Root cause: the LLM samples freely when deriving field names — there is no constraint or memory across runs.

---

## Proposed Solution

Add four new steps/behaviors to the command, split across CREATE and UPDATE mode.

### CREATE mode: two additions

**Step 3b — Name Inventory** *(inserted between current Step 3 and Step 4)*

Before drafting the CIVIL file, produce an explicit name mapping table for all fact and computed fields. The LLM follows this 4-step naming algorithm for each concept found in the policy:

1. Find the exact noun phrase in the policy text describing the concept
2. Strip words that duplicate the entity name (e.g., entity is `Household` → strip "household")
3. Convert to `snake_case`
4. If the result would be ambiguous with another field, append a disambiguating qualifier from the policy text

Present the table and ask for user approval before any CIVIL YAML is written. If `.naming-manifest.yaml` already exists (CREATE re-run), pre-populate the table from the manifest; only derive new names for concepts not already listed.

**Step 8b — Write `.naming-manifest.yaml`** *(inserted after Step 8 approval, before Step 9)*

Write `domains/<domain>/specs/.naming-manifest.yaml` using the approved Name Inventory table. On CREATE re-run, merge with existing manifest (preserve entries, add new ones only).

### UPDATE mode: two additions

**Step 0 — Load Naming Manifest + Divergence Detection** *(inserted before current Step 1)*

If `.naming-manifest.yaml` exists: compare all field names in the CIVIL file against the manifest. Halt and list mismatches if any are found. User must resolve (edit CIVIL or edit manifest) before proceeding.

If the manifest does not exist (domain extracted before this feature was added): warn and proceed without enforcement; manifest will be created after this UPDATE completes.

**Step 10b — Append New Fields to Manifest** *(inserted after Step 10 approval)*

Auto-append any new fact or computed fields added during this UPDATE to `.naming-manifest.yaml`. No extra confirmation required.

### UPDATE mode: one modification

**Step 5 (Re-extract affected sections)** — inject frozen names:

Before re-extracting any section containing fact or computed fields, inject the manifest's frozen names into the extraction prompt: "These fields already exist and must retain their exact names: [list]. Only introduce new field names for new concepts, using the 4-step naming algorithm: [algorithm]."

---

## Technical Considerations

- **File location:** `domains/<domain>/specs/.naming-manifest.yaml` — dotfile, alongside `.extraction-manifest.yaml`
- **File structure:**
  ```yaml
  version: "1.0"
  entities:
    Household:
      gross_monthly_income:
        policy_phrase: "gross monthly income"
        source_doc: "snap_eligibility_fy2026.md"
        section: "Income Definitions"
      household_size:
        policy_phrase: "number of people in the household"
        source_doc: "snap_eligibility_fy2026.md"
        section: "Household Composition"
  computed:
    net_income:
      policy_phrase: "net monthly income after deductions"
      source_doc: "snap_eligibility_fy2026.md"
      section: "Deductions"
  ```
- **No `generated_at` field** — omitted to avoid spurious diffs when hand-editing
- **User-editable by design** — contrast with `.extraction-manifest.yaml` which carries "do not edit manually" comment
- **Single YAML section per entity** — mirrors the `facts:` entity structure in the CIVIL file
- **Computed fields** are a top-level `computed:` section, not nested under any entity

---

## Acceptance Criteria

- [ ] Running `/extract-ruleset snap` a second time (after deleting the CIVIL file) produces identical fact and computed field names
- [ ] CREATE mode presents a Name Inventory table before writing any CIVIL YAML
- [ ] User can edit a name in the table; the edited name is used in the CIVIL file and frozen in the manifest
- [ ] `.naming-manifest.yaml` is written after the Step 8 human review gate approves
- [ ] UPDATE mode halts and lists mismatches if CIVIL field names diverge from the manifest
- [ ] UPDATE mode auto-appends new fields to the manifest after the Step 10 review gate
- [ ] Re-extracted sections in UPDATE mode never rename existing fields

---

## Implementation Detail

### Modified file

**`.claude/commands/extract-ruleset.md`** — single file, prompt/instruction changes only.

### CREATE mode changes

**Locate:** Step 3 ("Derive Program Name") — find the heading and paragraph in CREATE mode.

**Insert after Step 3 (new Step 3b):**

```markdown
### Step 3b — Name Inventory

Before drafting any CIVIL YAML, produce the canonical field name for every fact and computed concept in the policy. For each measurable quantity, flag, or derived value found in the policy documents, apply this algorithm:

1. Find the **exact noun phrase** in the policy text describing the concept
2. **Strip** any words that duplicate the entity name (e.g., entity is `Household` → strip "household" from "household gross income")
3. Convert to **`snake_case`**
4. If the result would be **ambiguous** with another field in the same entity, append a disambiguating qualifier from the policy text

Present this as a Markdown table:

| Policy Phrase | Entity / Section | Field Name | Source Section |
|--------------|-----------------|-----------|----------------|
| gross monthly income | Household | `gross_monthly_income` | §1.2 |
| number of people in the household | Household | `household_size` | §1.1 |
| net monthly income after all deductions | computed | `net_income` | §2.4 |

**If `.naming-manifest.yaml` already exists** (CREATE re-run after a previous successful extraction):
- Pre-populate the table with the frozen names from the manifest
- Only derive new names for policy concepts not already listed

Ask: "Do the field names in this table match your intent? You may edit any name." If the user changes any name, update the table and re-present. Loop until the user explicitly approves. Use the approved names throughout Step 4 onward.
```

**Locate:** Step 8 ("Human Review Gate") — find where Step 9 (Makefile) begins.

**Insert after Step 8 approval (new Step 8b):**

```markdown
### Step 8b — Write Naming Manifest

Now that the user has approved the rule-by-rule review, write `domains/<domain>/specs/.naming-manifest.yaml`:

```yaml
version: "1.0"
entities:
  <EntityName>:
    <field_name>:
      policy_phrase: "<exact policy phrase from Name Inventory>"
      source_doc: "<source filename>"
      section: "<section heading>"
  # repeat for each entity
computed:
  <field_name>:
    policy_phrase: "<exact policy phrase>"
    source_doc: "<source filename>"
    section: "<section heading>"
```

Populate every entry from the approved Name Inventory table (Step 3b). If a `.naming-manifest.yaml` already exists (CREATE re-run), merge: preserve all existing entries and append new ones.

This file is user-editable. Do **not** add an "auto-generated" comment.
```

### UPDATE mode changes

**Locate:** The start of UPDATE mode (before current Step 1 "Load Extraction Manifest").

**Insert new Step 0:**

```markdown
### Step 0 — Load Naming Manifest and Check for Divergence

**If `domains/<domain>/specs/.naming-manifest.yaml` exists:**

1. Read all field names from the manifest (`entities.*.*` keys and `computed.*` keys)
2. Read all field names from `domains/<domain>/specs/<program>.civil.yaml` (`facts.*.*` and `computed.*` keys)
3. Compare the two sets. If any field name:
   - Exists in the CIVIL file but not the manifest, **or**
   - Exists in both but differs (e.g., CIVIL has `income`, manifest has `gross_monthly_income`)

   Halt and list every mismatch:

   > ⚠️ Naming manifest divergence detected:
   > - CIVIL has `income` under `Household`, but manifest expects `gross_monthly_income`
   >
   > Resolve by either:
   > a) Edit the CIVIL file to restore the manifest name, or
   > b) Edit `.naming-manifest.yaml` to acknowledge the rename
   >
   > Then re-run `/extract-ruleset <domain>`.

   Do not continue until there are no mismatches.

**If the manifest does not exist** (domain was extracted before this feature was added):
> ⚠️ No naming manifest found. Field names will not be enforced this run. A manifest will be created after this UPDATE completes.

Proceed to Step 1.
```

**Locate:** Step 5 ("Re-extract affected sections").

**Add to the re-extraction instructions:**

```markdown
When re-extracting any section containing `facts:` or `computed:` fields:
- Inject the frozen names from `.naming-manifest.yaml` into the extraction prompt: "These fields must keep their exact current names: [list all names]. Only introduce new field names for concepts not in this list, using the 4-step naming algorithm: (1) exact noun phrase, (2) strip entity name words, (3) snake_case, (4) disambiguate if needed)."
- **Never rename an existing field** during re-extraction.
```

**Locate:** Step 10 ("Human Review Gate" for UPDATE).

**Insert after Step 10 approval (new Step 10b):**

```markdown
### Step 10b — Update Naming Manifest

If any new fact or computed fields were added during this UPDATE:

1. Apply the 4-step naming algorithm (from CREATE Step 3b) to derive the canonical name for each new concept
2. Append the new entries to `domains/<domain>/specs/.naming-manifest.yaml` under the appropriate entity or `computed:` section
3. Preserve all existing manifest entries unchanged

No additional user confirmation is needed; this happens automatically after the review gate passes.
```

### Output artifacts table

**Locate:** The output artifacts summary at the bottom of the command (if present).

**Add row:**

| Artifact | CREATE | UPDATE |
|----------|--------|--------|
| `domains/<domain>/specs/.naming-manifest.yaml` | Created | Updated (new fields appended) |

---

## Dependencies & Risks

**Dependencies:**
- No code changes — this is a prompt-only change to `.claude/commands/extract-ruleset.md`
- No new tooling required; the Write tool already handles YAML file creation

**Risks:**
- **Existing SNAP domain:** `.naming-manifest.yaml` does not exist yet for the SNAP domain. First UPDATE run after this change will warn and proceed without enforcement. The manifest will be created after that UPDATE completes. Alternatively, the user can manually create the manifest before the first UPDATE by running CREATE mode once on the existing CIVIL file (or create it by hand from the existing field names).
- **Algorithm edge cases:** The 4-step naming algorithm may not produce ideal names for all policies (e.g., terse policy language, non-English terms). The Name Inventory review gate is the safety valve — the user catches and corrects these before names are frozen.
- **Multi-entity policies:** The per-entity structure handles this correctly. Only single-entity SNAP is tested so far.

---

## Success Metrics

- Running `/extract-ruleset snap` a second time (CREATE re-run) produces a CIVIL file with zero field name differences from the first run
- The `.naming-manifest.yaml` for SNAP is created and tracks all 8 fact fields and 12 computed fields
- No existing test suite changes required (field names in tests are unchanged)

---

## References

- Brainstorm: [docs/brainstorms/2026-02-25-extract-ruleset-determinism-brainstorm.md](docs/brainstorms/2026-02-25-extract-ruleset-determinism-brainstorm.md)
- Command to modify: [.claude/commands/extract-ruleset.md](.claude/commands/extract-ruleset.md)
- Existing manifest pattern: [domains/snap/specs/.extraction-manifest.yaml](domains/snap/specs/.extraction-manifest.yaml)
- CIVIL example: [domains/snap/specs/eligibility.civil.yaml](domains/snap/specs/eligibility.civil.yaml)
- Prior plan (command implementation): [docs/plans/2026-02-24-feat-extract-ruleset-skill-plan.md](docs/plans/2026-02-24-feat-extract-ruleset-skill-plan.md)
