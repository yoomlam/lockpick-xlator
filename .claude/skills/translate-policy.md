# Translate Policy Document to CIVIL Module

Translate a government policy document into a CIVIL DSL module following the Xlator pipeline conventions.

## Input

A policy document in `input/policy_docs/` (Markdown, plain text, or PDF text).

If no document is specified, list the files in `input/policy_docs/` and ask which one to translate.

## Process

### Step 1: Read the Policy Document

Read the source document thoroughly. Identify:

1. **Program name and jurisdiction** — what benefit/program, which level of government, which states/jurisdiction
2. **Effective dates** — when do these rules apply?
3. **Applicant/household facts** — what information does a caseworker collect? (income, family size, age, etc.)
4. **Eligibility decisions** — what yes/no determinations does the policy make?
5. **Income thresholds and lookup tables** — are there tables of dollar amounts by household size, age band, etc.?
6. **Named constants** — fixed rates, percentages, dollar amounts used in rules
7. **The rules themselves** — what conditions produce allow vs. deny? What reasons are given?
8. **Legal citations** — CFR sections, USC provisions, or other citable authority for each rule

### Step 2: Identify CIVIL Components

Map the policy document to CIVIL DSL constructs:

| Policy Element | CIVIL Construct |
|---|---|
| Household/applicant inputs | `facts:` entity with typed fields |
| Eligibility outcome | `decisions:` (usually `eligible: bool`) |
| Denial/approval explanations | `decisions: denial_reasons: list[Reason]` |
| Dollar thresholds by size | `tables:` with key/value rows |
| Fixed rates/amounts | `constants:` |
| **Intermediate derived values** | **`computed:` fields (CIVIL v2)** |
| Income/asset test | `rules:` with `kind: deny` |
| Pass all tests → eligible | `rules:` with `kind: allow`, `when: "true"` |

### Step 3: Draft the CIVIL Module

Create the CIVIL YAML file at `specs/ruleset/<program_name>.civil.yaml`.

**Follow the exact structure from `specs/ruleset/schema.yaml`:**

```yaml
module: "eligibility.<program_name>"
description: "..."
version: "<year>Q<quarter>"
jurisdiction:
  level: federal  # or: state, county, city
  country: US
  # state: <code>  # if state-level
effective:
  start: YYYY-MM-DD
  end: YYYY-MM-DD  # optional

facts:
  <EntityName>:
    description: "..."
    fields:
      <field_name>:
        type: <int|float|bool|string|money|date|list|set|enum>
        description: "..."
        currency: USD  # for money type
        optional: true  # if not required

decisions:
  eligible:
    type: bool
    default: false
    description: "..."
  denial_reasons:
    type: list
    item: Reason
    default: []
    description: "..."

tables:
  <table_name>:
    description: "..."
    key: [<key_field>]
    value: [<value_field>]
    rows:
      - { <key_field>: <val>, <value_field>: <val> }

constants:
  UPPER_SNAKE_CASE_NAME: value

computed:  # optional (CIVIL v2) — intermediate derived values for multi-step formulas
  <field_name>:
    type: <money|bool|float|int>
    description: "..."
    expr: "<CIVIL expression>"     # single expression
  # For conditional (if/then/else):
  <field_name_2>:
    type: money
    description: "..."
    conditional:
      if: "<bool expression>"
      then: "<value expression>"
      else: "<value expression>"

rule_set:
  name: "<identifier>"
  precedence: "deny_overrides_allow"
  description: "..."

rules:
  - id: "<JURISDICTION>-<TOPIC>-<SEQ>"  # e.g., FED-SNAP-DENY-001
    kind: deny  # or: allow
    priority: 1  # lower = higher priority; allow rules typically 100+
    description: "..."
    when: "<CIVIL expression>"
    then:
      - add_reason:
          code: "MACHINE_CODE"
          message: "Human-readable explanation"
          citations:
            - label: "7 CFR § 273.9(a)(1)"
              url: "https://..."
              excerpt: "Brief excerpt"
```

**Reference:** See `specs/ruleset/example_benefit.yaml` for a complete working example.

