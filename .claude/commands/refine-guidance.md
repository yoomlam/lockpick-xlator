# Refine AI Guidance for a Domain

Create or update `ai-guidance.yaml` for a domain — the extraction goal file that shapes how `/extract-ruleset` reads policy documents. On first run (CREATE), guides the user through goal selection and optional doc-aware Q&A to produce a new file. On subsequent runs (UPDATE), loads the existing file and refines it section by section.

## Input

```
/refine-guidance <domain>
```

If `<domain>` is not provided, list all `domains/*/` directories as a numbered menu, prompt the user to choose, await their response, and use it as `<domain>` before continuing.

## Pre-flight

Run these checks before doing anything else:

1. **Domain argument provided?**
   - NO → List all directories matching `domains/*/` as a numbered menu and prompt:
     ```
     Available domains:
       1. snap
       2. example_domain
     Which domain? Enter a number or domain name:
     ```
     Await the user's response and use it as `<domain>`. Then continue.

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
  Run /index-inputs <domain> now? [y (recommended) / n — continue without index]:
  ```
  - **y** → Execute the `/index-inputs` flow inline for this domain (creating `specs/input-index.yaml`), then proceed to Step 3.
  - **n** → Skip to Step 4 (Q&A with goal-template defaults only).

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

After each section answer, write or update `domains/<domain>/specs/ai-guidance.yaml` immediately — before asking the next section's question. Compose the file from:

- Goal template base (all fields from the selected goal, or an empty scaffold if no template was available)
- `source_template: <goal_id>` — added after `goal_id:` field (use `"none"` if no template was selected)
- `generated_at: <YYYY-MM-DD>` — added after `source_template:`
- Updated `constraints:`, `standards:`, `guidance:` — merged from template + Q&A answers so far
- `edge_cases:` — populated from Q&A so far (empty list `[]` if not yet answered)

The file is created on the first section answer and overwritten on each subsequent one. By the time Step 4 completes, the file is fully populated.

### Step 5: Preview Gate

`ai-guidance.yaml` was written after each Q&A answer in Step 4 and is fully current.
Print: `ai-guidance.yaml is up to date at domains/<domain>/specs/ai-guidance.yaml`

Using observations from Step 3 (topic clusters, section headings, policy excerpts from `input-index.yaml`), synthesize 2–3 illustrative CIVIL rules this guidance would shape the AI to extract. Select examples spanning different rule types (categorical, computed, table-lookup) where the policy supports it.

If Step 3 was skipped (no input index), synthesize examples from the Q&A answers and goal template alone; omit "Source:" lines and add:
> *(No input index available — examples are illustrative only. Run `/index-inputs <domain>` for source-grounded previews.)*

If Step 3 observations are no longer in context (large docs), re-read `domains/<domain>/specs/input-index.yaml` silently to reconstruct.

Present:

─────────────────────────────────────────────
Preview: Rules this guidance would extract
─────────────────────────────────────────────

Rule 1 — [rule name / topic area]
  Source: "[quoted sentence from input-index.yaml section summary]"
  CIVIL:
    rules:
      - id: ...
        when: ...
        then: ...

Rule 2 — [rule name / topic area]
  Source: "..."
  CIVIL:
    computed:
      - name: ...
        ...

[Rule 3 if a third distinct type is identifiable — otherwise 2 is sufficient]

*(Illustrative samples — run `/extract-ruleset` for the full validated ruleset.)*
─────────────────────────────────────────────
Do these look right?
  [a] Looks good
  [1] Refine constraints
  [2] Refine standards
  [3] Refine guidance
  [4] Refine edge_cases
  [x] Reset (rollback file, restart Step 4 Q&A)
  [q] Quit (keep file as-is)

**On [a]:** Proceed to Step 6.

**On [1]–[4]:** Re-ask only that section's Q&A question, showing the user's most recent answer for that section as the pre-filled default:
```
Current [<section>]: (N items)
  - ...
