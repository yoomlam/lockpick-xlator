---
title: "feat: Add CIVIL quickref and redesign extract-ruleset review gate"
type: feat
status: completed
date: 2026-02-25
brainstorm: docs/brainstorms/2026-02-25-extract-ruleset-speedup-brainstorm.md
---

# feat: Add CIVIL quickref and redesign extract-ruleset review gate

## Overview

Two targeted improvements to the `/extract-ruleset` command, discovered during the `ak_doh apa_adltc` extraction run:

1. **Speed to Step 4**: Claude read ~900 lines of `tools/civil_schema.py` and `tools/transpile_to_opa.py` before drafting any CIVIL YAML — both unnecessary for authoring. Fix: add a schema constraints block to the command and create a dedicated `docs/civil-quickref.md` cheat sheet.
2. **Review gate redesign**: The current Step 8 conflates "I wasn't sure about this extraction" with "this rule is inherently complex" into a single HIGH/LOW bucket. Fix: split into two semantically distinct buckets.

## Problem Statement

### Issue 1 — Unnecessary reads slow Step 4

The command's CIVIL Expression Language block covers syntax only. It omits:
- `FactField` has no `default:` attribute (only `optional: true`)
- Fact field strings use type `string`, not `str`
- `ComputedField.type` is limited to `Literal["money", "bool", "float", "int"]`
- `Jurisdiction` requires `country:` (Claude missed this and had to look it up)
- `Rule.then` must be non-empty for all rules (allow and deny)
- `Conditional` requires all three branches: `if`, `then`, `else`
- The transpiler only processes `deny` rules → `denial_reasons`; allow rules are not transpiled

Without these constraints, Claude goes looking. The explicit prohibition on reading `tools/` is also missing.

### Issue 2 — Misleading review gate

The current split: HIGH PRIORITY = any score ≤2 or ≥4; LOW PRIORITY = all scores exactly 3.

This conflates two orthogonal concerns:
- **Extraction uncertainty** (fidelity ≤2 or clarity ≤2): "Did I get this right?"
- **Inherent complexity** (logic ≥4 or policy ≥4): "This rule is dense — worth careful reading"

A rule can be high-confidence AND complex. Grouping them makes the review list hard to act on.

## Proposed Solution

### Change 1 — `tools/civil_schema.py`: Add sync comment

Add a sync reminder comment near the top of the file (after the module docstring) pointing to `docs/civil-quickref.md`.

**File:** `tools/civil_schema.py`
**Where:** After the module docstring, before imports

```python
# IMPORTANT: If you change types, field attributes, or add new model classes,
# update docs/civil-quickref.md to match and refresh its "last verified" date.
# Also update specs/CIVIL_DSL_spec.md if the change affects the DSL design.
```

### Change 2 — Create `docs/civil-quickref.md`

New file. Authoritative single-file reference for CIVIL authoring. Does NOT duplicate the expression language (already in the command).

**Scope note:** This is a Claude authoring cheat sheet, not a replacement for `specs/CIVIL_DSL_spec.md`. It covers only the model types needed to write a CIVIL module. Add a note at the top pointing to the full spec for design rationale.

