---
title: "feat: SNAP Eligibility Rules-as-Code End-to-End POC"
type: feat
status: completed
date: 2026-02-17
brainstorm: docs/brainstorms/2026-02-17-first-translation-poc-brainstorm.md
---

# feat: SNAP Eligibility Rules-as-Code End-to-End POC

## Overview

Build a complete end-to-end proof of concept demonstrating the Xlator pipeline using real SNAP (Supplemental Nutrition Assistance Program) eligibility rules from USDA FNS. A caseworker enters household facts into a browser form; the system evaluates eligibility using machine-executable rules transpiled from a CIVIL DSL module, returning an `eligible`/`ineligible` decision with a deduction breakdown and denial reasons — all traceable back to federal regulation citations.

```
input/policy_docs/snap_eligibility_fy2026.md
    → Claude Code skill (translate-policy)
    → specs/ruleset/snap_eligibility.civil.yaml
    → tools/transpile_to_opa.py
    → output/ruleset/snap_eligibility.rego
    → OPA REST server (port 8181)
    ← demo/main.py (FastAPI, port 8000)
    ← demo/static/index.html (browser form)
```

---

## Problem Statement

Xlator has a well-designed CIVIL DSL specification but no running code and no real-world translation. Without a working end-to-end demo, the value proposition — that AI-assisted translation from government policy to machine-executable rules actually works — cannot be validated or demonstrated. This POC closes that gap using SNAP, a widely-understood government benefit whose income eligibility rules are publicly documented and well-suited to Rules-as-Code treatment.

---

## SNAP Rules in Scope (FY2026, 48 States + D.C.)

### Gross Income Test
- Limit: 130% of Federal Poverty Level
- Households with an elderly (age 60+) or disabled member are **exempt**

### Net Income Test
- Limit: 100% of Federal Poverty Level
- Applied after allowable deductions; **all households** must pass

### Allowable Deductions (applied in this order)
1. **20% earned income deduction** — applied to earned income only
2. **Standard deduction** — by household size ($209 for 1–3, $223 for 4, $261 for 5, $299 for 6+)
3. **Dependent care deduction** — actual costs when needed for work/training
4. **Excess shelter deduction** — shelter costs above 50% of income after prior deductions; capped at $744 (no cap if elderly/disabled member)

### FY2026 Thresholds

| Household Size | Gross Limit (130% FPL) | Net Limit (100% FPL) |
|---|---|---|
| 1 | $1,696 | $1,305 |
| 2 | $2,292 | $1,763 |
| 3 | $2,888 | $2,221 |
| 4 | $3,483 | $2,680 |
| 5 | $4,079 | $3,138 |
| 6 | $4,675 | $3,596 |
| 7 | $5,271 | $4,055 |
| 8 | $5,867 | $4,513 |
| 9+ | +$596/person | +$459/person |

### Out of Scope for This POC
- Asset/resource limits
- Categorical eligibility (BBCE) and state-level overlays
- Medical deduction (elderly/disabled out-of-pocket expenses)
- Homeless shelter standard
- Multiple rule engine targets (Drools, DMN)
- Packaging as a Claude plugin

---

## Technical Approach

### Architecture

```
Browser (index.html)
    POST /api/snap/eligibility (JSON: HouseholdFacts)
        ↓
FastAPI (demo/main.py :8000)
    POST http://localhost:8181/v1/data/snap/eligibility/decision
        ↓
OPA REST server (:8181)
    evaluates: output/ruleset/snap_eligibility.rego
        ↓
{"result": {"eligible": bool, "denial_reasons": [...], "computed": {...}}}
        ↑
FastAPI returns EligibilityResponse JSON
        ↑
Browser renders: eligible badge + deduction breakdown table + denial reasons list
```

### Key Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| CIVIL validation | Hand-written Python validator | `schema.yaml` is a reference doc, not JSON Schema; can't use `jsonschema` directly |
| OPA integration | REST server (`opa run --server`) | Avoids subprocess overhead per request; standard production pattern |
| HTTP client | `httpx.AsyncClient` | Async-native with FastAPI; handles OPA REST calls cleanly |
| Net income computation | Expressed in Rego, referenced in CIVIL `when:` clause | CIVIL lacks intermediate variable binding; Rego handles multi-step arithmetic natively |
| Test runner | Python script calling OPA REST API per YAML test case | Preserves the CIVIL test YAML format; reusable across rule engines |
| Household size 9+ | Formula in Rego: base + (size - 8) × increment | CIVIL table covers 1–8; Rego `else` clause handles overflow |
| Income inputs | Separate `earned_income` + `unearned_income` | 20% deduction applies only to earned income; SNAP statute requires the distinction |

