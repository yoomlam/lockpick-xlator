# Legacy Lockpicks: Xlator (Translator) project

Goal: Represent and translate the given input (federal, state, and local government policy documents and code from legacy systems) into specs (intermediate representations of rulesets), following a Rules-as-Code (RaC) approach. To create the output, the specs are used to build the modernized system, quickly building much of the UI workflows to gather the input needed to run the ruleset.

## Key Principles

* Incremental Approach: Work on one program or rule set topic at a time, building confidence before expanding scope.
* Version Control: Commit specs after each logical milestone to track evolution and enable rollback.
* AI Collaboration: Use AI to accelerate translation, but human review ensures accuracy and policy compliance.
* Testing Focus: Comprehensive tests prevent regressions and document expected behavior.

## Step-by-Step Process

This project takes an incremental approach where each iteration involves the user (an SME on the policies) to perform the following:
- The user adds `input` docs and code in manageable-sized amounts of policy docs
    - The codebase contains the input and there is no context window (and hence no limit).
    - The AI searches the codebase for the data it needs (similar to RAG but without a vector DB).
- The user interacts with an AI to update the `specs`. Once satisfied, the specs are commited into git for version control.
    - The user interacts with the AI to create/update the specs (ruleset, workflows, etc.) in manageable amounts.
    - The specs are in a DSL format that will evolve over time.
    - The specs are machine-readable so that it can be used to build the UI workflows.
- Tests for updated specs are added by an AI and verified by the user to ensure future changes do not cause a regression.
- Once a logical set of rules are captured, the user guides the AI to generate `output`, including the ruleset and code to get end-user input and run the ruleset on a given rules engine.
    - A transpiler or converter may be needed to create the output ruleset so that it is usable by the modern system.

Each policy domain is a self-contained unit under `domains/<name>/`:

```
domains/
  snap/                              ← example: SNAP federal income eligibility
    input/policy_docs/               ← source policy documents (Markdown, PDF, etc.)
    specs/
      eligibility.civil.yaml         ← CIVIL DSL ruleset (human + AI authored)
      tests/eligibility_tests.yaml   ← test cases
    output/
      eligibility.rego               ← generated OPA/Rego (do not edit manually)
    demo/
      main.py                        ← FastAPI backend
      static/index.html              ← browser form UI
      start.sh                       ← starts OPA + FastAPI
  <next-domain>/                     ← add new domains here
    input/ specs/ output/ demo/

specs/
  ruleset_schema.yaml                ← shared CIVIL DSL schema reference
tools/
  validate_civil.py                  ← CIVIL validator
  transpile_to_opa.py                ← CIVIL → OPA/Rego transpiler
  run_tests.py                       ← test runner
Makefile                             ← per-domain pipeline targets
```

### 1. Input Collection
- Add policy documents to `domains/<name>/input/policy_docs/`
- Use the `translate-policy` skill (`.claude/skills/translate-policy.md`) to extract CIVIL specs with AI assistance

### 2. Spec Creation (AI-Assisted)
- Work with AI to create `domains/<name>/specs/<module>.civil.yaml`
- Follow the CIVIL DSL schema at `specs/ruleset_schema.yaml`
- Commit completed specs to version control

### 3. Test Definition (AI-Assisted)
- AI generates `domains/<name>/specs/tests/<module>_tests.yaml`
- Review and verify test scenarios; add edge cases and boundary conditions

### 4. Output Generation
- `make <domain>-transpile` generates `domains/<name>/output/<module>.rego`

### 5. Validation & Iteration
- `make <domain>-test` runs tests against a live OPA server
- `make <domain>-demo` starts the demo (OPA + FastAPI)
- Iterate on specs as needed

### Example (SNAP)

```bash
make snap             # validate + transpile + test
make snap-demo        # start OPA + FastAPI demo at http://localhost:8000
```

## Vision diagram

```mermaid
flowchart TD

subgraph input
    policy_docs@{shape: docs} --> legacy_code
    legacy_code@{shape: procs}
    verified_artifacts
end

policy_docs --> Extractor1[[Extractor1]] --> ruleset
legacy_code --> Extractor2[[Extractor2]] --> specs

subgraph specs
    ruleset & workflows & artifacts
end

specs <--correct?--> verify[/verify/]

subgraph specs_testing
    tester_rule_engine[[Rule Engine]]
    ruleset --transpile?--> tester_rule_engine
    test_cases([test_cases]) --> tester_rule_engine --> expected_results([expected_results])
    tester_rule_engine --> explanation([explanation])
end

ruleset ---> Transpiler[[Transpiler]] --> ruleset2[ruleset]
workflows & artifacts ---> Coder[[Coder]] --> webforms

subgraph output["output (modern_system)"]
    ruleset2 --> rule_engine[[Rule Engine]] <--> code <--> webforms
end
```

- One incarnation of `Extractor1` is the [Policy Extraction (doc-to-logic) prototype](https://github.com/navapbc/lockpick-doc-to-logic)
- `Extractor2` will likely use AWS Transform, which also produces documentation, which would be included as part of the specs and can be used as input to the Coder.
    - Another option is to include verified output from AWS Transform (noted as `verified_artifacts`) as part of the `input`.

Not yet in the diagram:
- There can be multiple specs that can be compared to identify differences between systems (legacy vs legacy; modern vs modern; legacy vs modern).
- Validating the `modern_system` against the `legacy_system`
