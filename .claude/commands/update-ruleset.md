# Update Ruleset from Changed Policy Documents

Update an existing CIVIL DSL ruleset for a domain when input policy documents have changed.

## Input

```
/update-ruleset <domain>                          # auto-detect program or prompt if ambiguous
/update-ruleset <domain> <program>                # target a specific <program>.civil.yaml
/update-ruleset <domain> <program> <filename>     # scope update to one input file
```

`<filename>` is the basename of a `.md` file in `domains/<domain>/input/policy_docs/` (e.g., `APA.md`). The `.md` extension is appended automatically if omitted. When given, `<filename>` scopes the full pipeline: only that file is read as the policy corpus, and only its manifest entry is updated.

If `<domain>` is not provided, list all `domains/*/input/policy_docs/` directories and prompt the user to choose.

---

Read `core/ruleset-shared.md` now. It contains shared pre-flight logic (checks 3–6),
the scoring rubric, CIVIL reference, shared procedures (Sub-A/B/C), and common mistakes.

---

## Pre-flight

Run these checks before doing anything else:

1. **Domain folder exists?**
   - NO → Print: domain not found at `domains/<domain>/`, suggest running `/new-domain <domain>`. Stop.

2. **CIVIL file exists?**
   - NO → Print: no ruleset found for this domain, suggest `/extract-ruleset <domain>`. Stop.

Run shared pre-flight checks 3–6 from `core/ruleset-shared.md`.

---

## Process

### Step 0: Load Naming Manifest and Check for Divergence

**If `domains/<domain>/specs/naming-manifest.yaml` exists:**

1. Read all field names from the manifest (`entities.<EntityName>.<field>` keys and `computed.<field>` keys)
2. Read all fact and computed field names from `domains/<domain>/specs/<program>.civil.yaml`
3. Compare the two sets. If any field name exists in the CIVIL file but not the manifest, or exists in both but with a different spelling, **halt** and list every mismatch:

   > ⚠️ Naming manifest divergence detected:
   > - CIVIL has `income` under `Household`, but manifest expects `gross_monthly_income`
   >
   > Resolve by either:
   > a) Editing the CIVIL file to restore the manifest name, or
   > b) Editing `naming-manifest.yaml` to acknowledge the rename
   >
   > Then re-run `/update-ruleset <domain>`.

   Do not continue until there are no mismatches.

**If the manifest does not exist** (domain was extracted before this feature was added):

> ⚠️ No naming manifest found. Field names will not be enforced this run. A manifest will be created after this UPDATE completes.

Proceed to Step 1.

### Step 1: Load Baseline

Read `domains/<domain>/specs/extraction-manifest.yaml` to get the git SHA for each source doc.

**Fallback chain (if manifest absent):**
1. Get the CIVIL file's last commit SHA: `git log -1 --format="%H" -- domains/<domain>/specs/<program>.civil.yaml`
2. If no git history at all → treat as CREATE mode (full re-extraction); run `/extract-ruleset <domain>` instead.

### Step 1b: Reconcile Manifest

Before change detection, remove stale entries from `extraction-manifest.yaml` for files that no longer exist on disk. For each `source_docs` path, check if the file exists; if absent, remove that entry and print `Removed stale manifest entry: <path>`. Runs on every UPDATE invocation — ensures deleted or renamed input files don't cause change detection failures.

### Step 2: Detect Changes

If `<filename>` is given, scope change detection to that file only:

```bash
# Scoped (when <filename> is given):
git diff <baseline-sha>..HEAD -- domains/<domain>/input/policy_docs/<filename>
git status domains/<domain>/input/policy_docs/<filename>

# Full (when <filename> is not given):
git diff <baseline-sha>..HEAD -- domains/<domain>/input/policy_docs/
git status domains/<domain>/input/policy_docs/
```

Collect the list of changed/added/deleted input docs.

### Step 3: No Changes — Exit Early

If no changes detected:
```
All input docs are up to date. Nothing to extract.
To re-extract anyway, delete or rename domains/<domain>/specs/extraction-manifest.yaml and re-run.
```
Stop. Do not modify any files.

### Step 4: Identify Affected CIVIL Sections

For each changed doc, read the diff and determine which CIVIL sections need updating:

| Type of Change in Input Doc | Affected CIVIL Sections |
|---|---|
| Dollar thresholds by household size | `tables:`, possibly `computed:` (size 9+ formulas) |
| Fixed rates or percentages | `constants:` |
| New applicant fields added | `facts:`, possibly `rules:` |
| New eligibility test or condition | `rules:`, possibly `computed:` |
| Effective date change | `effective:` |
| Jurisdiction change | `jurisdiction:` |
| Deduction formula change | `computed:`, `constants:`, `rules:` |

### Step 5: Re-extract Affected Sections

**If `ai-guidance.yaml` was loaded in pre-flight**, recall the extraction goal before re-reading any policy sections:

```
---
[ai-guidance.yaml content — paste verbatim as loaded]
---

Apply these constraints and standards when re-extracting the affected CIVIL sections.
```

For each affected section, re-read the relevant parts of the changed policy doc and re-extract only that section. Do not touch sections not identified in Step 4.

When re-extracting any section that contains `facts:` or `computed:` fields, inject the frozen names from `naming-manifest.yaml` into your extraction reasoning: "These fields must keep their exact current names: [list all names from manifest]. Only introduce new field names for policy concepts not in this list, using the 4-step algorithm: (1) exact noun phrase, (2) strip entity-name words, (3) snake_case, (4) disambiguate if needed." **Never rename an existing field.**

### Step 6: Merge into Existing CIVIL File

