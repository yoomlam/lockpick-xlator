---
title: "feat: Add source field to CIVIL DSL for policy provenance tracking"
type: feat
status: completed
date: 2026-02-27
---

# feat: Add `source` Field to CIVIL DSL for Policy Provenance Tracking

## Overview

Add a `source` field to the CIVIL DSL on every `FactField`, `TableDef`, `ComputedField`, and `Rule`. The value identifies the heading, section, and paragraph within the source policy document where that variable or rule is defined. This gives extracted rules full traceability back to their policy origins.

## Problem Statement / Motivation

Currently, CIVIL YAML captures *what* a rule does but not *where in the policy document it comes from*. A reviewer looking at a rule like `gross_income_exceeds_limit` cannot tell at a glance whether it derives from §273.9(a) or §273.10(b) without hunting through the source document.

The `naming-manifest.yaml` already tracks a `section` field per `FactField`, but:
- It only covers fields, not tables or rules
- It lives outside the CIVIL file (a separate artifact)

Embedding `source:` directly in the CIVIL YAML gives every entity a self-contained audit trail, enabling traceability reports, diff views, and future policy-update detection.

## Proposed Solution

Add a `source: str | None` field to `FactField`, `TableDef`, `ComputedField`, and `Rule`. Being optional ensures full backward compatibility — all existing CIVIL files validate without modification.

No new model class is needed. The field is a plain free-text string combining heading, section, and paragraph in whatever format the policy document uses. The naming manifest already uses this pattern (`section: "7 CFR § 273.9 — Income and Deductions"`) and it is sufficient.

```python
# In civil_schema.py — add to FactField, TableDef, ComputedField, Rule
source: str | None = Field(
    default=None,
    description="Policy document location where this element is defined, e.g. '7 CFR § 273.9(a) — Income and Deductions'."
)
```

### CIVIL YAML example

```yaml
facts:
  Household:
    fields:
      gross_monthly_income:
        type: number
        description: "Total gross monthly income before deductions"
        source: "7 CFR § 273.9(a) — Income and Deductions"

computed:
  gross_income_exceeds_limit:
    expr: "gross_monthly_income > gross_limit"
    source: "7 CFR § 273.9(a)(1) — Gross Income Test"

tables:
  gross_income_limits:
    key_column: household_size
    value_column: monthly_limit
    source: "7 CFR § 273.9(a)(1) — Gross Income Limits Table"
    rows:
      - [1, 1580]
      ...

rules:
  - id: FED-SNAP-DENY-GROSS
    source: "7 CFR § 273.9(a)(1) — Gross Income Test"
    when: "gross_income_exceeds_limit"
    then:
      - add_reason:
          text: "Gross income exceeds 130% FPL limit"
          citations:
            - label: "7 CFR § 273.9(a)(1)"
```

### Distinction: `source:` vs `citations:`

| Field | Purpose | Audience |
|-------|---------|---------|
| `source:` (on Rule/Field/Table) | Where in the policy document this element was *extracted from* — for developer traceability | CIVIL authors, auditors |
| `citations:` (on add_reason action) | Legal authority cited in the *denial explanation shown to applicants* | End users, caseworkers |

A deny rule will often have the same CFR section in both. That is expected and not redundant: `source:` is the extraction record; `citations:` is the user-facing justification.

## Technical Considerations

### Schema

- **File:** `tools/civil_schema.py` — Pydantic v2 is the single source of truth
- Add `source: str | None = Field(default=None, description="...")` to `FactField`, `TableDef`, `ComputedField`, `Rule`
- No new model class needed
- **Do not** add `source:` to `FactEntity` (container concept, not a leaf definition), `DecisionField` (output, not a policy input), or `constants` (raw `dict[str, Any]` — structural change would be breaking)
- After editing `civil_schema.py`, regenerate `core/ruleset.schema.json` by running `python tools/civil_schema.py`

### Validator

No changes. `tools/validate_civil.py` delegates entirely to `CivilModule.model_validate()`. Optional fields are automatically accepted or rejected by Pydantic with no custom code needed.

### Transpiler

No changes. `tools/transpile_to_opa.py` reads known keys by name and never iterates unknown keys. `source:` is silently skipped — Rego output is identical before and after.

### Test Files

No changes. Test YAML files (`domains/*/specs/tests/`) operate on OPA inputs/outputs and have no schema awareness.

### Naming Manifest Relationship

The `naming-manifest.yaml` `section` field (per `FactField`/`ComputedField`) and the new CIVIL `source:` block are **independent and coexisting** — no enforcement of consistency between them. The manifest serves naming stability (UPDATE mode divergence detection); `source:` serves inline provenance. Keep the manifest `section` field so it can be shared independently of the CIVIL ruleset file.

### UPDATE Mode Behavior

UPDATE mode re-extracts some sections and preserves others verbatim. The resulting CIVIL file will have `source:` on re-extracted entities and absent on preserved ones — this hybrid state is valid (all fields are optional) and no detection/flagging of the asymmetry is needed. Future work could add a "coverage report" showing which entities lack `source:`.

