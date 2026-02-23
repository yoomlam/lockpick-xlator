---
title: "refactor: Multi-domain project structure"
type: refactor
status: active
date: 2026-02-23
brainstorm: docs/brainstorms/2026-02-23-multi-domain-structure-brainstorm.md
---

# refactor: Multi-domain project structure

## Overview

Reorganize xlator from a flat, SNAP-specific layout to a **domain-first** structure where each policy program lives under `domains/<name>/` with its own `input/`, `specs/`, `output/`, and `demo/`. Shared tooling (`tools/`, `specs/schema.yaml`) remains at the project root. A top-level `Makefile` provides per-domain pipeline targets.

## Problem Statement

The current layout is flat and tightly coupled to SNAP:

- All pipeline stages (`input/`, `specs/`, `output/`, `demo/`) live at the project root as if there will only ever be one domain
- `tools/transpile_to_opa.py` has a `transpile_snap()` function that hardcodes the OPA package name, table/constant names, and decision object shape
- `tools/run_tests.py` has a hardcoded module-level `OPA_DECISION_PATH` constant
- `demo/main.py` and `demo/start.sh` are entirely SNAP-specific
- Adding a second domain requires code changes in three different tools and creating a parallel directory structure by hand

## Proposed Solution

Five sequential phases:

1. **Directory restructure** — move all SNAP files into `domains/snap/`; elevate shared schema; delete example files
2. **Generalize transpiler** — replace `transpile_snap()` with a generic `transpile()` driven by the CIVIL YAML's own `decisions:`, `constants:`, `tables:` sections; add `--package` CLI flag
3. **Generalize test runner** — add `--opa-path` CLI flag to `run_tests.py`
4. **Parameterize demo** — each domain's `start.sh` manages its own OPA instance; no shared demo logic
5. **Add Makefile** — top-level `Makefile` with per-domain pipeline targets

After these phases, adding a new domain = create `domains/<name>/`, populate `specs/`, and add Makefile targets. No tool code changes required.

## Technical Considerations

### Transpiler generalization (biggest change)

`transpile_to_opa.py`'s `transpile_snap()` function currently hardcodes four things:

| Hardcoded item | Current value | Generic source |
|---|---|---|
| OPA package name | `snap.eligibility` | New `--package` CLI flag |
| Table names | `gross_income_limits`, etc. | CIVIL `tables:` section (already keyed) |
| Constants | `SHELTER_DEDUCTION_CAP`, etc. | CIVIL `constants:` section (already keyed) |
| Decision object shape | SNAP-specific fields | CIVIL `decisions:` section (already keyed) |

The generic parts (`emit_computed_section()`, `translate_expr()`) already exist and work correctly. The new generic `transpile()` function will read `decisions:`, `constants:`, and `tables:` from the parsed CIVIL YAML — the same pattern `emit_computed_section()` already uses.

### OPA package name convention

The OPA package name (`snap.eligibility`) does NOT auto-derive from the CIVIL module id (`eligibility.snap_federal`) — they use different conventions. The `--package` flag makes this explicit. The Makefile is the single source of truth for each domain's package name.

### `validate_before_transpile()` survives relocation

`transpile_to_opa.py` locates `validate_civil.py` via `os.path.dirname(__file__)`. As long as both files stay in `tools/`, no change needed.

### Per-domain OPA instances

Each domain's `demo/start.sh` starts its own OPA process on its own port. The OPA health-check and cleanup pattern from the current `demo/start.sh` is a reusable template — each domain's `start.sh` fills in `REGO_FILE` and `OPA_PORT`.

### Schema location change

`specs/ruleset/schema.yaml` moves to `specs/schema.yaml`. The `.claude/skills/translate-policy.md` skill file references paths and will need updating.

---

## Acceptance Criteria

- [ ] `domains/snap/` exists with `input/policy_docs/`, `specs/`, `output/`, `demo/` subdirectories
- [ ] All existing SNAP files are in their new locations (moved via `git mv` to preserve history)
- [ ] `specs/schema.yaml` is the shared CIVIL schema (moved from `specs/ruleset/schema.yaml`)
- [ ] `specs/ruleset/example_benefit.yaml` and `specs/tests/example_benefit_tests.yaml` are deleted
- [ ] `tools/transpile_to_opa.py` accepts `--package <name>` and generates correct Rego without SNAP-specific hardcoding in the generic path
- [ ] `tools/run_tests.py` accepts `--opa-path <path>` instead of using a hardcoded constant
- [ ] `domains/snap/demo/start.sh` starts OPA pointing at `domains/snap/output/eligibility.rego` and brings up the FastAPI demo
- [ ] `Makefile` at project root has targets: `snap`, `snap-validate`, `snap-transpile`, `snap-test`, `snap-demo`
- [ ] `make snap-transpile` regenerates `domains/snap/output/eligibility.rego` correctly
- [ ] `make snap-test` runs tests against a live OPA instance and passes
- [ ] `make snap-demo` starts the SNAP demo (OPA + FastAPI) successfully
- [ ] `README.md` and `.claude/skills/translate-policy.md` updated to reflect new paths
- [ ] Old top-level `input/`, `specs/ruleset/`, `output/`, `demo/` directories removed (or empty and gitignored)

---

## Implementation Phases

### Phase 1: Directory restructure

**Goal:** Move all SNAP artifacts into `domains/snap/`. No code changes.

Files to move (use `git mv` throughout):

