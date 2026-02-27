---
title: feat: Allow specifying input file for extract-ruleset
type: feat
status: completed
date: 2026-02-26
---

# feat: Allow Specifying Input File for `extract-ruleset`

## Overview

Add a third positional argument `[<filename>]` to `/extract-ruleset` so users can scope extraction to a specific policy document instead of the entire `input/policy_docs/` directory.

**Trigger:** The `ak_doh` domain's single policy file (`AK_DOH_APA_ADLTC.md`) was split into two files (`APA.md`, `ADLTC.md`). The command currently reads all `.md` files as a unified corpus with no way to target one file. The extraction manifest still points at the deleted combined file, creating a broken state.

## Problem Statement

Two interrelated problems:

1. **No per-file scoping**: `/extract-ruleset ak_doh apa_adltc` always processes every `.md` file in `input/policy_docs/`. When only one file changes, there's no way to scope extraction to that file.

2. **Manifest reconciliation gap**: When input files are renamed or split, the manifest retains stale entries for deleted files. On the next UPDATE run, change detection against deleted files fails silently. A reconciliation step is needed regardless of whether `<filename>` is specified.

## Proposed Solution

**New invocation signature:**

```
/extract-ruleset <domain>                          # unchanged
/extract-ruleset <domain> <program>                # unchanged
/extract-ruleset <domain> <program> <filename>     # NEW: scope to one file
```

**`<filename>` semantics:**
- Basename only (e.g., `APA.md`), not a relative path — command prepends `domains/<domain>/input/policy_docs/`
- Must include `.md` extension
- Scopes **the full pipeline**: both change detection AND the extraction corpus
- In CREATE mode: only `<filename>` is read as the policy corpus for CIVIL derivation
- In UPDATE mode: only `<filename>` is checked for changes; only its manifest entry is updated

**Interactive selection when `<filename>` is omitted and multiple `.md` files exist:**

```
Multiple policy documents found in domains/ak_doh/input/policy_docs/:
  1. APA.md
  2. ADLTC.md
  a. All files (unified corpus)

Process which file? [1/2/a]:
```

Selecting `a` runs the existing full-corpus flow unchanged. Selecting a number runs the scoped flow.

## Key Design Decision: Full-Pipeline vs. Change-Detection-Only Scoping

Two scoping models were considered:

| Model | What `<filename>` controls |
|---|---|
| A. Full-pipeline | Change detection + extraction corpus (reads ONLY the named file) |
| B. Change-detection-only | Only the git diff/status check; extraction still reads all files |

**Recommendation: Model A (full-pipeline scoping).**

Rationale: Model B would produce the same CIVIL output regardless of which file you specify — the only effect would be suppressing "no changes detected" for other files. This is confusing and not what a user intends when they say "process `APA.md`." Model A is honest: processing `APA.md` means the CIVIL extraction is derived from `APA.md` only.

**Consequence:** With Model A, the CIVIL output for a given run is derived solely from the named file. For domains where multiple files contribute to one CIVIL program (e.g., `APA.md` + `ADLTC.md` → `apa_adltc.civil.yaml`), the user should run *without* `<filename>` — all files are then read as a unified corpus, which is the correct multi-source behavior. Running with `<filename>` in this case produces a CIVIL file derived from that one file only (intentional partial extraction, e.g., for early exploration). The completion message makes the partial scope explicit:

```
Extraction complete. Processed: APA.md

Note: this domain has other policy docs not included in this run:
  - ADLTC.md (untracked)

To extract from all files as a unified corpus, run without specifying a filename.
```

## Technical Considerations

### 1. Manifest Reconciliation (Prerequisite — independent of `<filename>`)

Before any change detection in UPDATE mode, reconcile the manifest:

```
For each entry in manifest source_docs:
  If the file no longer exists on disk → remove the entry, log "Removed stale entry: <path>"
```

This must run before Step 2 (change detection) on every UPDATE run. It's what allows the `ak_doh` domain to recover from having `AK_DOH_APA_ADLTC.md` deleted.

### 2. Pre-flight: `<filename>` Existence Check

Add to the Pre-flight section:

```
If <filename> is given:
  - If <filename> has no .md extension, append it automatically
  - Verify domains/<domain>/input/policy_docs/<filename> exists on disk
  - If not: print error + list available .md files, then stop
```

### 3. Manifest Partial Update

When `<filename>` is given and other manifest entries exist:

```
Files processed this run          → update git_sha and last_extracted
On-disk files NOT processed       → preserve existing entry as-is
Files no longer on disk           → already removed by reconciliation step
```

The net effect: the manifest always reflects the exact set of files that currently exist on disk, with SHAs updated only for what was processed.

## Acceptance Criteria

### Core Behavior
- [ ] `/extract-ruleset ak_doh apa_adltc APA.md` — reads only `APA.md`, extracts CIVIL from it
- [ ] `/extract-ruleset ak_doh apa_adltc BADNAME.md` — prints "File not found" error and lists available files, then stops
- [ ] Running without `<filename>` when multiple `.md` files exist → interactive prompt appears
- [ ] Selecting `a` (all) from the prompt runs the existing full-corpus flow unchanged
- [ ] Completion message lists unprocessed sibling files when `<filename>` was used

### Manifest Correctness
- [ ] After running with `APA.md`: manifest has entry for `APA.md` with correct git SHA
- [ ] After running with `APA.md`: manifest has NO entry for deleted `AK_DOH_APA_ADLTC.md`
- [ ] After running with `APA.md`: `ADLTC.md` has no manifest entry (never processed)
- [ ] Stale manifest entries for deleted files are removed on every UPDATE run (even without `<filename>`)

### Regression (Existing Flows Unchanged)
- [ ] Single-file domains: no prompt appears; existing flow unchanged
- [ ] `/extract-ruleset snap` — behaves identically to before
- [ ] `/extract-ruleset snap eligibility` — behaves identically to before

## Files to Modify

| File | Change |
|---|---|
| `.claude/commands/extract-ruleset.md` | Extend Input section with third arg; add pre-flight `<filename>` check; add manifest reconciliation step before UPDATE Step 2; branch CREATE Step 1 on `<filename>`; branch UPDATE Steps 2, 7, and 9 on `<filename>`; update completion message |

No other files need modification. The manifest schema already supports a `source_docs:` list; no schema change is needed.

## Open Questions (Deferred)

1. **Naming manifest + scoped corpus**: When `<filename>` limits the corpus, the naming manifest only derives field names from that file (consistent with full-pipeline model). Cross-file field name conflicts deferred to a future iteration.

2. **Glob support**: Allow `<filename>` to be a glob (e.g., `AK_*`)? Deferred.

3. **`--force` interaction**: Does `--force` work with `<filename>`? Yes — force re-extraction even if `<filename>` reports no changes in git.

## References

- Command definition: [`.claude/commands/extract-ruleset.md`](.claude/commands/extract-ruleset.md)
- Broken manifest (motivating case): [`domains/ak_doh/specs/.extraction-manifest.yaml`](domains/ak_doh/specs/.extraction-manifest.yaml)
- New split policy docs: [`domains/ak_doh/input/policy_docs/APA.md`](domains/ak_doh/input/policy_docs/APA.md), [`domains/ak_doh/input/policy_docs/ADLTC.md`](domains/ak_doh/input/policy_docs/ADLTC.md)
- Decomposition plan (established argument patterns): [`docs/plans/2026-02-25.e-refactor-extract-ruleset-decomposition.md`](docs/plans/2026-02-25.e-refactor-extract-ruleset-decomposition.md)
