---
title: "refactor: Output .mmd file instead of .graph.md from computation_graph.py"
type: refactor
status: completed
date: 2026-03-04
---

# refactor: Output `.mmd` file instead of `.graph.md`

Change `tools/computation_graph.py` to write raw Mermaid (`.mmd`) instead of a Markdown-wrapped Mermaid file (`.graph.md`), enabling direct loading in Mermaid viewers. Update command files that reference the old filename.

## Acceptance Criteria

- [x] `computation_graph.py` writes `<program>.mmd` (raw `graph TD ...` content, no markdown header or fences)
- [x] `computation_graph.py` no longer writes `<program>.graph.md`
- [x] `.claude/commands/extract-ruleset.md` references `.mmd` (not `.graph.md`) in all locations
- [x] `.claude/commands/update-ruleset.md` references `.mmd` (not `.graph.md`) in all locations
- [x] Command embed instructions updated: read `.mmd` directly and wrap in a mermaid fence (no longer need to extract the fenced block from inside a markdown file)

## Changes

### `tools/computation_graph.py`

- **Output filename**: `{program}.graph.md` → `{program}.mmd`
- **File content**: Drop the markdown header (`# Computation Graph — ...`) and `Generated:` line and the ` ```mermaid ` / ` ``` ` fences — write the raw mermaid string only (e.g., `graph TD\n  ...`)
- Variable/path references: update any `graph_md_path` variable to `mmd_path`

Key lines to change (approximate):
- `tools/computation_graph.py` around line where `graph.md` path is constructed and written

### `.claude/commands/extract-ruleset.md`

Five locations to update:

| Line | Old | New |
|------|-----|-----|
| ~303 | `✓ Draft graph: domains/<domain>/specs/<program>.graph.md` | `✓ Draft graph: domains/<domain>/specs/<program>.mmd` |
| ~317 | `embed the fenced \`mermaid\` block from \`<program>.graph.md\` exactly as written` | `embed the contents of \`<program>.mmd\` in a \`\`\`mermaid fence` |
| ~320 | `[contents of <program>.graph.md — the flowchart LR block]` | `[contents of <program>.mmd]` |
| ~426 | `\| \`domains/<domain>/specs/<program>.graph.md\` \| Generated...` | use `.mmd` |
| ~427 | _(second row in same table if present)_ | update accordingly |

### `.claude/commands/update-ruleset.md`

Same five-location pattern as extract-ruleset.md (lines ~178, ~192, ~195, ~267-268).

## Context

- `.graph.yaml` is unchanged — only the markdown wrapper file is affected
- One stale `.graph.md` file exists (`domains/ak_doh/specs/apa_adltc.graph.md`) — it will be superseded next time the tool runs for that domain; no manual cleanup needed
- One pre-existing `domains/snap/specs/eligibility.mmd` exists from before the tool was created — it will be overwritten correctly on next run

## References

- [`tools/computation_graph.py`](tools/computation_graph.py) — `build_mermaid()` at ~line 121, file-write block at end of `main()`
- [`.claude/commands/extract-ruleset.md`](.claude/commands/extract-ruleset.md) — lines ~303, 317, 320, 426
- [`.claude/commands/update-ruleset.md`](.claude/commands/update-ruleset.md) — lines ~178, 192, 195, 267