<section key question> (Enter to keep as-is):
```
After the user answers, update `ai-guidance.yaml` immediately, regenerate the preview, and return to this step. Do not continue through the other sections automatically.

**On [x]:** Delete `domains/<domain>/specs/ai-guidance.yaml` and return to the beginning of Step 4.

**On [q]:** Print:
```
Exiting. ai-guidance.yaml saved at domains/<domain>/specs/ai-guidance.yaml
Run /refine-guidance <domain> to continue refining.
```
Stop.

**On unrecognized input:** Re-display the gate options and re-prompt.

### Step 6: Confirm

Print:
```
Created domains/<domain>/specs/ai-guidance.yaml

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
  Run /index-inputs <domain> now? [y (recommended) / n — continue without index]:
  ```
  - **y** → Execute `/index-inputs` inline, then proceed to Step 3.
  - **n** → Skip to Step 4.

### Step 3: Doc analysis *(same as CREATE Step 3, if index available)*

Read and extract signals as in CREATE Step 3.

Additionally: compare index topic tags against existing `guidance:` and `edge_cases:` items. Flag any topic areas prominently tagged in the index but not yet mentioned in guidance:
```
Potential gaps found in current guidance:
  - [topic area] appears frequently in policy docs but is not covered in guidance or edge_cases
```

### Step 4: Q&A refinement (targeted)

Before beginning Q&A, capture the current `ai-guidance.yaml` contents as a rollback snapshot (already in memory from Step 1). This snapshot is used if the user chooses [x] Reset.

If doc analysis flagged gaps, show them first (as above).

Then ask all four section questions in sequence. Prefix each question by showing the existing content for that section:
```
Current [constraints]: (<N> items)
  - ...
  - ...
What should I *not* infer or assume in this domain? (Enter to keep as-is, or describe changes):
```

Only sections where the user provides input are rewritten. Others are preserved verbatim.

After each section answer, write or update `domains/<domain>/specs/ai-guidance.yaml` immediately — before asking the next section's question. Preserve `source_template` unchanged; update `generated_at` to today's date. The file is overwritten on each section answer. By the time Step 4 completes, the file is fully populated.

### Step 5: Preview Gate

`ai-guidance.yaml` was written after each Q&A answer in Step 4 and is fully current.
Print: `ai-guidance.yaml is up to date at domains/<domain>/specs/ai-guidance.yaml`

Using observations from Step 3 (topic clusters, section headings, policy excerpts from `input-index.yaml`), synthesize 2–3 illustrative CIVIL rules this guidance would shape the AI to extract. Select examples spanning different rule types (categorical, computed, table-lookup) where the policy supports it.

If Step 3 was skipped (no input index), synthesize examples from the Q&A answers and goal template alone; omit "Source:" lines and add:
> *(No input index available — examples are illustrative only. Run `/index-inputs <domain>` for source-grounded previews.)*

If Step 3 observations are no longer in context (large docs), re-read `domains/<domain>/specs/input-index.yaml` silently to reconstruct.

Present:

─────────────────────────────────────────────
Preview: Rules this guidance would extract
─────────────────────────────────────────────
*(Showing illustrative samples based on updated guidance — existing rules will be preserved in the merge.)*

Rule 1 — [rule name / topic area]
  Source: "[quoted sentence from input-index.yaml section summary]"
  CIVIL:
    rules:
      - id: ...
        when: ...
        then: ...

Rule 2 — [rule name / topic area]
  Source: "..."
  CIVIL:
    computed:
      - name: ...
        ...

[Rule 3 if a third distinct type is identifiable — otherwise 2 is sufficient]

*(Illustrative samples — run `/extract-ruleset` for the full validated ruleset.)*
─────────────────────────────────────────────
Do these look right?
  [a] Looks good
  [1] Refine constraints
  [2] Refine standards
  [3] Refine guidance
  [4] Refine edge_cases
  [x] Reset (restore original file, restart Step 4 Q&A)
  [q] Quit (keep file as-is)

**On [a]:** Proceed to Step 6.

**On [1]–[4]:** Re-ask only that section's Q&A question, showing the user's most recent answer for that section as the pre-filled default:
```
Current [<section>]: (N items)
  - ...
<section key question> (Enter to keep as-is):
```
After the user answers, update `ai-guidance.yaml` immediately, regenerate the preview, and return to this step. Do not continue through the other sections automatically.

**On [x]:** Restore `domains/<domain>/specs/ai-guidance.yaml` to the rollback snapshot captured before Step 4 began, then return to the beginning of Step 4.

**On [q]:** Print:
```
Exiting. ai-guidance.yaml saved at domains/<domain>/specs/ai-guidance.yaml
Run /refine-guidance <domain> to continue refining.
```
Stop.

**On unrecognized input:** Re-display the gate options and re-prompt.

### Step 6: Confirm

Print:
```
Updated domains/<domain>/specs/ai-guidance.yaml

Next: Run /extract-ruleset <domain> to extract the CIVIL ruleset.
      Re-run /refine-guidance <domain> at any time to update guidance.
```

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