```
input/policy_docs/snap_eligibility_fy2026.md
  → domains/snap/input/policy_docs/snap_eligibility_fy2026.md

specs/ruleset/snap_eligibility.civil.yaml
  → domains/snap/specs/eligibility.civil.yaml

specs/tests/snap_eligibility_tests.yaml
  → domains/snap/specs/tests/eligibility_tests.yaml

output/ruleset/snap_eligibility.rego
  → domains/snap/output/eligibility.rego

demo/main.py, demo/static/, demo/requirements.txt, demo/start.sh
  → domains/snap/demo/

specs/ruleset/schema.yaml
  → specs/schema.yaml
```

Files to delete:
```
specs/ruleset/example_benefit.yaml
specs/tests/example_benefit_tests.yaml
```

Directories to clean up (remove if empty after moves):
```
input/policy_docs/   (keep input/ with updated README)
output/ruleset/
specs/ruleset/
specs/tests/
demo/
```

---

### Phase 2: Generalize transpiler

**Goal:** Replace `transpile_snap()` with a generic `transpile()` that derives all domain-specific values from the CIVIL YAML itself, plus a `--package` CLI argument.

**Changes to `tools/transpile_to_opa.py`:**

```python
# main() — add --package argument
parser.add_argument("--package", required=True,
    help="OPA package name, e.g. snap.eligibility")

# Replace transpile_snap(civil, output_path) call with:
transpile(civil, output_path, package=args.package)
```

The generic `transpile()` function:
- Emits `package <package_arg>` from the `--package` flag
- Emits `import rego.v1`
- Reads `constants:` from CIVIL YAML → emits one `const_<name> := <value>` rule per constant
- Reads `tables:` from CIVIL YAML → emits table lookup rules generically
- Calls existing `emit_computed_section()` (already generic, no change)
- Reads `decisions:` from CIVIL YAML → emits `decision := { key: value, ... }` collecting all decision fields
- Reads `rules:` from CIVIL YAML → calls existing rule emission (already generic)
- Emits `default` rules for all boolean outputs

The SNAP-specific `standard_deduction` size-7+ fallback can be handled via a `conditional:` entry in `computed:` in the CIVIL YAML rather than in the transpiler.

---

### Phase 3: Generalize test runner

**Goal:** Make `OPA_DECISION_PATH` a CLI argument instead of a hardcoded constant.

**Changes to `tools/run_tests.py`:**

```python
# Replace module-level constant:
#   OPA_DECISION_PATH = "/v1/data/snap/eligibility/decision"
# With CLI argument:
parser.add_argument("--opa-path",
    default="/v1/data/snap/eligibility/decision",
    help="OPA REST query path, e.g. /v1/data/snap/eligibility/decision")
```

Remove the hardcoded `net_income` display in the pass output (or make it generic by showing all computed fields from the test result).

---

### Phase 4: Parameterize demo

**Goal:** `domains/snap/demo/start.sh` manages its own OPA instance pointing at the correct domain's Rego file.

**Changes to `domains/snap/demo/start.sh`:**

The current `start.sh` resolves `REPO_ROOT` from `SCRIPT_DIR` — this survives the relocation since the relative path from `demo/` to root changes from `../..` to `../../..`.

Update:
```bash
# Old:
REGO_FILE="$REPO_ROOT/output/ruleset/snap_eligibility.rego"
# New:
REGO_FILE="$REPO_ROOT/domains/snap/output/eligibility.rego"
```

No changes needed to `demo/main.py` itself in this phase — the SNAP demo stays SNAP-specific. Future domains each get their own `main.py`.

---

### Phase 5: Add Makefile

**Goal:** Top-level `Makefile` provides one-command pipeline execution per domain.

```makefile
# Makefile
.PHONY: snap snap-validate snap-transpile snap-test snap-demo

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
```

Adding a new domain = add a new block of five variables and five targets.

---

### Phase 6: Update docs

**Goal:** Ensure docs and skills reflect new paths.

Files to update:
- `README.md` — update pipeline diagram, example commands, file paths
- `.claude/skills/translate-policy.md` — update the 7-step workflow's file path references (CIVIL YAML location, output Rego location)
- `docs/brainstorms/` and `docs/plans/` — add note pointing to this plan from the brainstorm (already linked via frontmatter)

---

## Dependencies & Risks

| Risk | Mitigation |
|---|---|
| `transpile_snap()` generalization misses SNAP-specific edge cases | Verify `make snap-test` passes before merging; keep the SNAP test suite as regression guard |
| `git mv` not used → git loses file history | Strictly use `git mv` (or `git add -A` after shell `mv` with rename detection) for all file moves |
| SNAP standard_deduction size-7+ fallback currently in transpiler | Move to CIVIL YAML `computed:` conditional before removing transpiler hardcode |
| Old paths referenced elsewhere (e.g. shell scripts, README commands) | Phase 6 update pass; search for `output/ruleset`, `specs/ruleset`, `demo/` in all text files |

---

## References

### Internal

- Brainstorm: [docs/brainstorms/2026-02-23-multi-domain-structure-brainstorm.md](../brainstorms/2026-02-23-multi-domain-structure-brainstorm.md)
- Transpiler: [tools/transpile_to_opa.py](../../tools/transpile_to_opa.py)
- Test runner: [tools/run_tests.py](../../tools/run_tests.py)
- Current demo: [demo/start.sh](../../demo/start.sh), [demo/main.py](../../demo/main.py)
- CIVIL schema: [specs/ruleset/schema.yaml](../../specs/ruleset/schema.yaml)
- Skill: [.claude/skills/translate-policy.md](../../.claude/skills/translate-policy.md)