---

## Implementation Phases

### Phase 1: Input Material + CIVIL Module

**Deliverables:**
- `input/policy_docs/snap_eligibility_fy2026.md`
- `specs/ruleset/snap_eligibility.civil.yaml`
- `specs/tests/snap_eligibility_tests.yaml`
- `tools/validate_civil.py`

#### 1.1 Source SNAP Policy Document

Create `input/policy_docs/snap_eligibility_fy2026.md` summarizing SNAP income eligibility rules from USDA FNS:
- Both income tests (gross + net)
- FY2026 threshold tables
- All deduction types and their order
- Elderly/disabled exemptions
- Cite 7 CFR § 273.9 throughout

This document is what the Claude Code translation skill reads. It should be clean prose + tables with legal citations, not scraped HTML.

#### 1.2 CIVIL Module

Create `specs/ruleset/snap_eligibility.civil.yaml` with this structure:

**Module header:**
```yaml
module: "eligibility.snap_federal"
description: "Federal SNAP income eligibility — gross and net income tests (FY2026, 48 states + D.C.)"
version: "2026Q1"
jurisdiction:
  level: federal
  country: US
effective:
  start: 2025-10-01
  end: 2026-09-30
```

**Facts entity (`Household`):**
```yaml
facts:
  Household:
    fields:
      household_size:         { type: int,   description: "Number of SNAP household members" }
      has_elderly_member:     { type: bool,  description: "Age 60+ member present (7 CFR § 273.1)", optional: true }
      has_disabled_member:    { type: bool,  description: "SSI/SSDI or disability criteria met (7 CFR § 273.1)", optional: true }
      gross_monthly_income:   { type: money, currency: USD, description: "Total monthly income before deductions" }
      earned_income:          { type: money, currency: USD, description: "Monthly earned income (wages, self-employment)", optional: true }
      unearned_income:        { type: money, currency: USD, description: "Monthly unearned income (Social Security, child support, etc.)", optional: true }
      shelter_costs_monthly:  { type: money, currency: USD, description: "Monthly shelter costs (rent/mortgage + utilities)", optional: true }
      dependent_care_costs:   { type: money, currency: USD, description: "Monthly out-of-pocket dependent care costs for work/training", optional: true }
```

**Decisions:**
```yaml
decisions:
  eligible:        { type: bool,  default: false, description: "Meets SNAP income eligibility criteria" }
  denial_reasons:  { type: list,  item: Reason,   description: "Reasons for ineligibility" }
  net_income:      { type: money, description: "Computed net monthly income after allowable deductions" }
```

**Tables:** `gross_income_limits`, `net_income_limits`, `standard_deductions` — one row per household size 1–8, with a formula note for 9+

**Rules:**
- `FED-SNAP-DENY-001`: Deny if gross income exceeds limit AND no elderly/disabled exemption (7 CFR § 273.9(a)(1))
- `FED-SNAP-DENY-002`: Deny if net income (after all deductions) exceeds net limit (7 CFR § 273.9(a)(2))
- `FED-SNAP-ALLOW-001`: Allow if both income tests pass
- Note in comments: CIVIL v1 lacks intermediate variable binding; the net income formula is fully expressed in the generated Rego, not in the CIVIL `when:` clause

#### 1.3 Test Cases

Create `specs/tests/snap_eligibility_tests.yaml` with 8 test cases:

| case_id | scenario | expected |
|---|---|---|
| `allow_001` | Household of 3, income well below both limits | eligible |
| `deny_gross_001` | Household of 3, gross > 130% FPL | ineligible (gross test) |
| `deny_net_001` | Household of 3, passes gross, fails net | ineligible (net test) |
| `allow_elderly_001` | Elderly member, high gross (would fail gross test), low net | eligible (exempt from gross) |
| `deny_elderly_net_001` | Elderly member, fails net test despite exemption | ineligible |
| `allow_shelter_001` | Shelter deduction pushes net income below limit | eligible |
| `boundary_gross_001` | Gross income exactly at 130% FPL limit | eligible (at-limit = pass) |
| `deny_large_001` | Household of 9, tests formula threshold | ineligible |

#### 1.4 CIVIL Validator