Update the existing `domains/<domain>/specs/<program>.civil.yaml` at section granularity:
- Replace only the affected top-level sections (`tables:`, `constants:`, `rules:`, etc.)
- Preserve all unchanged sections verbatim (including comments and formatting)
- Preserve any hand-edits in unchanged sections

### Step 7: Update Manifest

Update `domains/<domain>/specs/extraction-manifest.yaml`:

**If `<filename>` was given (partial update):**
- Update `extracted_at` to today's date
- In `source_docs:`, find the entry for `<filename>` and update its `git_sha` and `last_extracted`
- If no entry exists yet for `<filename>`, add one
- Preserve all other `source_docs:` entries verbatim (files not processed this run keep their existing SHA)

**If `<filename>` was not given (full update):**
- Update `git_sha` for each changed source doc
- Update `extracted_at` to today's date

### Step 8: Validate

Run **Sub-A: Validate**.

### Step 8b: Generate Computation Graph (Preview)

```bash
python tools/computation_graph.py domains/<domain>/specs/<program>.civil.yaml
```

Always run unconditionally — regenerates even if graph files already exist from a prior run.
Capture stdout. Do not echo verbatim.

**On success (exit 0):**
Read `domains/<domain>/specs/<program>.graph.yaml`. Extract all nodes where `kind == "computed"`.

**On failure (exit 1):**
Print `Warning: computation graph preview could not be generated — continuing to review.`
Proceed to Step 9 without showing graph content.

### Step 9: Human Review Gate

**If Step 8b succeeded**, show the following block before the `Changed input docs:` block:

```
✓ Draft graph: domains/<domain>/specs/<program>.mmd

Dependency graph (computed fields):
  <field_1>    ← <dep_1>, <dep_2>    → <used_by_1>
  <field_2>    ← <dep_1>             → [rule: <rule_id>]
  ...
```

Format each line as: `<node_key>  ← <depends_on list>  → <used_by list>`
- `depends_on`: join with `, ` — raw field names; no decoration
- `used_by`: prefix rule nodes with `[rule: ]`; plain names for computed refs
- Empty `depends_on`: show `← [no deps]`; empty `used_by`: show `→ [unused]` (potential dead-code)
- Zero computed fields: replace the table with `(No computed fields in this module.)` but still show the Mermaid block

Then embed the contents of `<program>.mmd` in a ```mermaid fence:

````mermaid
[contents of <program>.mmd]
````

---

Present a **diff-style summary** (not the full ruleset):

```
Changed input docs:
  - input/policy_docs/<filename>.md

Updated CIVIL sections:
  tables.gross_income_limits:
    OLD: household_size=3 → max_gross_monthly: $2,888
    NEW: household_size=3 → max_gross_monthly: $2,945
    Source: "<quote from policy doc>"

  rules.FED-SNAP-DENY-003:
    OLD when: <expression>   OLD scores: fidelity:3 clarity:3 logic:2 policy:3
    NEW when: <expression>   NEW scores: fidelity:2 clarity:2 logic:3 policy:4
    NEW Notes: "'unless' clause may need a separate allow rule for exemption paths"

  (repeat for each changed row/constant/rule/computed field)
```

**Score reset:** When a rule or computed field is re-extracted, its `review:` block is replaced entirely with fresh scores. Unchanged items retain their existing scores. Score reset applies at section granularity — if a `computed:` section is re-extracted, all fields in that section get new scores.

Ask: "Does this update look correct? Any changes missing or incorrect?"

**On rejection:** Re-extract the specific disputed section, re-merge, re-validate, re-present. Do not proceed until confirmed.

### Step 9b: Update Naming Manifest

If any new fact or computed fields were added: derive canonical names using the 4-step algorithm from `/extract-ruleset` Step 3b, then append them to `naming-manifest.yaml` under the appropriate entity or `computed:` section. Preserve all existing entries unchanged.

If no manifest exists yet, create it now from all current CIVIL field names. No user confirmation needed — this runs automatically after the review gate passes.

### Step 9c: Write Stale-Cases Hint

After the review gate passes, write `domains/<domain>/specs/.stale-cases.yaml` for use by `/create-tests`:

```yaml
# Written by /update-ruleset. Consumed and deleted by /create-tests.
stale_cases:
  - case_id: "<case_id>"
    reason: "<what changed — e.g., 'gross_limit for household_size 3 changed from 2888 to 2945'>"
```

Include any test case whose `inputs` contain a value that was a table boundary or constant value in the old CIVIL file but has changed in the updated version. If no cases are stale, write an empty list:
```yaml
stale_cases: []
```

### Step 9d: Refresh Computation Graph

Run **Sub-B: Generate Computation Graph**.

Run **Sub-C: Guidance Capture**.

Run **Sub-D: Extraction Complete Footer**.

---

## Output

Files created or modified by this command:

| File | Action |
|------|--------|
| `domains/<domain>/specs/<program>.civil.yaml` | Updated (affected sections only) |
| `domains/<domain>/specs/extraction-manifest.yaml` | Updated |
| `domains/<domain>/specs/naming-manifest.yaml` | Updated (new fields appended) |
| `domains/<domain>/specs/<program>.graph.yaml` | Generated (Step 8b) / Refreshed (Step 9d) |
| `domains/<domain>/specs/<program>.mmd` | Generated (Step 8b) / Refreshed (Step 9d) |
| `domains/<domain>/specs/.stale-cases.yaml` | Created (after Step 9c; consumed by `/create-tests`) |
| `domains/<domain>/specs/input-index.yaml` | Read-only (if present) |
| `domains/<domain>/specs/ai-guidance.yaml` | Read (required — run `/refine-guidance <domain>` first) / Updated by Sub-C if guidance items accepted |

Tests, transpilation, and Rego output are handled by `/create-tests` and `/transpile-and-test`.
