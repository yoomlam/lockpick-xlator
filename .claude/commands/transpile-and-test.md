# Transpile and Test

Transpile a CIVIL module to Rego and run the test suite.

## Input

```
/transpile-and-test [<domain>]                 # auto-detect program or prompt if ambiguous
/transpile-and-test [<domain> <program>]       # target a specific program
```

If `<domain>` is not provided, list all `domains/*/specs/*.civil.yaml` files and prompt the user to choose.

## Pre-flight

1. **Domain folder exists?** — NO → Print: "Domain `<domain>` not found." Stop.

2. **Makefile target exists?**
   ```bash
   grep -n "<domain>-transpile" Makefile
   ```
   - Found → continue.
   - Missing → scaffold by appending a new block to `Makefile` and continue:

     ```makefile
     # ---------------------------------------------------------------------------
     # <DOMAIN_UPPER> — <description from CIVIL module, or domain name if not yet written>
     # ---------------------------------------------------------------------------

     <DOMAIN>_CIVIL    := domains/<domain>/specs/<program>.civil.yaml
     <DOMAIN>_TESTS    := domains/<domain>/specs/tests/<program>_tests.yaml
     <DOMAIN>_REGO     := domains/<domain>/output/<program>.rego
     <DOMAIN>_PACKAGE  := <domain>.<program>
     <DOMAIN>_OPA_PATH := /v1/data/<domain>/<program>/decision

     <domain>: <domain>-validate <domain>-transpile <domain>-test

     <domain>-validate:
     	python tools/validate_civil.py $(<DOMAIN>_CIVIL)

     <domain>-transpile: <domain>-validate
     	python tools/transpile_to_opa.py $(<DOMAIN>_CIVIL) $(<DOMAIN>_REGO) --package $(<DOMAIN>_PACKAGE)

     <domain>-test:
     	python tools/run_tests.py $(<DOMAIN>_TESTS) --opa-path $(<DOMAIN>_OPA_PATH)

     <domain>-demo:
     	bash domains/<domain>/demo/start.sh
     ```

     Also add `.PHONY: <domain> <domain>-validate <domain>-transpile <domain>-test <domain>-demo` to the `.PHONY` line at the top of the Makefile.

     For `<DOMAIN>_PACKAGE`: if `domains/<domain>/specs/<program>.civil.yaml` exists, derive from its `module:` field (e.g., `"eligibility.snap_federal"` → `snap.eligibility`). Otherwise use `<domain>.<program>` as a placeholder.

3. **OPA available?**
   ```bash
   which opa
   ```
   - NOT in PATH → Warn: "OPA not found. Transpilation will run but tests will be skipped. Install OPA to run the full test suite." Proceed with transpile-only path (see below).

## Execution — OPA Present

```bash
make <domain>-transpile && make <domain>-test
```

Relay make output verbatim. No summary formatting.

**On test failure:** Show the failing case ID(s) and actual vs. expected output. Ask the user to diagnose:

- **Rule error** — the CIVIL `when:` expression is wrong → fix in the CIVIL file and re-run `/extract-ruleset <domain>`
- **Test expectation error** — the test case has wrong expected values → fix in the tests file and re-run `/transpile-and-test <domain>`
- **Transpiler bug** — the Rego generation is incorrect → file a transpiler issue; do not modify CIVIL or tests

## Execution — OPA Absent (Fallback)

Run transpilation only:

```bash
python tools/transpile_to_opa.py \
    domains/<domain>/specs/<program>.civil.yaml \
    domains/<domain>/output/<program>.rego \
    --package <domain>.<program>
```

Print: "Transpilation complete. Tests skipped — OPA not in PATH. Install OPA to run the full suite."
