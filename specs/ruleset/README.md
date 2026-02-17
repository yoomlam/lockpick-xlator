# CIVIL DSL Specification

**Civic Instructions & Validations Intermediate Language**

---

## Introduction

Below is a **basic, practical DSL** aimed at government policy/regulation logic (eligibility + tax instructions) that's easy to **transpile** later to OPA/Rego, DMN, Drools, etc. It's designed around: **jurisdiction + effective dates + citations + explainability**.

This specification defines **CIVIL** (Civic Instructions & Validations Intermediate Language), the target architecture for Xlator's policy rule engine.

---

Design goals
------------

-   **Policy-native metadata**: jurisdiction, authority, citations, effective dates, version.
-   **Deterministic evaluation**: no hidden state; input facts → outputs.
-   **Layering**: federal baseline + state + city overrides/stricter rules.
-   **Explainability**: rules emit _reasons_ with citations.
-   **Transpiler-friendly**: simple AST, minimal syntax sugar.

---

Core concepts
-------------

### 1) Inputs are typed “facts”

Facts are the only input; the engine is a pure function:

`evaluate(policy_bundle, facts, as_of_date, jurisdiction) -> decisions + reasons`

### 2) Outputs are “decisions”

Decisions can be boolean, enum, numeric, or structured objects.

### 3) Rules are “when/then” with a reason

A rule can:

-   set a decision (`eligible = true`)
-   compute derived values (`agi = ...`)
-   emit instructions (`instructions += [...]`)
-   add violations/reasons (`reasons += reason(...)`)

### 4) Policy bundle supports versions + effective dates

Quarterly updates become a new policy bundle version, not in-place edits.

---

DSL structure (high level)
--------------------------

-   `policy_bundle`: a versioned collection of modules
-   `module`: scoped to domain (eligibility, tax, etc.)
-   `definitions`: types, constants, tables
-   `rule_set`: rules + precedence strategy

---

Syntax (YAML-like, transpiler-friendly)
---------------------------------------

### Policy bundle skeleton

```yaml
bundle: "civics:benefits"
version: "2026Q1"
effective:
  start: 2026-01-01
  end: 2026-03-31
jurisdiction:
  level: federal
  country: US

modules:
  - file: eligibility/housing_assistance.civil.yaml
  - file: tax/filing_basics.civil.yaml
```

---

Module format
-------------

### 1) Types + fact schema

```yaml
module: "eligibility.housing_assistance"
description: "Housing Assistance eligibility rules"
jurisdiction: { level: federal, country: US }

facts:
  Applicant:
    fields:
      age: { type: int }
      resident: { type: bool }
      household_size: { type: int }
      annual_income: { type: money, currency: USD }
      city: { type: string }
      state: { type: string }

decisions:
  eligible: { type: bool, default: false }
  reasons:  { type: list, item: Reason, default: [] }

types:
  Reason:
    fields:
      code: { type: string }
      message: { type: string }
      citations: { type: list, item: Citation }
  Citation:
    fields:
      label: { type: string }      # e.g., "42 USC § 1437a"
      url: { type: string, optional: true }
      excerpt: { type: string, optional: true }  # keep short
```

### 2) Constants + tables

```yaml
constants:
  MIN_AGE: 18

tables:
  income_limit_by_household:
    key: [household_size]
    value: [max_income]
    rows:
      - { household_size: 1, max_income: 35000 }
      - { household_size: 2, max_income: 42000 }
      - { household_size: 3, max_income: 48000 }
```

### 3) Rule set

```yaml
rule_set:
  name: "federal_eligibility"
  precedence: "deny_overrides_allow"   # other options: first_match, priority_order

rules:
  - id: "FED-RESIDENCY"
    kind: "deny"
    when: "Applicant.resident == false"
    then:
      - add_reason:
          code: "NOT_RESIDENT"
          message: "Applicant must be a resident."
          citations:
            - { label: "42 USC § 1437a" }

  - id: "FED-MIN-AGE"
    kind: "deny"
    when: "Applicant.age < MIN_AGE"
    then:
      - add_reason:
          code: "UNDERAGE"
          message: "Applicant must be at least 18 years old."
          citations:
            - { label: "24 CFR § 5.403" }

  - id: "FED-INCOME"
    kind: "deny"
    when: "Applicant.annual_income > table('income_limit_by_household', Applicant.household_size).max_income"
    then:
      - add_reason:
          code: "INCOME_TOO_HIGH"
          message: "Income exceeds the limit for household size."
          citations:
            - { label: "24 CFR § 5.609" }

  - id: "FED-ALLOW"
    kind: "allow"
    when: "true"
    then:
      - set: { eligible: true }
```

**Notes for transpilers**

-   `kind: deny/allow` makes compilation easy to “deny wins” logic (OPA style) or DMN hit policies.
-   `add_reason` gives explainability without needing an engine-specific tracer.
-   `table()` is declarative and maps to DMN tables, Rego data, or Drools facts.

---

Jurisdiction layering (federal → state → city)
----------------------------------------------

You’ll want a _composition DSL_ that defines how modules merge.

### Overlay bundle example (Illinois overrides)