**Sections:**
1. Header with last-verified datestamp + link to `specs/CIVIL_DSL_spec.md` for full spec
2. Module-level required vs optional sections table (`CivilModule` fields)
3. `FactField` attribute table (type, description, optional, currency, values)
4. `FactEntity` attribute table (description, fields)
5. `ComputedField` attribute table + `expr` xor `conditional` constraint
6. `Conditional` attribute table (all three branches required)
7. `DecisionField` attribute table
8. `TableDef` attribute table
9. `Rule` attribute table + `then` non-empty constraint
10. `RuleSet` attribute table
11. `Jurisdiction` attribute table (`country` required)
12. `Effective` attribute table
13. Valid enum values for all `Literal` fields
14. Transpiler behavior summary (what generates Rego, what doesn't)
15. Common gotchas list (the 7 items from Issue 1 above)

### Change 3 — `extract-ruleset.md`: Add CIVIL Schema Constraints section

New section inserted **after the Scoring Rubric and before "Process — CREATE Mode"** (so it applies to both CREATE and UPDATE modes).

**Content:**
- Prohibition: *"Do NOT read any files in `tools/` before the validation step (Step 6 in CREATE, Step 8 in UPDATE). All type constraints are in the block below and in `docs/civil-quickref.md`."*
- The 7 non-obvious gotchas as a compact bullet list
- Reference to `docs/civil-quickref.md` for the full attribute tables

**Example structure:**

```markdown
## CIVIL Schema Constraints

> **Do NOT read `tools/civil_schema.py`, `tools/transpile_to_opa.py`, or any other
> file in `tools/` before the validation step.** All type constraints needed for
> authoring are in this section and in `docs/civil-quickref.md`.

Key constraints not covered by the expression language reference above:

- **`FactField` has no `default:` attribute** — use `optional: true` instead; defaults are input-level concerns
- **String type is `string`**, not `str` — `int`, `float`, `bool`, `string`, `date`, `money`, `list`, `set`, `enum`
- **`ComputedField.type` is limited** to `money`, `bool`, `float`, `int` — no `string` in computed fields
- **`Jurisdiction` requires `country:`** — e.g., `country: US` — it is not optional
- **`Rule.then` must be non-empty** — every rule (allow and deny) needs at least one action
- **`Conditional` requires all three branches** — `if`, `then`, and `else` are all required; no optional else
- **Transpiler ignores allow rules** — only `deny` rules generate Rego; `then:` actions on allow rules are documentary only

For full attribute tables (required vs optional fields for each model), see [`docs/civil-quickref.md`](../docs/civil-quickref.md).
```

### Change 4 — `extract-ruleset.md`: Rewrite Step 8 review gate

Replace the current HIGH/LOW PRIORITY format with a two-bucket format.

**New partitioning logic:**

| Bucket | Condition | Meaning |
|--------|-----------|---------|
| Uncertain Extractions | `extraction_fidelity` ≤2 OR `source_clarity` ≤2 | Claude wasn't confident — human must verify |
| Complex Rules | `logic_complexity` ≥4 OR `policy_complexity` ≥4 | Inherently dense — worth careful review |
| Verified | Not in either bucket | All four scores in 3–5/3–5/1–3/1–3 range |

Items in both buckets → appear once under Uncertain Extractions with both flags noted.

**New summary header format:**
```
Review summary: X uncertain, Y complex, Z verified  (N items total)
```

**New item block format (Uncertain Extractions):**
```
─────────────────────────────────────────────────────────────────
⚠️  UNCERTAIN: <rule-id or "computed: <field_name>">
    Scores: fidelity:<N> clarity:<N> logic:<N> policy:<N>
    Flagged for: <"low extraction fidelity" and/or "low source clarity">
                 <+ "high logic complexity" and/or "high policy complexity" if also complex>
    Policy: "<exact source sentence(s)>"
    CIVIL:  <when: expression or expr:/conditional:>
    Notes:  <notes field content, or "(none)" if omitted>
─────────────────────────────────────────────────────────────────
```

**New item block format (Complex Rules):**
```
─────────────────────────────────────────────────────────────────
🔍  COMPLEX: <rule-id or "computed: <field_name>">
    Scores: fidelity:<N> clarity:<N> logic:<N> policy:<N>
    Flagged for: <"high logic complexity" and/or "high policy complexity">
    Policy: "<exact source sentence(s)>"
    CIVIL:  <when: expression or expr:/conditional:>
    Notes:  <notes field content, or "(none)" if omitted>
─────────────────────────────────────────────────────────────────
```

**Verified compact list:**
```
✅  VERIFIED (<N> items — not uncertain, not complex)
    • FED-SNAP-DENY-001: Gross income exceeds 130% FPL limit
    • computed: gross_income — total household gross monthly income
    ...
```

**Edge cases:**
- If no uncertain items → omit that section entirely
- If no complex items → omit that section entirely
- If no verified items → omit the Verified list
- If ALL items verified → show: "All items verified — no uncertain or complex items."

**Rejection handling** (same as current but updated terminology):
On rejection, re-extract the specific disputed item, re-validate (retry loop), recompute its `review:` scores, then re-present the full review gate. Do not proceed until the user confirms.

## Acceptance Criteria

- [ ] `tools/civil_schema.py` has a sync comment pointing to both `docs/civil-quickref.md` and `specs/CIVIL_DSL_spec.md`
- [ ] `docs/civil-quickref.md` exists with last-verified datestamp `2026-02-25` and link to `specs/CIVIL_DSL_spec.md`
- [ ] Quickref covers all authoring-relevant model types with required/optional attribute tables (CivilModule, FactField, FactEntity, ComputedField, Conditional, DecisionField, TableDef, Rule, RuleSet, Jurisdiction, Effective)
- [ ] Quickref lists all valid enum values for `Literal` fields
- [ ] Quickref has a transpiler behavior section
- [ ] Quickref has a "Common Gotchas" section with the 7 items
- [ ] `extract-ruleset.md` has a `## CIVIL Schema Constraints` section before CREATE mode steps
- [ ] That section includes the `tools/` prohibition and the 7 gotchas as bullets
- [ ] Step 8 in `extract-ruleset.md` uses Uncertain/Complex/Verified buckets
- [ ] Step 8 partitioning: Uncertain = fidelity ≤2 OR clarity ≤2; Complex = logic ≥4 OR policy ≥4
- [ ] Items in both buckets appear once under Uncertain with both flags noted
- [ ] All three edge cases (no uncertain, no complex, all verified) are handled in Step 8
- [ ] Rejection/re-extract flow preserved in Step 8

## File Edits Summary

| File | Change type | Scope |
|------|-------------|-------|
| `tools/civil_schema.py` | Edit | ~3 lines added after docstring |
| `docs/civil-quickref.md` | Create | ~120 lines |
| `.claude/commands/extract-ruleset.md` | Edit — insert | ~25 lines, new section before CREATE mode |
| `.claude/commands/extract-ruleset.md` | Edit — replace | ~50 lines, Step 8 only |

## References

- Brainstorm: [docs/brainstorms/2026-02-25-extract-ruleset-speedup-brainstorm.md](../brainstorms/2026-02-25-extract-ruleset-speedup-brainstorm.md)
- Schema source: [tools/civil_schema.py](../../tools/civil_schema.py)
- Command file: [.claude/commands/extract-ruleset.md](../../.claude/commands/extract-ruleset.md)
- SNAP example (reference implementation): [domains/snap/specs/eligibility.civil.yaml](../../domains/snap/specs/eligibility.civil.yaml)