Create `tools/validate_civil.py` — a Python script that reads a CIVIL YAML file and checks:
- All required top-level keys present (`module`, `description`, `version`, `jurisdiction`, `effective`, `facts`, `decisions`, `rule_set`, `rules`)
- `jurisdiction.level` is one of: `federal`, `state`, `county`, `city`
- Each rule has `id`, `kind` (deny/allow), `priority`, `when`, `then`
- Exits with code 0 on success, 1 with descriptive errors on failure

```
Usage: python tools/validate_civil.py specs/ruleset/snap_eligibility.civil.yaml
```

---

### Phase 2: OPA Transpiler + Verification

**Deliverables:**
- `tools/transpile_to_opa.py`
- `output/ruleset/snap_eligibility.rego`
- `tools/run_tests.py`

#### 2.1 Transpiler (`tools/transpile_to_opa.py`)

Python script that reads a CIVIL YAML module and emits a Rego policy file.

For the SNAP module specifically, the transpiler must:
- Emit `package snap.eligibility` and `import future.keywords.if`
- Build income threshold lookup dicts from CIVIL tables (sizes 1–8)
- Implement size 9+ formula as Rego `else` clauses
- Compute net income in a properly ordered sequence:
  1. `earned_income_deduction := input.earned_income * 0.20`
  2. `standard_deduction` from table (size → amount)
  3. `dependent_care_deduction := input.dependent_care_costs`
  4. `shelter_excess` = `max(0, shelter_costs - 0.50 × income_after_prior_deductions)`
  5. `shelter_deduction` = `min(shelter_excess, 744)` unless elderly/disabled → no cap
  6. `net_income` = gross minus all deductions above
- Emit `default eligible := false` to prevent undefined results
- Return a structured `decision` object: `{eligible, denial_reasons, computed: {net_income, deductions_applied}}`

```
Usage: python tools/transpile_to_opa.py specs/ruleset/snap_eligibility.civil.yaml output/ruleset/snap_eligibility.rego
```

#### 2.2 Rego Verification Steps

After generating `output/ruleset/snap_eligibility.rego`:
1. `opa check output/ruleset/snap_eligibility.rego` — syntax check
2. `opa run --server --addr :8181 output/ruleset/snap_eligibility.rego` — start server
3. Run `tools/run_tests.py` — confirm all 8 test cases pass

#### 2.3 Test Runner (`tools/run_tests.py`)

Python script that:
- Reads a CIVIL `_tests.yaml` file
- For each test case, POSTs `{"input": test.inputs}` to `http://localhost:8181/v1/data/snap/eligibility/decision`
- Compares `result.eligible` against `expected.eligible`
- Reports pass/fail per case with diff on failure
- Exits 0 if all pass, 1 if any fail

```
Usage: python tools/run_tests.py specs/tests/snap_eligibility_tests.yaml
```

---

### Phase 3: FastAPI Backend

**Deliverables:**
- `demo/main.py`
- `demo/requirements.txt`

#### 3.1 FastAPI App (`demo/main.py`)

```python
# demo/main.py — key structure

class HouseholdFacts(BaseModel):
    household_size: int
    has_elderly_member: bool = False
    has_disabled_member: bool = False
    gross_monthly_income: float
    earned_income: float = 0.0
    unearned_income: float = 0.0
    shelter_costs_monthly: float = 0.0
    dependent_care_costs: float = 0.0

class EligibilityResponse(BaseModel):
    eligible: bool
    denial_reasons: list[dict]
    computed: dict  # net_income, deductions_applied, gross_limit, net_limit

@app.post("/api/snap/eligibility", response_model=EligibilityResponse)
async def check_eligibility(facts: HouseholdFacts): ...
    # POST to http://localhost:8181/v1/data/snap/eligibility/decision
    # Parse body["result"]
    # Return 503 if OPA unreachable, 422 if result undefined
```

**Startup health check:** On startup, FastAPI verifies OPA is reachable at `http://localhost:8181/health` and logs a clear error if not.

#### 3.2 Dependencies (`demo/requirements.txt`)
```
fastapi
uvicorn[standard]
httpx
pydantic
```

---

### Phase 4: HTML Frontend

**Deliverables:**
- `demo/static/index.html`
- `demo/start.sh`

#### 4.1 HTML Form (`demo/static/index.html`)

Plain HTML + vanilla JS, no framework. Single page with:

