# CIVIL DSL — Authoring Quick Reference

<!-- Last verified against tools/civil_schema.py: 2026-02-27 -->

This is a **Claude authoring cheat sheet** for writing valid CIVIL YAML modules.
For full specification and design rationale, see [CIVIL_DSL_spec.md](CIVIL_DSL_spec.md).

---

## Module-Level Structure (`CivilModule`)

| Field | Required | Notes |
|-------|----------|-------|
| `module` | ✅ | Unique identifier, e.g. `"eligibility.snap_federal"` |
| `description` | ✅ | Human-readable description |
| `version` | ✅ | e.g. `"2026Q1"` |
| `jurisdiction` | ✅ | See `Jurisdiction` table |
| `effective` | ✅ | See `Effective` table |
| `facts` | ✅ | Dict of entity names → `FactEntity` |
| `decisions` | ✅ | Dict of decision names → `DecisionField` |
| `rule_set` | ✅ | See `RuleSet` table |
| `rules` | ✅ | List of `Rule` objects |
| `tables` | — | Optional lookup tables |
| `constants` | — | Optional named constants (UPPER_SNAKE_CASE) |
| `computed` | — | Optional derived intermediate values (CIVIL v2) |
| `types` | — | Optional custom type definitions |

---

## `FactEntity`

| Field | Required | Notes |
|-------|----------|-------|
| `description` | — | Human-readable entity description |
| `fields` | ✅ | Dict of field names → `FactField` |

Entity names use **PascalCase** (e.g. `Household`, `Applicant`).

## `FactField`

| Field | Required | Notes |
|-------|----------|-------|
| `type` | ✅ | See valid fact types below |
| `description` | — | Human-readable field description |
| `source` | — | Policy document location, e.g. `"7 CFR § 273.9(a) — Income and Deductions"` |
| `optional` | — | `true` if the field may be absent (default: `false`) |
| `currency` | — | Currency code for `money` type, e.g. `USD` |
| `values` | — | List of allowed strings for `enum` type |

> ⚠️ **`FactField` has no `default:` attribute.** Use `optional: true` for optional fields.

Valid `type` values for fact fields:
`int`, `float`, `bool`, `string`, `date`, `money`, `list`, `set`, `enum`

> ⚠️ **Use `string`, not `str`.**

---

## `ComputedField`

| Field | Required | Notes |
|-------|----------|-------|
| `type` | ✅ | `money`, `bool`, `float`, or `int` only |
| `currency` | — | Currency code for `money` type |
| `description` | — | Human-readable description |
| `source` | — | Policy document location, e.g. `"7 CFR § 273.9(d)(1) — Earned Income Deduction"` |
| `expr` | ✅ or `conditional` | CIVIL expression (mutually exclusive with `conditional`) |
| `conditional` | ✅ or `expr` | If/then/else branch (mutually exclusive with `expr`) |
| `review` | — | `ReviewBlock` with extraction quality scores |

> ⚠️ **`ComputedField.type` is limited to `money`, `bool`, `float`, `int`.** No `string` in computed fields.

> ⚠️ **Exactly one of `expr` or `conditional` must be present** — not both, not neither.

## `Conditional`

| Field | Required | Notes |
|-------|----------|-------|
| `if` | ✅ | Boolean CIVIL expression |
| `then` | ✅ | CIVIL expression for the true branch |
| `else` | ✅ | CIVIL expression for the false branch |

> ⚠️ **All three branches are required.** There is no optional `else`.

---

## `DecisionField`

| Field | Required | Notes |
|-------|----------|-------|
| `type` | ✅ | e.g. `bool`, `list`, `money`, `string` |
| `default` | — | Default value when no rules fire (e.g. `false`, `[]`) |
| `description` | — | Human-readable description |
| `item` | — | Item type for `list`/`set` decisions (e.g. `Reason`) |

---

## `TableDef`

| Field | Required | Notes |
|-------|----------|-------|
| `description` | — | Human-readable description |
| `source` | — | Policy document location, e.g. `"7 CFR § 273.9(a)(1) — Gross Income Limits Table"` |
| `key` | ✅ | List of key column name(s), e.g. `[household_size]` |
| `value` | ✅ | List of value column name(s), e.g. `[max_gross_monthly]` |
| `rows` | ✅ | List of row dicts, e.g. `[{household_size: 1, max_gross_monthly: 1580}]` |

