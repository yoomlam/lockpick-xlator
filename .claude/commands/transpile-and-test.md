# Transpile and Test

Transpile a CIVIL module to Rego and run the test suite.

## Input

```
/transpile-and-test [<domain>]                 # auto-detect program or prompt if ambiguous
/transpile-and-test [<domain> <program>]       # target a specific program
```

If `<domain>` is not provided, run `./x list` and prompt the user to choose.

## Pre-flight

1. **Domain folder exists?** — NO → Print: "Domain `<domain>` not found." Stop.

2. **CIVIL file exists?**
   `domains/<domain>/specs/<program>.civil.yaml`
   - Found → continue.
   - Missing → Print: "CIVIL spec not found: `domains/<domain>/specs/<program>.civil.yaml`". Stop.

3. **OPA available?**
   ```bash
   which opa
   ```
   - NOT in PATH → Warn: "OPA not found. Transpilation will run but tests will be skipped. Install OPA to run the full test suite (`./x setup`)." Proceed with transpile-only path (see below).

## Execution — OPA Present

```bash
./x pipeline <domain> <program>
```

Relay output verbatim. No summary formatting.

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

Print: "Transpilation complete. Tests skipped — OPA not in PATH. Run `./x setup` to install OPA."
