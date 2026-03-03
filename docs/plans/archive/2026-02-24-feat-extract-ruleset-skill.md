---
title: "feat: Add extract-ruleset skill for incremental CIVIL DSL creation and updates"
type: feat
status: active
date: 2026-02-24
---

# feat: Add extract-ruleset skill for incremental CIVIL DSL creation and updates

## Overview

Add a Claude Code slash command `/extract-ruleset <domain> [<program>]` that creates or updates a domain's CIVIL DSL ruleset from documents in its `input/` subfolder. Unlike the existing `/translate-policy` skill (which walks through an interactive from-scratch translation), `extract-ruleset` is domain-aware, parameterized, and supports incremental updates when input documents have been added or modified since the previous extraction run.

## Problem Statement / Motivation

The existing `/translate-policy` skill is a guided, interactive process designed for a first-time translation. Once a domain's CIVIL file exists, re-running it from scratch is wasteful and risky — it could overwrite carefully reviewed rules. When policy documents are updated (e.g., new FY fiscal year tables, amended thresholds), practitioners need a way to:

1. Detect which input documents have changed since the last extraction
2. Identify which CIVIL sections those changes affect (tables, constants, rules, computed)
3. Apply surgical updates without disturbing unaffected sections
4. Validate, re-test, and get human sign-off before re-transpiling

The skill also serves the CREATE case for new domains where no CIVIL file exists yet, as a streamlined alternative to the full guided `/translate-policy` flow.

## Proposed Solution

Create a single skill file at `.claude/skills/extract-ruleset.md`. In Claude Code, skill files in `.claude/skills/` are automatically available as slash commands — no additional plumbing required. The skill runs two modes based on whether a CIVIL file already exists, with a pre-flight validation phase before branching.

An **extraction manifest** file (`domains/<domain>/specs/extraction-manifest.yaml`) is introduced to reliably track which input doc git SHAs produced which CIVIL file, enabling precise UPDATE mode change detection without relying solely on git log timestamps.

## Technical Considerations

### Skill File Location and Invocation

```
.claude/skills/extract-ruleset.md
```

Invoked as:
```
/extract-ruleset snap                   # domain only — auto-detects or prompts for program
/extract-ruleset snap eligibility       # domain + program — targets a specific CIVIL file
/extract-ruleset wic income_test        # new domain, new program
```

The domain name constructs paths: `domains/<domain>/input/policy_docs/`, `domains/<domain>/specs/`, `domains/<domain>/output/`. The optional `<program>` name identifies which `<program>.civil.yaml` to create or update when multiple CIVIL files exist in `core/`.

### Pre-flight Checks (always runs first)

Before mode detection, the skill validates preconditions and handles errors gracefully:

```
1. Domain argument provided?
   NO → Prompt: "Which domain? (e.g., snap, wic)" → retry

2. Does domains/<domain>/ exist?
   NO → Offer to scaffold: domains/<domain>/{input/policy_docs/,core/,output/,demo/}
        Print structure, instruct user to add policy docs, then exit.

3. Does domains/<domain>/input/policy_docs/ exist and contain files?
   NO → Print instructions; exit. ("No input docs found — add .md files to input/policy_docs/")

4. Does an OPA-compatible runtime exist? (opa binary in PATH)
   NO → Warn; proceed but skip transpile/test steps at the end.
```

### Mode Detection

```
Count *.civil.yaml files in domains/<domain>/specs/:

  0 found → CREATE mode
  1 found → UPDATE mode (targeting that file)
  2+ found AND <program> arg not given → Prompt: "Multiple CIVIL files found: [list]
             Which program to update? Or 'all' to process each." → update one or iterate
  2+ found AND <program> arg given → UPDATE mode on <program>.civil.yaml
```

### CREATE Mode Flow