Table reference in expressions: `table('table_name', key_expr).value_column`

---

## `Rule`

| Field | Required | Notes |
|-------|----------|-------|
| `id` | ✅ | Unique. Recommended: `<JURISDICTION>-<TOPIC>-<KIND>-<SEQ>` |
| `kind` | ✅ | `deny` or `allow` |
| `priority` | ✅ | Int; lower = higher priority. Allow rules typically 100+ |
| `when` | ✅ | Boolean CIVIL expression |
| `then` | ✅ | List of `Action` objects — **must be non-empty** |
| `description` | — | Human-readable description |
| `source` | — | Policy document location, e.g. `"7 CFR § 273.9(a)(1) — Gross Income Test"` |
| `review` | — | `ReviewBlock` with extraction quality scores |

> ⚠️ **`then:` must be non-empty for all rules**, including allow rules.

> ⚠️ **Transpiler ignores allow rules.** Only `deny` rules generate Rego. `then:` on allow rules is documentary only.

> ⚠️ **Rule `id` values must be unique** across the entire `rules:` list.

---

## `RuleSet`

| Field | Required | Notes |
|-------|----------|-------|
| `name` | ✅ | Rule set identifier |
| `precedence` | — | `deny_overrides_allow`, `allow_overrides_deny`, `first_match`, or `priority_order` |
| `description` | — | Human-readable description |

---

## `Jurisdiction`

| Field | Required | Notes |
|-------|----------|-------|
| `level` | ✅ | `federal`, `state`, `county`, or `city` |
| `country` | ✅ | ISO country code, e.g. `US` |
| `state` | — | State/province code, e.g. `AK` |
| `county` | — | County name |
| `city` | — | City name |

> ⚠️ **`country:` is required**, even for state-level programs.

---

## `Effective`

| Field | Required | Notes |
|-------|----------|-------|
| `start` | ✅ | Effective start date, e.g. `2026-01-01` |
| `end` | — | Effective end date (optional for open-ended policies) |

---

## Valid Enum Values

| Field | Valid values |
|-------|-------------|
| `FactField.type` | `int` `float` `bool` `string` `date` `money` `list` `set` `enum` |
| `ComputedField.type` | `money` `bool` `float` `int` |
| `Rule.kind` | `deny` `allow` |
| `Jurisdiction.level` | `federal` `state` `county` `city` |
| `RuleSet.precedence` | `deny_overrides_allow` `allow_overrides_deny` `first_match` `priority_order` |

---

## Transpiler Behavior

The `transpile_to_opa.py` transpiler generates Rego from a CIVIL module. Key behaviors:

| CIVIL construct | Rego output |
|----------------|-------------|
| `tables:` | Object literal lookup dict |
| `computed:` fields with `expr:` | Rego derived rule: `field := expr` |
| `computed:` fields with `conditional:` | Rego: `field := then if { if_expr } else := else_expr` |
| `rules:` with `kind: deny` | `denial_reasons contains reason if { ... }` |
| `rules:` with `kind: allow` | **Nothing** — allow rules are not transpiled |
| `decisions:` with `type: bool` | `default eligible := false` + `eligible if { count(denial_reasons) == 0 }` |
| `decisions:` with `type: list` | `denial_reasons` set comprehension |
| `computed:` fields | Included in `decision.computed` object |

The structured output object is always at `decision` (e.g., query `/v1/data/<pkg>/decision`).

---

## Common Gotchas

1. **`FactField` has no `default:`** — use `optional: true`; defaults are input-level concerns
2. **`string` not `str`** — fact field type for strings is `string`
3. **`ComputedField.type` cannot be `string`** — only `money`, `bool`, `float`, `int`
4. **`jurisdiction.country` is required** — don't omit it for state-level programs
5. **`then:` must be non-empty** — every rule needs at least one action
6. **`Conditional` needs all three branches** — `if`, `then`, and `else` are all required
7. **Allow rules aren't transpiled** — only `deny` rules produce Rego output; allow rules are documentary