**Form inputs:**
- `household_size` (number, 1–20)
- `has_elderly_member` (checkbox)
- `has_disabled_member` (checkbox)
- `gross_monthly_income` (number, dollar amount)
- `earned_income` (number, dollar amount, labeled "portion from wages/self-employment")
- `shelter_costs_monthly` (number, optional)
- `dependent_care_costs` (number, optional)

**Results display (below form, shown after submit):**
- Large badge: green "ELIGIBLE" or red "INELIGIBLE"
- Deduction breakdown table: shows gross income, each deduction amount, net income, net income limit
- Denial reasons list (only if ineligible): code + message + citation link
- Loading state during request; error message on 4xx/5xx

#### 4.2 Startup Script (`demo/start.sh`)

```bash
#!/usr/bin/env bash
# Start OPA server and FastAPI app together
opa run --server --addr :8181 ../output/ruleset/snap_eligibility.rego &
OPA_PID=$!
echo "OPA server started (PID $OPA_PID). Waiting for readiness..."
sleep 2
curl -sf http://localhost:8181/health || { echo "OPA failed to start"; kill $OPA_PID; exit 1; }
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

### Phase 5: Claude Code Translation Skill

**Deliverables:**
- `.claude/skills/translate-policy.md`

#### 5.1 Skill Design

The skill guides Claude through translating any government policy doc into a CIVIL module. Key steps the skill prescribes:

1. **Read the source document** from `input/policy_docs/`
2. **Identify the facts schema**: what inputs does a caseworker know about a household/person?
3. **Identify the decisions**: what yes/no determinations does the policy make?
4. **Identify constants and tables**: thresholds, rates, lookup values
5. **Identify the rules**: what conditions map to allow/deny + what reasons are given?
6. **Draft the CIVIL module** following `specs/ruleset/schema.yaml`
7. **Run the validator**: `python tools/validate_civil.py <output_file>`
8. **Draft test cases** covering at least: one clear allow, one gross deny, one net deny, one boundary case
9. **Human review gate**: present a diff of policy text vs. CIVIL module and ask for sign-off before proceeding to transpilation

The skill includes the CIVIL module structure as a template and references `specs/ruleset/example_benefit.yaml` as an annotated example.

---

### Phase 6: Documentation

**Deliverables:**
- `docs/snap-demo-script.md`

#### 6.1 Demo Script

Step-by-step walkthrough covering:
1. Prerequisites: OPA CLI installed, Python 3.11+, `pip install -r demo/requirements.txt`
2. Run the transpiler: `python tools/transpile_to_opa.py ...`
3. Run the validator: `python tools/validate_civil.py ...`
4. Run the test suite: `python tools/run_tests.py ...`
5. Start the demo: `cd demo && bash start.sh`
6. Open `http://localhost:8000/static/index.html`
7. Enter example facts (provide 3 pre-filled scenarios)
8. Show where to find the CIVIL source, the generated Rego, and the USDA FNS citations

---

## File Structure

```
input/
  policy_docs/
    snap_eligibility_fy2026.md       ← Phase 1.1
specs/
  ruleset/
    snap_eligibility.civil.yaml      ← Phase 1.2
  tests/
    snap_eligibility_tests.yaml      ← Phase 1.3
tools/
  validate_civil.py                  ← Phase 1.4
  transpile_to_opa.py                ← Phase 2.1
  run_tests.py                       ← Phase 2.3
output/
  ruleset/
    snap_eligibility.rego            ← Phase 2.1 (generated)
demo/
  main.py                            ← Phase 3.1
  requirements.txt                   ← Phase 3.2
  static/
    index.html                       ← Phase 4.1
  start.sh                           ← Phase 4.2
.claude/
  skills/
    translate-policy.md              ← Phase 5.1
docs/
  snap-demo-script.md                ← Phase 6.1
  brainstorms/
    2026-02-17-first-translation-poc-brainstorm.md
  plans/
    2026-02-17-feat-snap-eligibility-rac-poc-plan.md  ← this file
```

---

## Acceptance Criteria