1. Read all `*.md` files in `input/policy_docs/` — treat as a unified policy corpus
2. Map policy elements to CIVIL constructs (using the same table as `/translate-policy`)
3. Derive `<program>` name from: (a) `<program>` arg if given, (b) module name found in policy text, (c) prompt user
4. Draft `domains/<domain>/specs/<program>.civil.yaml`
5. Write `domains/<domain>/specs/extraction-manifest.yaml` recording git SHAs of source docs
6. Run `python tools/validate_civil.py` — on failure: auto-fix and retry up to 3 times, then halt and show errors
7. Draft `domains/<domain>/specs/tests/<program>_tests.yaml` (6+ cases: allow, deny-gross, deny-net, exemption, boundary, edge)
8. **Human review gate** (CREATE): full rule list with source policy quote + CIVIL `when:` expression for each rule. Rejection → re-extract specific rule, re-validate, re-present
9. Scaffold Makefile block for the new domain (if no target exists for it yet)
10. Transpile and test: `make <domain>-transpile && make <domain>-test`; on test failure → show failing case + actual vs. expected, ask user to diagnose

### UPDATE Mode Flow

1. Load `domains/<domain>/specs/extraction-manifest.yaml` to get baseline git SHAs
   - If manifest absent → fall back to `git log -1` on the CIVIL file for baseline SHA
   - If no git history at all → full re-extraction (equivalent to CREATE mode)
2. Check for changed input docs:
   ```bash
   git diff <baseline-sha>..HEAD -- domains/<domain>/input/policy_docs/
   git status domains/<domain>/input/policy_docs/  # catches untracked new files
   ```
3. No changes detected → report "All input docs up to date. No changes to extract." + offer force re-extract option
4. For each changed doc, analyze which CIVIL sections it affects (see Section Impact Mapping below)
5. Re-extract only the affected CIVIL sections from the changed docs
6. Merge updated sections into the existing CIVIL YAML at section granularity — preserve all unchanged sections, comments, and any hand-edits
7. Update `extraction-manifest.yaml` with new git SHAs
8. Run `python tools/validate_civil.py` — on failure: auto-fix and retry up to 3 times, then halt
9. Identify stale test cases (those whose threshold values reference changed table keys or constants)
10. **Human review gate** (UPDATE): diff-style view — removed/added/changed rules with old→new values and source quotes; stale test case list; suggested new test cases. Rejection → re-extract specific section, re-merge, re-present
11. Apply test updates (add/update stale cases)
12. Transpile and test: on failure → show failing case IDs + actual vs. expected, ask whether issue is rule, test expectation, or transpiler bug

### Section Impact Mapping

When an input doc changes, the skill performs LLM-based analysis to determine affected sections:

| Input Doc Change | Likely CIVIL Sections Affected |
|---|---|
| New/changed dollar thresholds by household size | `tables:`, possibly `computed:` (size 9+ formula) |
| New/changed fixed percentages or amounts | `constants:` |
| New applicant fields added | `facts:` (new field), possibly `rules:` |
| New eligibility test added | `rules:` (new deny rule), `computed:` (if multi-step) |
| Effective date change | `effective:` |
| Jurisdiction change | `jurisdiction:` |
| Deduction formula change | `computed:`, `constants:`, `rules:` |

### Extraction Manifest Format

```yaml
# domains/<domain>/specs/extraction-manifest.yaml
# Auto-generated by /extract-ruleset — do not edit manually

civil_file: eligibility.civil.yaml
extracted_at: "2026-02-24"
source_docs:
  - path: input/policy_docs/snap_eligibility_fy2026.md
    git_sha: "a1b2c3d4"
    last_extracted: "2026-02-24"
```

### Multiple Input Docs → One CIVIL File

All docs in `input/policy_docs/` for a domain contribute to a **single CIVIL module** (the default). This matches the SNAP pattern where one program has one policy doc and one CIVIL file. If a domain legitimately needs two separate CIVIL programs (e.g., `income_test.civil.yaml` and `asset_test.civil.yaml`), the user invokes the skill twice with different `<program>` args, each time pointing to a relevant subset of docs (noted in the manifest).

### Relationship to `/translate-policy`

| Dimension | `/translate-policy` | `/extract-ruleset` |
|---|---|---|
| Mode | Always from-scratch | CREATE or UPDATE |
| Domain param | Discovered interactively | Required argument |
| Update handling | Not supported | Core feature |
| Change detection | N/A | manifest + git diff |
| Interactivity | Guided, step-by-step | Pre-flight + review gate |
| Test generation | Full test suite (6+ cases) | Full suite (CREATE) or delta (UPDATE) |
| Validation retry | Manual | Auto-fix up to 3 attempts |
| Makefile scaffolding | No | Yes (on first CREATE) |
| Use case | Learning / exploratory | Production day-to-day |