```yaml
bundle: "civics:benefits"
version: "2026Q1"
effective: { start: 2026-01-01, end: 2026-03-31 }
jurisdiction: { level: state, country: US, state: IL }

overlays:
  - target_module: "eligibility.housing_assistance"
    strategy: "add_stricter_denials"     # other: replace_rule_set, override_by_id
    rules:
      - id: "IL-INCOME-ADJUST"
        kind: "deny"
        when: "Applicant.annual_income > 45000 && Applicant.household_size == 3"
        then:
          - add_reason:
              code: "IL_INCOME_TOO_HIGH"
              message: "Illinois sets a lower income cap for household size 3."
              citations:
                - { label: "305 ILCS 5/xx-x" }
```

### City overlay example (Chicago adds requirement)

```yaml
bundle: "civics:benefits"
version: "2026Q1"
jurisdiction: { level: city, country: US, state: IL, city: Chicago }
effective: { start: 2026-01-01, end: 2026-03-31 }

overlays:
  - target_module: "eligibility.housing_assistance"
    strategy: "add_stricter_denials"
    rules:
      - id: "CHI-RESIDENCY-DURATION"
        kind: "deny"
        when: "Applicant.resident == true && Applicant.residency_months < 6"
        then:
          - add_reason:
              code: "CHI_RESIDENCY_TOO_SHORT"
              message: "Chicago requires 6+ months of residency."
              citations:
                - { label: "Chicago Municipal Code § x-x-x" }
```

To support this, the fact schema can include `Applicant.residency_months`.

---

Tax filing instructions example
-------------------------------

Taxes often need:
-   computed values
-   conditional instructions
-   outputs beyond booleans

### Module

```yaml
module: "tax.filing_basics"
jurisdiction: { level: federal, country: US }

facts:
  Taxpayer:
    fields:
      filing_status: { type: enum, values: [single, mfj, mfs, hoh] }
      age: { type: int }
      has_w2: { type: bool }
      has_1099: { type: bool }
      self_employed: { type: bool }
      gross_income: { type: money, currency: USD }
      withholding: { type: money, currency: USD }

decisions:
  must_file: { type: bool, default: false }
  forms:     { type: set, item: string, default: [] }
  instructions: { type: list, item: Instruction, default: [] }
  reasons:   { type: list, item: Reason, default: [] }

types:
  Instruction:
    fields:
      step: { type: string }
      message: { type: string }
      citations: { type: list, item: Citation }
```

### Rules

```yaml
constants:
  SINGLE_THRESHOLD: 14600   # example placeholder

rule_set:
  name: "filing_requirement"
  precedence: "priority_order"

rules:
  - id: "ADD-FORM-1040"
    priority: 10
    when: "true"
    then:
      - add_to_set: { forms: "Form 1040" }

  - id: "SELF_EMPLOYED_SCHEDULE_C"
    priority: 20
    when: "Taxpayer.self_employed == true"
    then:
      - add_to_set: { forms: "Schedule C" }
      - add_instruction:
          step: "Report self-employment income"
          message: "Complete Schedule C for business income/expenses."
          citations:
            - { label: "IRS Instructions for Schedule C" }

  - id: "MUST_FILE_SINGLE"
    priority: 30
    when: "Taxpayer.filing_status == 'single' && Taxpayer.gross_income >= SINGLE_THRESHOLD"
    then:
      - set: { must_file: true }
      - add_reason:
          code: "INCOME_OVER_THRESHOLD"
          message: "Gross income meets or exceeds the filing threshold."
          citations:
            - { label: "26 USC § 6012" }
```

This is intentionally “instructional”—it outputs forms/instructions, not just allow/deny.

---

Expression language (minimal)
-----------------------------

Keep it small so you can transpile to almost anything:

-   literals: numbers, strings, booleans, dates
-   field access: `Applicant.age`
-   boolean ops: `&& || !`
-   comparisons: `== != < <= > >=`
-   arithmetic: `+ - * /`
-   functions:
    -   `table(name, key...).field`
    -   `in(value, [a,b,c])`
    -   `exists(field)` / `is_null(field)`
    -   `date("YYYY-MM-DD")`, `between(date, start, end)`

---

Compilation targets (how this maps later)
-----------------------------------------

This DSL is basically an **intermediate representation**:

-   **OPA/Rego**: rules become derived booleans/sets; tables become data; reasons become structured outputs.
-   **DMN**: tables map directly; precedence maps to hit policies; reason codes become outputs.
-   **Drools**: facts are working memory; rules map to LHS/RHS; reasons are inserted.

Because you’ve separated:
-   metadata
-   tables/constants
-   pure expressions
-   deterministic actions (`set`, `add_reason`, `add_instruction`)

…you’re not locked in.

---

What I’d build first (minimum viable)
-------------------------------------

1.  **Parser** (YAML → AST) with schema validation
2.  **Reference interpreter** (slow but correct) to run tests
3.  **Golden test harness** (fixtures per jurisdiction + quarter)
4.  **Transpiler** to your first engine once semantics stabilize

The reference interpreter is critical: it becomes your “semantic source of truth” while you swap engines.

---

Possible next steps:
-   a formal EBNF-style grammar (if you prefer a text syntax over YAML),
-   a precise precedence/merge algorithm for overlays,
-   and a canonical JSON AST shape to make the transpiler straightforward.