**CIVIL Expression Language** (for `when:` clauses and `computed:` expressions):
- Field access: `Household.household_size`, `Applicant.age`
- Constants: `MIN_AGE`, `INCOME_MULTIPLIER`
- Table lookup: `table('gross_income_limits', Household.household_size).max_gross_monthly`
- Boolean: `&&`, `||`, `!`
- Comparison: `==`, `!=`, `<`, `<=`, `>`, `>=`
- Arithmetic: `+`, `-`, `*`, `/`
- Functions: `exists(field)`, `is_null(field)`, `between(value, min, max)`, `in(value, [a, b, c])`
- `computed:` only: `max(a, b)`, `min(a, b)` — numeric comparison; computed field names as bare identifiers

**Multi-step formulas (CIVIL v2):** If a rule requires multi-step arithmetic with intermediate variables (e.g., a deduction chain where each step depends on the prior), use a `computed:` section to define each step. The `when:` clause can then reference the final computed field name directly.

### Step 4: Run the Validator

```bash
python tools/validate_civil.py specs/ruleset/<program_name>.civil.yaml
```

Fix any errors reported before proceeding.

### Step 5: Draft Test Cases

Create `specs/tests/<program_name>_tests.yaml` with at least 6 test cases:

Required coverage:
- **1 clear allow** — all conditions comfortably met
- **1 gross income deny** (if there's a gross income test)
- **1 net income deny** — passes gross, fails net after deductions
- **1 exemption case** — elderly, disabled, or other exemption path
- **1 boundary case** — income exactly at a threshold (should pass if ≤ limit)
- **1 edge case** — large household (size 9+), all-zero income, or other edge condition

Test case format:
```yaml
test_suite:
  spec: "<program_name>.civil.yaml"
  description: "..."
  version: "1.0"

tests:
  - case_id: "allow_001"
    description: "..."
    inputs:
      household_size: 3
      gross_monthly_income: 1800
      # ... (flat key-value, not nested by entity name)
    expected:
      eligible: true
      denial_reasons: []
    tags: ["happy_path", "allow"]
```

**Reference:** See `specs/tests/example_benefit_tests.yaml` for structure.

### Step 6: Human Review Gate

Before transpiling, present a summary:

1. Show the list of rules translated
2. Quote the source policy text for each rule
3. Show the CIVIL `when:` expression that implements it
4. Ask: "Does this translation correctly capture the policy intent? Any rules missing or incorrect?"

**Do not proceed to transpilation until the human confirms.**

### Step 7: Transpile and Test

Once the human approves:

```bash
# Generate OPA/Rego
python tools/transpile_to_opa.py specs/ruleset/<program_name>.civil.yaml output/ruleset/<program_name>.rego

# Syntax check
opa check output/ruleset/<program_name>.rego

# Start OPA and run tests
opa run --server --addr :8181 output/ruleset/<program_name>.rego &
sleep 2
python tools/run_tests.py specs/tests/<program_name>_tests.yaml
```

Report the test results to the user.

## Output

- `input/policy_docs/<source>.md` — policy source document
- `specs/ruleset/<program_name>.civil.yaml` — CIVIL module (validated ✓)
- `specs/tests/<program_name>_tests.yaml` — test cases
- `output/ruleset/<program_name>.rego` — generated OPA/Rego (syntax checked ✓, tests passing ✓)

## Common Mistakes to Avoid

- **Don't nest inputs by entity name** in test cases — inputs are always flat key-value
- **Don't forget `default eligible := false`** in the transpiler — OPA boolean rules are undefined, not false, when conditions don't match
- **Don't forget `default passes_<test> := false`** for intermediate boolean rules
- **Cite the actual CFR/USC section** for each rule, not just "Program Policy Manual"
- **Use `optional: true`** for fact fields that may not always be provided (e.g., `earned_income`, `shelter_costs`)
- **Distinguish earned vs. unearned income** if any deduction applies only to earned income
- **Use `computed:` for multi-step formulas** — don't reference undefined identifiers in `when:` clauses; if a value needs multiple steps to compute, define it in `computed:` and reference it by name