**Decision**: `extract-ruleset` supersedes `/translate-policy` for structured domain workflows. `/translate-policy` is retained for single-file exploratory extraction outside the domain structure (e.g., quick experiments not yet committed to a domain folder).

### Validation Retry Loop

```
validate_civil.py → FAIL?
  Attempt 1: Identify error, re-extract the offending section, re-validate
  Attempt 2: Re-read the policy source for the offending section, re-extract, re-validate
  Attempt 3: Flag remaining errors, halt with message:
             "Validation failed after 3 attempts. Errors: [list]
              Please fix manually and re-run: python tools/validate_civil.py <path>"
```

## Implementation Plan

### Phase 1: Skill File (MVP)

Create `.claude/skills/extract-ruleset.md` with all sections:
- `## Input` — invocation syntax, argument parsing, domain/program discovery
- `## Pre-flight` — precondition checks and scaffolding offers
- `## Mode Detection` — 0/1/2+ CIVIL file branching
- `## Process (CREATE)` — steps 1–10 as defined above
- `## Process (UPDATE)` — steps 1–12 as defined above
- `## Section Impact Mapping` — the table + LLM analysis instructions
- `## Output` — files created/modified
- `## Common Mistakes to Avoid` — CIVIL gotchas from project MEMORY

### Phase 2: Settings Permissions

Verify `.claude/settings.local.json` includes:
```json
"Bash(git log:*)",
"Bash(git diff:*)",
"Bash(git status:*)"
```
(The validate/transpile/test commands are already allowed.)

### Phase 3: Makefile Scaffolding in Skill

The skill's CREATE mode includes instructions to append a new Makefile block for the domain if one doesn't exist. The block follows the exact pattern of the SNAP block, with domain-appropriate variable names and paths. The skill prompts for the OPA package name if it can't be derived from the CIVIL `module:` field.

## Acceptance Criteria

### Pre-flight
- [ ] `/extract-ruleset nonexistent` with no domain folder offers to scaffold `domains/nonexistent/{input/policy_docs/,core/,output/,demo/}` and exits
- [ ] `/extract-ruleset snap` with empty `input/policy_docs/` prints a clear "no docs found" message and exits without writing any files

### CREATE mode
- [ ] Given `/extract-ruleset <new-domain>` with docs in `domains/<domain>/input/policy_docs/`, produces a valid `core/<program>.civil.yaml`
- [ ] Produced CIVIL file passes `validate_civil.py` with zero errors
- [ ] Produces `extraction-manifest.yaml` recording git SHAs of source docs
- [ ] Produces at least 6 test cases in `core/tests/<program>_tests.yaml`
- [ ] Human review gate is presented with rule list + source quotes before transpilation
- [ ] Review gate rejection triggers targeted re-extraction of the disputed rule
- [ ] After confirmation, Makefile block is appended for the new domain
- [ ] After confirmation, `<program>.rego` is generated and all tests pass
- [ ] On OPA test failure, shows failing case ID + actual vs. expected output

### UPDATE mode
- [ ] Reads `extraction-manifest.yaml` to establish baseline git SHAs
- [ ] Given `/extract-ruleset snap` with no input doc changes, reports "up to date" and exits cleanly
- [ ] Given `/extract-ruleset snap` after modifying an input doc, correctly identifies the changed file
- [ ] Applies targeted updates to only the affected CIVIL sections (not the whole file)
- [ ] Review gate presents diff (old→new) for changed rules/tables/constants with source quotes
- [ ] Stale test cases are flagged by name before transpiling
- [ ] After human confirmation, re-validates (with retry), re-transpiles, and re-runs tests
- [ ] Updates `extraction-manifest.yaml` with new git SHAs after successful update

### Multi-CIVIL handling
- [ ] `/extract-ruleset snap` with 2 CIVIL files in core/ and no `<program>` arg prompts user to select one
- [ ] `/extract-ruleset snap eligibility` directly targets `eligibility.civil.yaml` without prompting

### Validation
- [ ] Validation failure triggers auto-fix up to 3 attempts before halting
- [ ] Final halt message includes the specific validation errors and manual fix instructions

## Dependencies & Risks

