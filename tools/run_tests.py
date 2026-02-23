#!/usr/bin/env python3
"""
CIVIL Test Runner

Reads a CIVIL _tests.yaml file and executes each test case against the
OPA REST server, reporting pass/fail per case.

Requires OPA REST server to be running:
    opa run --server --addr :8181 output/ruleset/snap_eligibility.rego

Usage:
    python tools/run_tests.py <tests_yaml> [--opa-url URL]

Example:
    python tools/run_tests.py specs/tests/snap_eligibility_tests.yaml

Options:
    --opa-url   OPA REST server base URL (default: http://localhost:8181)

Exit codes:
    0 — all tests passed
    1 — one or more tests failed, or connection error
"""

import sys
import json
import yaml
import urllib.request
import urllib.error
import urllib.parse


DEFAULT_OPA_URL = "http://localhost:8181"
# OPA REST path: /v1/data/<package_path>/<rule>
# Package snap.eligibility → /v1/data/snap/eligibility/decision
OPA_DECISION_PATH = "/v1/data/snap/eligibility/decision"


def load_tests(path):
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"ERROR: Tests file not found: {path}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"ERROR: YAML parse error: {e}", file=sys.stderr)
        sys.exit(1)


def query_opa(opa_url, inputs):
    url = opa_url.rstrip("/") + OPA_DECISION_PATH
    payload = json.dumps({"input": inputs}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
            return body.get("result")
    except urllib.error.URLError as e:
        print(f"\nERROR: Could not connect to OPA at {opa_url}: {e}", file=sys.stderr)
        print("Is the OPA server running? Try:", file=sys.stderr)
        print("    opa run --server --addr :8181 output/ruleset/snap_eligibility.rego", file=sys.stderr)
        sys.exit(1)


def check_result(result, expected, case_id):
    """Returns list of failure messages (empty = pass)."""
    failures = []

    if result is None:
        failures.append("OPA returned undefined result (missing required input fields?)")
        return failures

    # Check eligible
    if "eligible" in expected:
        got = result.get("eligible")
        want = expected["eligible"]
        if got != want:
            failures.append(f"eligible: expected {want}, got {got}")

    # Check denial_reasons — verify expected codes are present
    if "denial_reasons" in expected:
        got_reasons = result.get("denial_reasons", [])
        got_codes = {r.get("code") for r in got_reasons}
        for expected_reason in expected["denial_reasons"]:
            code = expected_reason.get("code")
            if code and code not in got_codes:
                failures.append(f"denial_reasons: expected code {code!r}, got codes {sorted(got_codes)}")

    return failures


def run_tests(tests_path, opa_url):
    suite = load_tests(tests_path)
    test_cases = suite.get("tests", [])
    suite_desc = suite.get("test_suite", {}).get("description", tests_path)

    print(f"Running: {suite_desc}")
    print(f"OPA:     {opa_url}{OPA_DECISION_PATH}")
    print(f"Cases:   {len(test_cases)}")
    print()

    passed = 0
    failed = 0
    failures = []

    for case in test_cases:
        case_id = case.get("case_id", "?")
        description = case.get("description", "")
        inputs = case.get("inputs", {})
        expected = case.get("expected", {})

        result = query_opa(opa_url, inputs)
        case_failures = check_result(result, expected, case_id)

        if case_failures:
            failed += 1
            failures.append((case_id, description, case_failures, result))
            print(f"  FAIL  {case_id}: {description}")
            for msg in case_failures:
                print(f"        ↳ {msg}")
        else:
            passed += 1
            eligible = result.get("eligible") if result else "?"
            computed = result.get("computed", {}) if result else {}
            net = computed.get("net_income", "?")
            print(f"  PASS  {case_id}: {description}")
            print(f"        eligible={eligible}, net_income=${net:,.2f}" if isinstance(net, (int, float)) else f"        eligible={eligible}")

    print()
    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} total")

    if failures:
        print()
        print("FAILED CASES — full OPA output:")
        for case_id, desc, msgs, result in failures:
            print(f"\n  {case_id}: {desc}")
            print(f"  OPA result: {json.dumps(result, indent=4)}")

    return failed == 0


def main():
    args = sys.argv[1:]
    tests_path = None
    opa_url = DEFAULT_OPA_URL

    i = 0
    while i < len(args):
        if args[i] == "--opa-url" and i + 1 < len(args):
            opa_url = args[i + 1]
            i += 2
        else:
            tests_path = args[i]
            i += 1

    if not tests_path:
        print(f"Usage: {sys.argv[0]} <tests_yaml> [--opa-url URL]", file=sys.stderr)
        sys.exit(1)

    success = run_tests(tests_path, opa_url)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