### Functional Requirements
- [x] `input/policy_docs/snap_eligibility_fy2026.md` contains SNAP gross + net income rules with FY2026 thresholds and 7 CFR citations
- [x] `specs/ruleset/snap_eligibility.civil.yaml` passes `tools/validate_civil.py` with exit code 0
- [x] CIVIL module includes correct FY2026 threshold tables (sizes 1–8) and standard deduction table
- [x] CIVIL module defines `has_elderly_member` and `has_disabled_member` as optional bool facts
- [x] CIVIL module defines separate `earned_income` and `unearned_income` fact fields
- [x] All 8 test cases in `snap_eligibility_tests.yaml` pass via `tools/run_tests.py`
- [x] `output/ruleset/snap_eligibility.rego` passes `opa check` with no errors
- [x] Rego correctly implements the elderly/disabled gross income exemption
- [x] Rego correctly computes net income with shelter deduction cap ($744 for non-elderly, uncapped otherwise)
- [x] Rego handles household size 9+ correctly via formula
- [x] FastAPI `POST /api/snap/eligibility` returns correct `eligible`, `denial_reasons`, and `computed` fields
- [x] FastAPI returns HTTP 503 (not a crash) when OPA is unreachable
- [x] HTML form shows loading state during request and error message on failure
- [x] Full pipeline is re-runnable by following `docs/snap-demo-script.md` from scratch

### Quality Gates
- [x] `tools/validate_civil.py` exits 1 with a clear human-readable error on a malformed CIVIL file
- [x] `tools/transpile_to_opa.py` exits 1 with a clear error if CIVIL validation fails
- [x] OPA policy always returns a result (no undefined) for any valid input combination
- [x] `tools/run_tests.py` prints a pass/fail summary and exits 1 if any test fails

---

## Dependencies & Prerequisites

- **OPA CLI** — `brew install opa` or download from https://github.com/open-policy-agent/opa/releases
- **Python 3.11+** with `pip`
- **PyPI packages**: `fastapi`, `uvicorn[standard]`, `httpx`, `pydantic`, `pyyaml`
- **No database, no auth, no external API calls** — fully local POC

---

## Risk Analysis

| Risk | Likelihood | Mitigation |
|---|---|---|
| CIVIL expression language insufficient for net income formula | High | Express full formula in Rego; CIVIL module documents the intent in comments |
| OPA `undefined` on missing optional inputs | Medium | Use `default` rules in Rego for all optional fields; Pydantic enforces types before OPA call |
| SNAP rules more complex than expected mid-implementation | Medium | Strict out-of-scope list; add a "not supported" banner in the UI for excluded scenarios |
| schema.yaml can't be used for automated validation | Known | Custom Python validator hand-coded from schema.yaml reference |
| Shelter deduction calculation order bugs | Medium | Dedicated test case (`allow_shelter_001`) specifically tests the shelter deduction path |

---

## Future Considerations

After the POC is validated:
1. **State-level overlays** — BBCE raises gross limit to 185–200% FPL in most states; CIVIL jurisdiction layering is designed for this
2. **General-purpose transpiler** — parameterize `transpile_to_opa.py` to handle any CIVIL module, not just SNAP
3. **CIVIL v2: intermediate variables** — the net income calculation reveals the need for intermediate binding (`let net := ...`); document this as a language gap
4. **Additional output targets** — DMN, Drools, or a custom CIVIL interpreter
5. **Packaging as Claude plugin** — wrap the translation skill + transpiler as an installable Claude Code plugin

---

## References

### Internal
- CIVIL DSL specification: [specs/ruleset/README.md](specs/ruleset/README.md)
- CIVIL schema reference: [specs/ruleset/schema.yaml](specs/ruleset/schema.yaml)
- Example CIVIL module: [specs/ruleset/example_benefit.yaml](specs/ruleset/example_benefit.yaml)
- Example test suite: [specs/tests/example_benefit_tests.yaml](specs/tests/example_benefit_tests.yaml)
- Brainstorm: [docs/brainstorms/2026-02-17-first-translation-poc-brainstorm.md](docs/brainstorms/2026-02-17-first-translation-poc-brainstorm.md)

### External
- USDA FNS SNAP Eligibility: https://www.fns.usda.gov/snap/recipient/eligibility
- USDA FNS FY2026 Income Standards: https://www.fns.usda.gov/snap/allotment/cola/fy26
- Code of Federal Regulations 7 CFR § 273.9: https://www.ecfr.gov/current/title-7/subtitle-B/chapter-II/subchapter-C/part-273/section-273.9
- OPA REST API Reference: https://www.openpolicyagent.org/docs/rest-api
- OPA Integration Guide: https://www.openpolicyagent.org/docs/latest/integration/
- FastAPI Documentation: https://fastapi.tiangolo.com/
