# Refine AI Guidance for a Domain

Create or update `ai-guidance.yaml` for a domain — the extraction goal file that shapes how `/extract-ruleset` reads policy documents. On first run (CREATE), guides the user through goal selection and optional doc-aware Q&A to produce a new file. On subsequent runs (UPDATE), loads the existing file and refines it section by section.

## Input

```
/refine-guidance <domain>
```

If `<domain>` is not provided, list all `domains/*/` directories and prompt the user to choose.

## Pre-flight

Run these checks before doing anything else:

1. **Domain argument provided?**
   - NO → List all directories matching `domains/*/` and prompt: "Which domain? (provide as argument)" Then stop.

2. **Domain folder exists?**
   - NO → Print:
     ```
     Domain not found: domains/<domain>/
     Run: /new-domain <domain>
     ```
     Then stop. Do not scaffold a new domain here — that's `/new-domain`'s job.

3. **Detect mode** — check for `domains/<domain>/specs/ai-guidance.yaml`:
   - **Present** → **UPDATE mode**
   - **Absent** → **CREATE mode**

---

## Process — CREATE Mode

### Step 1: Goal selection

Scan `core/goals/*.yaml` for all available goal files:

- **No files found** → Print `No goal templates found in core/goals/. Continuing without a base template.` and proceed to Step 2 with no base template.
- **Exactly one found** → Print: `One goal template found: <display_name>. Using it.` Ask: `Continue with this goal? [y/n]` — if `n`, stop.
- **Multiple found** → Present a numbered menu of `display_name` values (same numbered-list style used throughout other commands); user selects one.

Print the selected template content for the user to review.

### Step 2: Input index check

Check for `domains/<domain>/specs/input-index.yaml`:

- **Exists** → Read it; proceed to Step 3 (doc analysis).
- **Absent** → Ask:
  ```
  No input index found for this domain. An index enables doc-aware guidance suggestions.
  Run /index-inputs <domain> first, or continue without doc analysis? [index / continue]:
  ```
  - `index` → Execute the `/index-inputs` flow inline for this domain (creating `specs/input-index.yaml`), then proceed to Step 3.
  - `continue` → Skip to Step 4 (Q&A with goal-template defaults only).

### Step 3: Doc analysis *(only if input-index.yaml available)*

Read `domains/<domain>/specs/input-index.yaml` and extract signals:

- **Topic tags** across all sections → cluster to find prominent domain areas
- **Section headings** → reveals statutory structure (e.g., income tests, deduction chains)
- **File summaries** → reveals program scope and terminology

For each of the four guidance sections (`constraints`, `standards`, `guidance`, `edge_cases`), generate a list of proposed additions grounded in these index signals. Hold these proposals for Step 4.

### Step 4: Q&A refinement

Ask one question per section, in order. For each:

1. Show doc-derived proposals (if any from Step 3), formatted as a bullet list.
2. Ask the section's key question (see table below).
3. Incorporate the user's answer: if they confirm, keep proposals; if they add text, append it; if they replace, use their text.

| Section | Key question |
|---|---|
| `constraints` | "What should I *not* infer or assume in this domain?" |
| `standards` | "Are there normalization rules specific to this program? (units, categories, naming)" |
| `guidance` | "What non-obvious rule patterns should I look for?" |
| `edge_cases` | "What special populations or situations does this program treat differently?" |

All four sections are asked in sequence. The user can answer "nothing to add" or press Enter to accept proposals as-is or skip a section.

### Step 5: Write `ai-guidance.yaml`

Compose the file from:

- Goal template base (all fields from the selected goal, or an empty scaffold if no template was available)
- `source_template: <goal_id>` — added after `goal_id:` field (use `"none"` if no template was selected)
- `generated_at: <YYYY-MM-DD>` — added after `source_template:`
- Updated `constraints:`, `standards:`, `guidance:` — merged from template + Q&A answers
- `edge_cases:` — new top-level list, populated from Q&A (empty list `[]` if user skipped)

Write to `domains/<domain>/specs/ai-guidance.yaml`.

Print: `Created domains/<domain>/specs/ai-guidance.yaml`

Print next steps:
```
Next: Run /extract-ruleset <domain> to extract the CIVIL ruleset.
      Re-run /refine-guidance <domain> at any time to update guidance.
```

---

## Process — UPDATE Mode

### Step 1: Load existing file

Read `domains/<domain>/specs/ai-guidance.yaml`. Print a summary:
```
Current guidance: <display_name> (source: <source_template>, updated: <generated_at>)
Sections: constraints (<N> items), standards (<N> items), guidance (<N> items), edge_cases (<N> items)
```

### Step 2: Input index check *(same as CREATE Step 2)*

Check for `domains/<domain>/specs/input-index.yaml`:

- **Exists** → Read it; proceed to Step 3.
- **Absent** → Ask:
  ```
  No input index found for this domain. An index enables doc-aware guidance suggestions.
  Run /index-inputs <domain> first, or continue without doc analysis? [index / continue]:
  ```
  - `index` → Execute `/index-inputs` inline, then proceed to Step 3.
  - `continue` → Skip to Step 4.

### Step 3: Doc analysis *(same as CREATE Step 3, if index available)*

Read and extract signals as in CREATE Step 3.

Additionally: compare index topic tags against existing `guidance:` and `edge_cases:` items. Flag any topic areas prominently tagged in the index but not yet mentioned in guidance:
```
Potential gaps found in current guidance:
  - [topic area] appears frequently in policy docs but is not covered in guidance or edge_cases
```

### Step 4: Q&A refinement (targeted)

If doc analysis flagged gaps, show them first (as above).

Then ask all four section questions in sequence. Prefix each question by showing the existing content for that section:
```
Current [constraints]: (<N> items)
  - ...
  - ...
What should I *not* infer or assume in this domain? (Enter to keep as-is, or describe changes):
```

Only sections where the user provides input are rewritten. Others are preserved verbatim.

### Step 5: Write updated file

Overwrite `domains/<domain>/specs/ai-guidance.yaml`. Preserve `source_template` unchanged. Update `generated_at` to today's date.

Print: `Updated domains/<domain>/specs/ai-guidance.yaml`

---

## Output

```
domains/<domain>/specs/ai-guidance.yaml    [CREATED or UPDATED]
```

## Common Mistakes to Avoid

- Do not add `edge_cases:` to goal template files in `core/goals/` — they are domain-agnostic; `edge_cases:` belongs only in per-domain `ai-guidance.yaml`
- In UPDATE mode, do not rewrite sections the user did not change — preserve exact wording of unchanged sections
- `source_template` is never updated in UPDATE mode — it records which goal the file was originally created from
- Do not create or scaffold a domain folder here — if the domain doesn't exist, stop and refer to `/new-domain`
