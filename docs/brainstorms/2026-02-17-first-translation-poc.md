# Brainstorm: First Real Translation POC

**Date:** 2026-02-17
**Status:** Draft
**Author:** Collaborative brainstorm

---

## What We're Building

An internal proof-of-concept that demonstrates the full Xlator pipeline end-to-end:

```
Real policy doc (SNAP eligibility rules)
    → Claude-assisted translation
    → CIVIL module + test cases
    → OPA/Rego transpilation
    → OPA evaluates facts → decisions + reasons
```

This proves the value proposition: that AI-assisted translation from raw government policy to machine-executable rules actually works, with real input material and real output.

---

## Why This Approach

**Why SNAP?** SNAP eligibility rules (USDA/FNS) are publicly available, well-documented, and widely used as a reference case in the Rules-as-Code community. They have enough complexity (income thresholds, household size, categorical eligibility, gross/net tests) to be meaningful without being overwhelming.

**Why OPA?** OPA (Open Policy Agent) is production-proven, has a simple JSON/YAML fact format, and is one of the explicitly named compilation targets in the CIVIL spec. It's the best-supported path to a running evaluator without building a custom interpreter.

**Why end-to-end?** A CIVIL module alone doesn't demonstrate the full value. The POC needs to show that the output actually runs and produces correct decisions — otherwise it's just a YAML file.

---

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Policy domain | SNAP eligibility (federal) | Public domain, rich but approachable |
| Input source | USDA FNS public documentation | Freely available, citable |
| SNAP rule scope | Gross income + net income tests | Meaningful complexity; includes deductions |
| CIVIL translation | Claude Code skill (reusable) | Makes pipeline repeatable for any policy doc |
| Output target | OPA/Rego | Named in spec, well-supported |
| Demo surface | Web form + FastAPI backend + OPA | Browser posts facts → FastAPI calls OPA → returns decision + reasons |

---

## Proposed Steps

1. **Source input material** — Download/copy SNAP eligibility rules from USDA FNS into `input/policy_docs/`
2. **Translate to CIVIL** — Use Claude to generate a CIVIL module (`core/ruleset/snap_eligibility.civil.yaml`) following `schema.yaml`
3. **Write test cases** — Use Claude to generate test scenarios (`core/tests/snap_eligibility_tests.yaml`) covering allow/deny cases
4. **Validate structure** — Confirm the CIVIL module validates against `core/ruleset/schema.yaml`
5. **Transpile to OPA** — Build a Python script that converts CIVIL YAML → OPA/Rego policy file
6. **Run OPA evaluation** — Set up OPA CLI, feed in fact bundles, confirm decisions match test expectations
7. **Build web view** — FastAPI backend wraps OPA evaluation; simple HTML form posts facts and displays decision + reasons
8. **Document the demo** — Capture the input → output trace as a demo script in `docs/`

---

## Open Questions

1. **Transpiler language:** Python is the default assumption for the CIVIL → OPA transpiler script. Is that correct?
2. **Validation of translation quality:** How do we verify the CIVIL module correctly captures the policy intent, not just structure? Working assumption: "matches USDA source text" + passing test cases is sufficient for POC.

---

## Out of Scope (for this POC)

- Asset limits and categorical eligibility (SNAP rules beyond income tests)
- State-level SNAP overlays (jurisdiction layering)
- Multiple rule engine targets (Drools, DMN)
- A general-purpose transpiler (OPA only, hardcoded for now)
- Packaging as a Claude plugin

---

## Success Criteria

- [ ] Real SNAP policy text lives in `input/policy_docs/`
- [ ] CIVIL module validates against schema with no errors
- [ ] Test cases cover at least 6 scenarios (gross income fail, net income fail, deduction edge cases, allow)
- [ ] OPA evaluates facts and returns correct `allow`/`deny` + reasons
- [ ] FastAPI backend + HTML form shows facts in → decision + reasons (calls OPA internally)
- [ ] A Claude Code skill exists that can repeat the translation for a new policy doc
- [ ] Full pipeline can be re-run by following documented steps
