# Draft or Update Test Cases

Create or update the test suite for a CIVIL module based on its current specs.

## Input

```
/create-tests [<domain>]                  # auto-detect program or prompt if ambiguous
/create-tests [<domain> <program>]        # target a specific <program>.civil.yaml
```

If `<domain>` is not provided, list all `domains/*/specs/*.civil.yaml` files and prompt the user to choose.

## Pre-flight

1. **Domain folder exists?** — NO → Print: "Domain `<domain>` not found. Run `/extract-ruleset <domain>` first." Stop.
2. **CIVIL file exists?**
   - `domains/<domain>/specs/<program>.civil.yaml` missing → Print: "No CIVIL file found. Run `/extract-ruleset <domain>` first." Stop.
3. **`specs/tests/` directory exists?** — NO → create `domains/<domain>/specs/tests/` silently.

## Mode Detection

```bash
ls domains/<domain>/specs/tests/<program>_tests.yaml 2>/dev/null
```

| Result | Mode |
|--------|------|
| File absent | **CREATE mode** — write new test suite from CIVIL file |
| File present | **UPDATE mode** — update stale test cases |

---

## Process — CREATE Mode

Read `domains/<domain>/specs/<program>.civil.yaml` to understand:
- All fact fields (types, optionality)
- All decisions (e.g., `eligible`, `denial_reasons`)
- All deny rules and their conditions
- All computed fields involved in eligibility thresholds
- All tables and constants referenced in rules

Draft at minimum 6 test cases covering:

| Tag | What to cover |
|-----|---------------|
| `allow` | All conditions comfortably met (happy path) |
| `deny` + gross test | Fails gross income threshold (if one exists) |
| `deny` + net test | Passes gross, fails net after deductions (if net check exists) |
| `allow` + exemption | Elderly, disabled, or other exemption path (if one exists) |
| `allow` + boundary | Income or value exactly at a threshold (≤ limit = pass) |
| `deny` + edge | Large household (size 9+), all-zero income, or other extreme |

**Test format** (inputs always flat key-value, never nested by entity name):

```yaml
test_suite:
  spec: "<program>.civil.yaml"
  description: "..."
  version: "1.0"

tests:
  - case_id: "allow_001"
    description: "..."
    inputs:
      household_size: 3
      gross_monthly_income: 1800
      # ... flat key-value
    expected:
      eligible: true
      denial_reasons: []
    tags: ["happy_path", "allow"]
```

**Reference:** See `domains/snap/specs/tests/eligibility_tests.yaml` for a complete working example.

Write to `domains/<domain>/specs/tests/<program>_tests.yaml`.

---

## Process — UPDATE Mode

### Step 1: Load Stale-Case Hints

Check for `domains/<domain>/specs/.stale-cases.yaml`:

- **If present** (written by `/extract-ruleset` in this session): load the stale case list from it. These are cases whose `inputs` contain values that matched old table boundaries or constants now changed.
- **If absent** (standalone run after a manual CIVIL edit): compare each test case's `inputs` values against all current `tables:` rows and `constants:` values in the CIVIL file. Flag any case where an input value exactly matches a value that no longer appears in any table row or constant.

  Print: "No `.stale-cases.yaml` found — using table/constant comparison to detect stale cases. Logic-only rule changes (e.g., operator changes, new conditions) will not be detected; review manually."

### Step 2: Update Stale Cases

For each stale case:
- Update threshold values in `inputs` and `expected` to match the current CIVIL tables and constants
- Preserve all other fields unchanged (`case_id`, `description`, `tags`)

If no stale cases were identified:
```
No stale cases detected. Review manually for logic-only rule changes.
```
Proceed to Step 3.

### Step 3: Add New Coverage

Read the current CIVIL file. For any deny rules, computed fields, or exemption paths not covered by an existing test case, add new cases to fill coverage gaps. Aim to maintain the 6-tag coverage from CREATE mode.

### Step 4: Write Updated Test File

Overwrite `domains/<domain>/specs/tests/<program>_tests.yaml` with the updated suite.

### Step 5: Clean Up Sidecar

Delete `domains/<domain>/specs/.stale-cases.yaml` if it exists (prevents stale hints on the next standalone run).

---

## Common Mistakes to Avoid

- **Don't nest inputs by entity name** — inputs are always flat key-value
- **Don't change `case_id` values** when updating stale cases — preserve existing IDs
- **Don't delete cases that aren't stale** — only update or add; removal is a human decision
- **Omit optional fact fields** that aren't relevant to a test case — only include inputs the test actually depends on
