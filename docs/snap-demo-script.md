# Xlator SNAP Eligibility POC — Demo Script

This document walks through the full Xlator pipeline end-to-end using SNAP income eligibility rules as the first real translation.

## What This Demonstrates

```
domains/snap/input/policy_docs/snap_eligibility_fy2026.md   ← real USDA FNS policy
    ↓  (Claude Code skill: translate-policy)
domains/snap/specs/eligibility.civil.yaml                   ← CIVIL DSL intermediate representation
    ↓  (make snap-transpile)
domains/snap/output/eligibility.rego                        ← OPA/Rego policy (generated)
    ↓  (OPA REST server)
domains/snap/demo/main.py (FastAPI)                         ← API layer
    ↓  (HTTP)
domains/snap/demo/static/index.html                         ← browser form
```

---

## Prerequisites

**Required:**

```bash
# OPA CLI
brew install opa
opa version   # should print v0.x.x

# Python 3.11+ and uv
python --version
brew install uv   # or: curl -LsSf https://astral.sh/uv/install.sh | sh

# Create and activate virtual environment
uv venv
source .venv/bin/activate

# Install demo Python packages
uv pip install -r domains/snap/demo/requirements.txt
```

**Optional (to run tests):**

```bash
uv pip install pyyaml   # already included in demo/requirements.txt
```

---

## Step-by-Step Walkthrough

### 1. Review the Source Policy Document

Open [domains/snap/input/policy_docs/snap_eligibility_fy2026.md](domains/snap/input/policy_docs/snap_eligibility_fy2026.md). This is what the Claude Code translation skill reads. It contains:

- Gross income test: 130% FPL, elderly/disabled exempt
- Net income test: 100% FPL after deductions
- FY2026 income thresholds by household size
- Deduction types and their order (earned income, standard, dependent care, shelter)
- Legal citations throughout (7 CFR § 273.9)

### 2. Review the CIVIL Module

Open [domains/snap/specs/eligibility.civil.yaml](domains/snap/specs/eligibility.civil.yaml). This is the intermediate representation — what Xlator produces before compilation to any specific rule engine.

Key sections:
- `facts: Household:` — 8 input fields including earned/unearned income split and shelter costs
- `tables:` — FY2026 gross/net limits and standard deductions by household size (1–8)
- `computed:` — intermediate values: deduction chain, gross/net limits, passes_* flags
- `rules:` — 3 rules: deny gross, deny net, allow if both pass

### 3. Validate the CIVIL Module

```bash
make snap-validate
# Expected: ✓ domains/snap/specs/eligibility.civil.yaml is valid CIVIL
```

### 4. Generate the OPA/Rego Policy

```bash
make snap-transpile
# Expected: ✓ Transpiled to domains/snap/output/eligibility.rego
```

Then syntax-check the generated Rego:

```bash
opa check domains/snap/output/eligibility.rego
# Expected: (no output = clean)
```

Open [domains/snap/output/eligibility.rego](domains/snap/output/eligibility.rego) and notice:
- Income threshold dicts populated from CIVIL tables
- `gross_limit`/`net_limit` with `conditional:` fallback for household size 9+
- Full deduction chain: `earned_income_deduction` → `standard_deduction` → `dependent_care_deduction` → `shelter_excess` → `shelter_deduction` → `net_income`
- `default passes_gross_test := false` pattern (critical: OPA boolean rules are undefined, not false)
- `decision` object with `eligible`, `denial_reasons`, and `computed` breakdown

### 5. Run the Test Suite

Start OPA, then run all 8 test cases:

```bash
# Terminal 1: Start OPA
opa run --server --addr :8181 domains/snap/output/eligibility.rego

# Terminal 2: Run tests
make snap-test
```

Expected output:
```
Running: Test cases for federal SNAP income eligibility (FY2026)
Cases:   8

  PASS  allow_001: Household of 3 with low income passes both tests
  PASS  deny_gross_001: Gross income exceeding 130% FPL denied at gross test
  PASS  deny_net_001: Passes gross, fails net income test
  PASS  allow_elderly_001: Elderly household exempt from gross test
  PASS  deny_elderly_net_001: Elderly fails net test despite gross exemption
  PASS  allow_shelter_001: Shelter deduction brings net income below limit
  PASS  boundary_gross_001: Gross exactly at limit passes (boundary condition)
  PASS  deny_large_001: Household of 9 denied via formula threshold

Results: 8 passed, 0 failed out of 8 total
```

### 6. Start the Demo

```bash
make snap-demo
```