## Acceptance Criteria

### Schema

- [ ] `SourceRef` model added to `tools/civil_schema.py` with `heading`, `section`, `paragraph` all `str | None`
- [ ] `source: SourceRef | None = None` added to `FactField`, `TableDef`, `ComputedField`, and `Rule`
- [ ] `core/ruleset.schema.json` regenerated (run `python tools/civil_schema.py`)
- [ ] `core/CIVIL_DSL_spec.md` updated to document the new model

### Backward Compatibility

- [ ] `make snap-validate` passes on existing `domains/snap/specs/eligibility.civil.yaml` with no changes to that file
- [ ] `make ak-doh-validate` passes on `domains/ak_doh/specs/apa_adltc.civil.yaml` with no changes
- [ ] `make snap-transpile` produces byte-identical Rego output compared to before

### Documentation

- [ ] `docs/civil-quickref.md` updated: `source` row added to `FactField`, `TableDef`, `ComputedField`, and `Rule` attribute tables; header "last verified" date bumped to 2026-02-27
- [ ] `.claude/commands/extract-ruleset.md` updated:
  - Step 4 CIVIL YAML template shows `source:` on at least one example of each: `FactField`, `ComputedField`, `TableDef`, and `Rule`
  - Instruction added: map the Name Inventory "Source Section" value into `source` by *combining* it with surrounding heading context (e.g., `"§ 273.9(a)"` + heading `"Income and Deductions"` → `"7 CFR § 273.9(a) — Income and Deductions"`), not copying verbatim
  - Clarifying note: `source:` = extraction traceability; `citations:` = user-facing legal authority on deny reasons

### CIVIL Authoring

- [ ] A CIVIL file with `source:` on every `FactField`, `TableDef`, `ComputedField`, and `Rule` validates and transpiles correctly

## Dependencies & Risks

| Item | Detail |
|------|--------|
| **Pydantic v2 already in use** | No new dependency; pattern established in `2026-02-25.c` plan |
| **`ruleset.schema.json` regeneration** | Must run `python tools/civil_schema.py` after schema edit — this is already the established workflow |
| **Naming manifest `section` divergence** | The manifest `section` field and CIVIL `source:` track the same information in different places and can silently drift on policy updates. Coexistence is acceptable for now; eventual deprecation of manifest `section` is the right long-term resolution (see Out of Scope). |
| **AI extraction quality** | `source:` population is only as good as the AI agent's document navigation; free-text strings mean no normalization guarantee across runs. |
| **`constants:` excluded** | Deliberate. Constants use `dict[str, Any]`; adding `source:` there would be a breaking change requiring a transpiler update. Track as future work if needed. |
| **Multi-action rule granularity** | A single `Rule` with multiple `then:` actions from different paragraphs gets one `source:` for the whole rule. Sub-action provenance is not supported in v1. |

## Out of Scope

- `FactEntity` — container for fields, not itself a leaf policy element
- `DecisionField` (output declarations like `eligible: boolean`)
- `constants:` — structural change too disruptive; track separately
- Backfilling `source:` into existing CIVIL files — optional follow-up
- Deprecating `section` from `naming-manifest.yaml` in favour of CIVIL `source:` — tracked in Dependencies & Risks as future resolution
- Sub-action provenance within multi-`then:` rules
- Normalizing `source:` values across runs (e.g., enforcing CFR citation format)
- Emitting `source:` as Rego comments in the transpiler — optional cosmetic follow-up

## Implementation Order

1. `tools/civil_schema.py` — add `source: str | None` to `FactField`, `TableDef`, `ComputedField`, `Rule`
2. `python tools/civil_schema.py` → regenerate `core/ruleset.schema.json`
3. Verify backward compatibility and transpiler invariance: `make snap-validate && make ak-doh-validate && make snap-transpile` (output must be identical to before)
4. `core/CIVIL_DSL_spec.md` — document the new field
5. `docs/civil-quickref.md` — add `source` row to all four attribute tables; bump "last verified" date
6. `.claude/commands/extract-ruleset.md` — update Step 4 template and instructions

## References & Research

### Internal References

- Schema source of truth: [tools/civil_schema.py](tools/civil_schema.py)
- Validator: [tools/validate_civil.py](tools/validate_civil.py)
- Transpiler: [tools/transpile_to_opa.py](tools/transpile_to_opa.py)
- Extract command: [.claude/commands/extract-ruleset.md](.claude/commands/extract-ruleset.md)
- Authoring quickref: [docs/civil-quickref.md](docs/civil-quickref.md)
- Naming manifest example: [domains/snap/specs/naming-manifest.yaml](domains/snap/specs/naming-manifest.yaml)
- Prior schema extension plan (review/scoring): [docs/plans/2026-02-25.b-feat-civil-review-scoring-annotation.md](docs/plans/2026-02-25.b-feat-civil-review-scoring-annotation.md)
- Prior Pydantic migration plan: [docs/plans/2026-02-25.c-feat-pydantic-civil-schema.md](docs/plans/2026-02-25.c-feat-pydantic-civil-schema.md)