**Dependencies:**
- Existing tools (`validate_civil.py`, `transpile_to_opa.py`, `run_tests.py`) — no changes needed
- Git availability (already present)
- OPA binary for transpile/test steps (skill warns gracefully if absent)

**Risks:**
- **LLM accuracy in UPDATE mode merge**: Merging re-extracted sections into an existing CIVIL file without corrupting hand-edits is the highest-risk operation. Mitigated by section-granularity merging (not line-by-line diff) and the mandatory human review gate.
- **Manifest drift**: If a user edits input docs and commits without running the skill, the manifest SHAs go stale. Mitigated by the `git status` fallback that catches uncommitted changes.
- **Skills superseding translate-policy**: Users familiar with `/translate-policy` need to know to use `/extract-ruleset` for domain workflows. Mitigated by noting the relationship in both skill files.

## File Listing

### New Files
- `.claude/skills/extract-ruleset.md` — the skill/slash command
- `domains/<domain>/specs/extraction-manifest.yaml` — generated per domain on first CREATE run

### Modified Files
- `.claude/settings.local.json` — verify git commands are in allow list
- `Makefile` — a new domain block is appended by the skill on first CREATE run

### Reference Files (unchanged)
- `.claude/skills/translate-policy.md` — structural pattern to follow
- `domains/snap/specs/eligibility.civil.yaml` — CIVIL working example
- `domains/snap/specs/tests/eligibility_tests.yaml` — test format reference
- `core/ruleset_schema.yaml` — CIVIL DSL schema reference

## Success Metrics

- A practitioner can run `/extract-ruleset snap` after an annual FPL table update and get a validated, tested CIVIL update in a single session, with only the `tables:` section changed
- The skill correctly identifies changed sections for the SNAP domain (tables and/or constants) when thresholds are updated
- Zero manual edits required to the generated CIVIL YAML to pass validation
- A new domain can be scaffolded and its first CIVIL file extracted in one `/extract-ruleset` invocation

## Open Questions

These are resolved defaults — document here for implementation reference:

| Question | Default Decision |
|---|---|
| Multiple input docs → one or many CIVIL files? | One CIVIL file per `<program>` arg; all docs in `policy_docs/` contribute |
| Change detection baseline? | `extraction-manifest.yaml` git SHAs; fallback to CIVIL file's last git commit |
| Validation failure recovery? | Auto-fix up to 3 LLM attempts, then halt with instructions |
| Review gate content in UPDATE? | Diff view: old→new values with source quotes; stale test list |
| `translate-policy` relationship? | Superseded for domain workflows; retained for exploratory single-file use |
| Makefile scaffolding? | Yes — append domain block on CREATE if target missing |
| OPA not running? | Warn and skip test step; still produce CIVIL and Rego |
| No changes detected? | Report "up to date"; offer `--force` re-extract |

## References & Research

### Internal References
- Existing skill pattern: [.claude/skills/translate-policy.md](.claude/skills/translate-policy.md)
- CIVIL working example: [domains/snap/specs/eligibility.civil.yaml](domains/snap/specs/eligibility.civil.yaml)
- Test format: [domains/snap/specs/tests/eligibility_tests.yaml](domains/snap/specs/tests/eligibility_tests.yaml)
- CIVIL schema: [core/ruleset_schema.yaml](core/ruleset_schema.yaml)
- Settings/permissions: [.claude/settings.local.json](.claude/settings.local.json)

### External References (from project_status.md)
- [PolicyEngine rules-engineer agent](https://github.com/PolicyEngine/policyengine-claude/blob/main/agents/country-models/rules-engineer.md) — entity extraction patterns
- [doc-to-logic entity extraction](https://github.com/navapbc/lockpick-doc-to-logic) — NLP-based rule extraction approach
- [AutoRAC encoder prompts](https://github.com/RulesFoundation/autorac/blob/main/src/autorac/prompts/encoder.py) — structured rule encoding
- [AI-powered Rules-as-Code Experiment 3](https://digitalgovernmenthub.org/publications/ai-powered-rules-as-code-experiments-with-public-benefits-policy/#experiment-three) — effectiveness of rule templates + RAG

### Related Work
- PR #3: Multi-domain project structure refactor (foundation for this work)
- Current branch: `yl/extraction-skill`