This starts OPA (port 8181) and FastAPI (port 8000).

Open: **http://localhost:8000/static/index.html**

### 7. Try These Scenarios

#### Scenario A: Clear eligible household

| Field | Value |
|---|---|
| Household size | 3 |
| Elderly/disabled | No |
| Gross monthly income | $1,800 |
| Earned income | $0 |
| Shelter costs | $500 |

Expected: **ELIGIBLE**. Net income = $1,591 (gross $1,800 − std ded $209 = $1,591, no shelter excess). Both tests pass.

#### Scenario B: Gross income fails

| Field | Value |
|---|---|
| Household size | 3 |
| Elderly/disabled | No |
| Gross monthly income | $3,200 |
| Earned income | $3,200 |
| Shelter costs | $800 |

Expected: **INELIGIBLE** — `GROSS_INCOME_EXCEEDS_LIMIT`. Gross $3,200 > limit $2,888 for size 3.

#### Scenario C: Elderly exemption saves the day

| Field | Value |
|---|---|
| Household size | 3 |
| Elderly member | ✓ |
| Gross monthly income | $3,200 |
| Earned income | $0 |
| Shelter costs | $2,400 |

Expected: **ELIGIBLE**. High gross income (would fail gross test for non-elderly), but elderly exemption applies. After deductions: std ded $209, shelter excess = max(0, $2,400 − 50% × $2,991) = $904.50, no cap (elderly). Net = $2,086.50 < net limit $2,221. ✓

### 8. Explore the API Directly

```bash
curl -s -X POST http://localhost:8000/api/snap/eligibility \
  -H "Content-Type: application/json" \
  -d '{
    "household_size": 3,
    "has_elderly_member": false,
    "has_disabled_member": false,
    "gross_monthly_income": 1800,
    "earned_income": 0,
    "unearned_income": 1800,
    "shelter_costs_monthly": 500,
    "dependent_care_costs": 0
  }' | python -m json.tool
```

The API documentation is at: http://localhost:8000/docs

---

## Tracing the Full Pipeline

For a given decision, you can trace the full lineage:

1. **Policy text** → `domains/snap/input/policy_docs/snap_eligibility_fy2026.md` (with CFR citations)
2. **CIVIL intent** → `domains/snap/specs/eligibility.civil.yaml` (rule `FED-SNAP-DENY-001`)
3. **Rego execution** → `domains/snap/output/eligibility.rego` (`passes_gross_test`, `denial_reasons`)
4. **API response** → `denial_reasons[].citation = "7 CFR § 273.9(a)(1)"`
5. **Browser display** → Denial reason with citation shown to caseworker

---

## Extending to a New Policy

Use the Claude Code translation skill to translate another policy:

```
/translate-policy
```

The skill will:
1. Ask which document in `domains/<name>/input/policy_docs/` to translate
2. Guide through identifying facts, decisions, tables, and rules
3. Draft the CIVIL module and test cases
4. Request human review before transpiling
5. Run the test suite and report results

---

## Troubleshooting

**"OPA server not reachable"** — Make sure OPA is running before starting FastAPI:
```bash
opa run --server --addr :8181 domains/snap/output/eligibility.rego
curl http://localhost:8181/health  # should return {}
```

**"Policy engine returned undefined"** — A required input field is missing. All numeric fields default to 0, so this usually means `household_size` wasn't provided.

**"opa command not found"** — Install OPA: `brew install opa`

**Tests fail after regenerating Rego** — Restart the OPA server; it doesn't hot-reload.

---

## File Inventory

| File | Purpose |
|---|---|
| `domains/snap/input/policy_docs/snap_eligibility_fy2026.md` | Source policy document |
| `domains/snap/specs/eligibility.civil.yaml` | CIVIL intermediate representation |
| `domains/snap/specs/tests/eligibility_tests.yaml` | 8 test cases |
| `specs/ruleset_schema.yaml` | CIVIL DSL schema reference |
| `tools/validate_civil.py` | Validates CIVIL YAML structure |
| `tools/transpile_to_opa.py` | CIVIL → OPA/Rego transpiler |
| `tools/run_tests.py` | Runs YAML test cases against OPA REST |
| `domains/snap/output/eligibility.rego` | Generated OPA policy (do not edit) |
| `domains/snap/demo/main.py` | FastAPI backend |
| `domains/snap/demo/static/index.html` | Browser form |
| `domains/snap/demo/start.sh` | Starts OPA + FastAPI |
| `.claude/skills/translate-policy.md` | Claude Code skill for pipeline reuse |
