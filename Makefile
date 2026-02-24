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

.PHONY: snap snap-setup snap-validate snap-transpile snap-test snap-demo

baseline-setup:
	# Install UV (Python tool) if it doesn't exist
	command -v uv || brew install uv
	test -d .venv || uv venv

	# Install OPA CLI if it doesn't exist
	# Used for testing and demo; Claude may also run it for its testing
	# OPA is a rules engine that can run Rego policies
	# Use OPA for now, but we'll support other ruleset languages and rule engines
	command -v opa || brew install opa

# ---------------------------------------------------------------------------
# SNAP — Federal income eligibility
# ---------------------------------------------------------------------------

SNAP_CIVIL    := domains/snap/specs/eligibility.civil.yaml
SNAP_TESTS    := domains/snap/specs/tests/eligibility_tests.yaml
SNAP_REGO     := domains/snap/output/eligibility.rego
SNAP_PACKAGE  := snap.eligibility
SNAP_OPA_PATH := /v1/data/snap/eligibility/decision

snap-setup: baseline-setup
	# Install Python dependencies
	uv pip install -r domains/snap/demo/requirements.txt

snap: snap-validate snap-transpile snap-test

snap-validate:
	python tools/validate_civil.py $(SNAP_CIVIL)

snap-transpile: snap-validate
	python tools/transpile_to_opa.py $(SNAP_CIVIL) $(SNAP_REGO) --package $(SNAP_PACKAGE)

snap-test:
	python tools/run_tests.py $(SNAP_TESTS) --opa-path $(SNAP_OPA_PATH)

snap-demo:
	bash domains/snap/demo/start.sh
