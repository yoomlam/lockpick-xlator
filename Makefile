# Xlator Pipeline — per-domain targets
#
# Usage:
#   make snap              — validate + transpile + test
#   make snap-validate     — validate CIVIL YAML
#   make snap-transpile    — generate Rego from CIVIL YAML
#   make snap-test         — run tests against a live OPA server (OPA must be running)
#   make snap-demo         — start OPA + FastAPI demo
#
# Adding a new domain:
#   1. Create domains/<name>/ with input/, specs/, output/, demo/
#   2. Copy this block, replacing SNAP_ prefix and snap- prefixes with your domain name
#   3. Set DOMAIN_CIVIL, DOMAIN_TESTS, DOMAIN_REGO, DOMAIN_PACKAGE, DOMAIN_OPA_PATH

.PHONY: snap snap-validate snap-transpile snap-test snap-demo

# ---------------------------------------------------------------------------
# SNAP — Federal income eligibility
# ---------------------------------------------------------------------------

SNAP_CIVIL    := domains/snap/specs/eligibility.civil.yaml
SNAP_TESTS    := domains/snap/specs/tests/eligibility_tests.yaml
SNAP_REGO     := domains/snap/output/eligibility.rego
SNAP_PACKAGE  := snap.eligibility
SNAP_OPA_PATH := /v1/data/snap/eligibility/decision

snap: snap-validate snap-transpile snap-test

snap-validate:
	python tools/validate_civil.py $(SNAP_CIVIL)

snap-transpile: snap-validate
	python tools/transpile_to_opa.py $(SNAP_CIVIL) $(SNAP_REGO) --package $(SNAP_PACKAGE)

snap-test:
	python tools/run_tests.py $(SNAP_TESTS) --opa-path $(SNAP_OPA_PATH)

snap-demo:
	bash domains/snap/demo/start.sh
