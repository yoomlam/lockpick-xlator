# Brainstorm: Faster `/extract-ruleset` — Schema Context & Review Gate Redesign

**Date:** 2026-02-25
**Status:** Ready for planning
**Trigger:** Observed friction in `ak_doh apa_adltc` extraction run

---

## What We're Building

Two targeted improvements to the `/extract-ruleset` command:

1. **Speed to Step 4**: Give Claude everything it needs to draft a valid CIVIL module without reading `civil_schema.py` or `transpile_to_opa.py`.
2. **Review gate redesign (Step 8)**: Replace the single HIGH/LOW PRIORITY split with two semantically meaningful buckets — *Uncertain Extractions* and *Complex Rules*.

---

## Problem Analysis

### Issue 1 — Slow path to Step 4

During the `ak_doh` run, Claude read:
- `tools/civil_schema.py` (~491 lines) — to verify field types, `FactField` constraints, and `computed:` type limits
- `tools/transpile_to_opa.py` (~426 lines) — to understand how allow rules with `set:` actions would be transpiled (they aren't)

These reads added ~900 lines of context before any extraction work began. The command references `civil_schema.py` only for the validation retry loop (Step 6), not for Step 4 drafting. The command does not reference `transpile_to_opa.py` at all.

**Root cause**: The command's embedded CIVIL Expression Language reference is accurate but incomplete. It omits:
- `FactField` has no `default:` attribute
- Fact field type for strings is `string` (not `str`)
- `computed:` types limited to `money`, `bool`, `float`, `int` only
- `jurisdiction:` requires `country:` (required field)
- `then:` must be non-empty for all rules
- Transpiler only processes `deny` rules → `denial_reasons`; allow rules are ignored

Without these constraints, Claude goes looking.

### Issue 2 — Misleading review gate categories

The current Step 8 groups all items with any score ≤2 or ≥4 as "HIGH PRIORITY" and all-3 items as "LOW PRIORITY". This conflates two orthogonal concerns:

- **Extraction uncertainty** (`extraction_fidelity` ≤2 or `source_clarity` ≤2): "I wasn't sure about this — human should verify"
- **Inherent complexity** (`logic_complexity` ≥4 or `policy_complexity` ≥4): "This rule is dense — worth careful reading even if I'm confident"

A rule can be high-confidence AND complex. A rule can be uncertain AND simple. Grouping them makes the review list feel noisy and makes it hard to know what kind of attention each item needs.

---

## Decisions

### Decision 1 — Two-part fix for Step 4 speed (Option A + B combined)

**A: CIVIL Schema Constraints block in the command prompt**

Add a `## CIVIL Schema Constraints` section to `extract-ruleset.md` immediately before Step 4. ~30 lines covering:
- The 6-7 non-obvious structural rules (no `default:` in FactField, `string` not `str`, `computed:` type limits, required `jurisdiction.country`, non-empty `then:`, transpiler-only-processes-deny)
- This prevents reading `civil_schema.py` and `transpile_to_opa.py` entirely

**B: `docs/civil-quickref.md` cheat sheet**

A standalone document:
- All valid fact field types (the primitive set)
- `FactField`, `ComputedField`, `Decision`, `Rule`, `RuleSet`, `TableDef` — minimal attribute tables
- Transpiler behavior summary: what generates Rego, what doesn't
- Does NOT duplicate the expression language reference (already embedded in the command)

The command includes an explicit prohibition before Step 4: *"Do NOT read any files in `tools/` before Step 6 (validation). All type constraints and transpiler behavior are covered by `docs/civil-quickref.md` and the CIVIL Schema Constraints block above."*

**Why both?** The gotchas block in the command is Claude's fast-path guard for the 6-7 most common pitfalls. The quickref is the authoritative single-file fallback for anything not covered by the gotchas block.

**Keeping the quickref in sync with `civil_schema.py`:**

Two-layer mechanism — both layers needed:

1. **Comment in `civil_schema.py`** (top of file, hard to miss):
   ```python
   # IMPORTANT: If you change types, field attributes, or add new model classes,
   # update docs/civil-quickref.md to match.
   ```

2. **"Last verified" datestamp in the quickref header**:
   ```
   <!-- Last verified against tools/civil_schema.py: 2026-02-25 -->
   ```
   When a developer edits `civil_schema.py`, they update this date. When the date is stale (older than the last commit touching `civil_schema.py`), the quickref is suspect.

A generated approach (script that emits type tables from Pydantic models) is possible if drift becomes a real problem, but adds maintenance overhead now. Start with the comment + datestamp; upgrade if needed.

### Decision 2 — Two-bucket review gate

Replace the HIGH/LOW split with:

**Bucket 1: Uncertain Extractions** (`extraction_fidelity` ≤2 OR `source_clarity` ≤2)
- These need human verification: "Did I get this right?"
- Listed first; most actionable

**Bucket 2: Complex Rules** (`logic_complexity` ≥4 OR `policy_complexity` ≥4)
- These need careful reading: "Is this inherently hard policy captured correctly?"
- Listed second; for expert domain review

**Items in neither bucket**: Shown as a compact "Verified" list (not in Bucket 1 AND not in Bucket 2). No block format needed.

**Items in both buckets**: Appear once, under Bucket 1, with both flags noted.

**Summary header format**:
```
Review summary: X uncertain, Y complex, Z verified  (N items total)
```

---

## Scope

### In scope
- Edit `extract-ruleset.md`: add CIVIL Schema Constraints section before Step 4
- Create `docs/civil-quickref.md`
- Rewrite Step 8 review gate format in `extract-ruleset.md`

### Out of scope
- Changing `civil_schema.py` or the validator
- Changing the SNAP example file
- Automating the review gate (still human-reviewed)

---

## Open Questions

*None — resolved during brainstorm.*

---

## Resolved Questions

- **Which approach for schema constraints?** A + B combined (gotchas in command + standalone quickref)
- **Review gate structure?** Two buckets: Uncertain Extractions + Complex Rules
- **Four vs two buckets?** Two buckets preferred
