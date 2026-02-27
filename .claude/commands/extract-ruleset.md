# Extract or Update Ruleset from Policy Documents

Create or incrementally update a CIVIL DSL ruleset for a domain, based on documents in its `input/policy_docs/` subfolder. Handles both first-time extraction (CREATE) and updating an existing ruleset when input documents have changed (UPDATE).

## Input

```
/extract-ruleset <domain>                          # auto-detect program or prompt if ambiguous
/extract-ruleset <domain> <program>                # target a specific <program>.civil.yaml
/extract-ruleset <domain> <program> <filename>     # scope extraction to one input file
```

`<filename>` is the basename of a `.md` file in `domains/<domain>/input/policy_docs/` (e.g., `APA.md`). The `.md` extension is appended automatically if omitted. When given, `<filename>` scopes the full pipeline: only that file is read as the policy corpus, and only its manifest entry is updated.

If `<domain>` is not provided, list all `domains/*/input/policy_docs/` directories and prompt the user to choose.

## Pre-flight

Run these checks before doing anything else:

1. **Domain folder exists?**
   - NO → Offer to scaffold the standard structure:
     ```
     domains/<domain>/
       input/policy_docs/
       specs/
       output/
       demo/
     ```
     Print the structure, tell the user to add `.md` policy documents to `input/policy_docs/`, then stop.

2. **Input docs present?**
   - `domains/<domain>/input/policy_docs/` missing or empty → Print: "No input documents found. Add `.md` files to `domains/<domain>/input/policy_docs/` and re-run." Then stop.

3. **`<filename>` valid (if given)?**
   - If `<filename>` has no `.md` extension, append it automatically (e.g., `APA` → `APA.md`)
   - Verify `domains/<domain>/input/policy_docs/<filename>` exists on disk
   - If not found: print `"File not found: domains/<domain>/input/policy_docs/<filename>"`, list available `.md` files, then stop.

4. **Multiple input docs + no `<filename>`?**
   - If `domains/<domain>/input/policy_docs/` contains 2+ `.md` files and `<filename>` was **not** given, prompt:
     ```
     Multiple policy documents found in domains/<domain>/input/policy_docs/:
       1. <file1>.md
       2. <file2>.md
       ...
       a. All files (unified corpus)

     Process which file? [1/2/.../a]:
     ```
   - Selecting `a` proceeds with all files as a unified corpus (unchanged behavior).
   - Selecting a number sets `<filename>` to that file for the rest of the run.

## Mode Detection

```bash
ls domains/<domain>/specs/*.civil.yaml 2>/dev/null
```

| Count | Action |
|-------|--------|
| 0 files | **CREATE mode** — extract from scratch |
| 1 file | **UPDATE mode** — update that file |
| 2+ files and no `<program>` arg | List them, prompt: "Which program to update? (or specify as second argument)" |
| 2+ files and `<program>` arg given | **UPDATE mode** on `<program>.civil.yaml` |

---

## Scoring Rubric

When writing `review:` blocks, score each rule and computed field on four dimensions using this table. Apply scores independently — a rule can have high fidelity and high complexity simultaneously.

| Score | extraction_fidelity | source_clarity | logic_complexity | policy_complexity |
|-------|---------------------|----------------|------------------|-------------------|
| 1 | Guessed; source is silent on this | Contradictory or absent from source | Single boolean or comparison | Plain everyday English |
| 2 | Inferred with low confidence | Vague; multiple reasonable interpretations | 2–3 conditions, no table lookups | Some jargon or implicit cross-refs |
| 3 | Reasonable translation with minor gaps | Reasonably clear with minor ambiguity | 4–6 conditions or 1 table lookup | Moderate legalese or defined terms |
| 4 | Strong match to source text | Clear but uses statutory defined terms | 7–9 conditions or 2+ table lookups | Dense statutory language or CFR references |
| 5 | Direct quote or explicit formula | Exact thresholds/formulas stated verbatim | 10+ conditions, nested booleans, multiple tables | Exceptions-to-exceptions, multi-CFR cross-refs |

**Special cases:**
- Structural allow rules (`when: "true"`) always score `logic_complexity: 1`. Score `extraction_fidelity` and `source_clarity` based on whether the policy explicitly states the default-allow logic or leaves it implicit.
- `notes:` is required for any item where any score is ≤ 2 or ≥ 4. For all-3 items, `notes:` may be omitted.

---

## CIVIL Reference

> **Do NOT read `tools/civil_schema.py`, `tools/transpile_to_opa.py`, or any other
> file in `tools/` before authoring any CIVIL YAML (Step 4 in CREATE, Step 5 in UPDATE).**
> All syntax and type constraints needed for authoring are in this section and in
> [`docs/civil-quickref.md`](../docs/civil-quickref.md).

### Expression Language

For `when:` conditions and `computed:` expressions:

- Field access: `Household.household_size`, `Applicant.age`
- Constants: `MIN_AGE`, `INCOME_MULTIPLIER`
- Table lookup: `table('gross_income_limits', Household.household_size).max_gross_monthly`
- Boolean: `&&`, `||`, `!`
- Comparison: `==`, `!=`, `<`, `<=`, `>`, `>=`
- Arithmetic: `+`, `-`, `*`, `/`
- Functions: `exists(field)`, `is_null(field)`, `between(value, min, max)`, `in(value, [a, b, c])`
- `computed:` only: `max(a, b)`, `min(a, b)` — computed field names as bare identifiers

**Multi-step formulas (CIVIL v2):** Use a `computed:` section for chains where each step depends on the prior (e.g., a deduction chain). The `when:` clause references the final computed field name directly.

### Schema Constraints

Non-obvious type and structural rules:

- **`FactField` has no `default:` attribute** — use `optional: true` instead; defaults are input-level concerns
- **String type is `string`**, not `str` — valid types: `int`, `float`, `bool`, `string`, `date`, `money`, `list`, `set`, `enum`
- **`ComputedField.type` is limited** to `money`, `bool`, `float`, `int` — no `string` in computed fields
- **`Jurisdiction` requires `country:`** — e.g., `country: US` — it is not optional
- **`Rule.then` must be non-empty** — every rule (allow and deny) needs at least one action
- **`Conditional` requires all three branches** — `if`, `then`, and `else` are all required; no optional else
- **Transpiler ignores allow rules** — only `deny` rules generate Rego; `then:` actions on allow rules are documentary only

For full attribute tables (required vs optional fields for each model), see [`docs/civil-quickref.md`](../docs/civil-quickref.md).

---

## Process — CREATE Mode

### Step 1: Read Policy Documents

If `<filename>` is given, read only `domains/<domain>/input/policy_docs/<filename>`.
Otherwise, read every `.md` file in `domains/<domain>/input/policy_docs/` as a unified policy corpus.

Identify:

1. **Program name and jurisdiction** — what benefit/program, which level of government
2. **Effective dates** — when do these rules apply?
3. **Applicant/household facts** — what information does a caseworker collect? (income, family size, age, etc.)
4. **Eligibility decisions** — what yes/no determinations does the policy make?
5. **Income thresholds and lookup tables** — tables of dollar amounts by household size, age band, etc.
6. **Named constants** — fixed rates, percentages, dollar amounts used in rules
7. **The rules themselves** — conditions for allow vs. deny, and the reasons given
8. **Legal citations** — CFR sections, USC provisions, or other citable authority

### Step 2: Identify CIVIL Components

Map policy elements to CIVIL DSL constructs:

| Policy Element | CIVIL Construct |
|---|---|
| Household/applicant inputs | `facts:` entity with typed fields |
| Eligibility outcome | `decisions:` (usually `eligible: bool`) |
| Denial/approval explanations | `decisions: denial_reasons: list[Reason]` |
| Dollar thresholds by size | `tables:` with key/value rows |
| Fixed rates/amounts | `constants:` |
| **Intermediate derived values** | **`computed:` fields (CIVIL v2)** |
| Income/asset test | `rules:` with `kind: deny` |
| Pass all tests → eligible | `rules:` with `kind: allow`, `when: "true"` |

### Step 3: Derive Program Name

Use `<program>` argument if given. Otherwise:
1. Infer from the `module:` name found in the policy text (e.g., "SNAP income eligibility" → `eligibility`)
2. If ambiguous, prompt: "What should the program file be named? (e.g., `eligibility`, `income_test`)"

### Step 3b: Name Inventory

Before drafting any CIVIL YAML, produce the canonical field name for every fact and computed concept in the policy. For each measurable quantity, flag, or derived value found in the policy documents, apply this algorithm:

1. Find the **exact noun phrase** in the policy text describing the concept
2. Use specific field names to evoke the meaning without having to look up the corresponding policy text and minimize risk of name collisions in future extractions
3. **Strip** any words that duplicate the entity name (e.g., entity is `Household` → strip "household" from "household gross income" → `gross income`)
4. Convert to **`snake_case`**
5. If the result would be **ambiguous** with another field in the same entity, append a disambiguating qualifier from the policy text

Present the result as a Markdown table:

| Policy Phrase | Entity / Section | Field Name | Source Section |
|--------------|-----------------|-----------|----------------|
| gross monthly income | Household | `gross_monthly_income` | §1.2 |
| number of people in the household | Household | `household_size` | §1.1 |
| net monthly income after all deductions | computed | `net_income` | §2.4 |

**If `domains/<domain>/specs/.naming-manifest.yaml` already exists** (CREATE re-run after a previous successful extraction):
- Pre-populate the table with the frozen names from the manifest
- Only derive new names for policy concepts not already listed

Ask: "Do the field names in this table match your intent? You may edit any name." If the user changes any name, update the table and re-present. Loop until the user explicitly approves. Use the approved names in Step 4 onward.

### Step 4: Draft the CIVIL Module

Create `domains/<domain>/specs/<program>.civil.yaml`:

```yaml
module: "eligibility.<program_name>"
description: "..."
version: "<year>Q<quarter>"
jurisdiction:
  level: federal  # or: state, county, city
  country: US
  # state: <code>  # if state-level
effective:
  start: YYYY-MM-DD
  end: YYYY-MM-DD  # optional

facts:
  <EntityName>:
    description: "..."
    fields:
      <field_name>:
        type: <int|float|bool|string|money|date|list|set|enum>
        description: "..."
        currency: USD  # for money type
        optional: true  # if not required

decisions:
  eligible:
    type: bool
    default: false
    description: "..."
  denial_reasons:
    type: list
    item: Reason
    default: []
    description: "..."

tables:
  <table_name>:
    description: "..."
    key: [<key_field>]
    value: [<value_field>]
    rows:
      - { <key_field>: <val>, <value_field>: <val> }

constants:
  UPPER_SNAKE_CASE_NAME: value

computed:  # optional (CIVIL v2) — intermediate derived values for multi-step formulas
  <field_name>:
    type: <money|bool|float|int>
    description: "..."
    expr: "<CIVIL expression>"     # single expression
    review:
      extraction_fidelity: <1-5>
      source_clarity: <1-5>
      logic_complexity: <1-5>
      policy_complexity: <1-5>
      notes: "<explain any score ≤2 or ≥4>"  # omit if all scores are 3
  <field_name_2>:
    type: money
    description: "..."
    conditional:
      if: "<bool expression>"
      then: "<value expression>"
      else: "<value expression>"
    review:
      extraction_fidelity: <1-5>
      source_clarity: <1-5>
      logic_complexity: <1-5>
      policy_complexity: <1-5>
      notes: "<explain any score ≤2 or ≥4>"  # omit if all scores are 3

rule_set:
  name: "<identifier>"
  precedence: "deny_overrides_allow"
  description: "..."

rules:
  - id: "<JURISDICTION>-<TOPIC>-<KIND>-<SEQ>"  # e.g., FED-SNAP-DENY-001
    kind: deny  # or: allow
    priority: 1  # lower = higher priority; allow rules typically 100+
    description: "..."
    when: "<CIVIL expression>"
    then:
      - add_reason:
          code: "MACHINE_CODE"
          message: "Human-readable explanation"
          citations:
            - label: "7 CFR § 273.9(a)(1)"
              url: "https://..."
              excerpt: "Brief excerpt"
    review:                          # assign scores while policy text is in context
      extraction_fidelity: <1-5>
      source_clarity: <1-5>
      logic_complexity: <1-5>
      policy_complexity: <1-5>
      notes: "<explain any score ≤2 or ≥4>"  # omit if all scores are 3
```

**Scoring:** Assign `review:` blocks to every entry in `rules:` and `computed:` as you draft them. Use the Scoring Rubric above. Write scores while the source policy text is in context — do not defer to a separate pass.

**Reference:** See `domains/snap/specs/eligibility.civil.yaml` for a complete working example. See the **CIVIL Reference** section above for expression language syntax and multi-step formula guidance.

### Step 5: Write Extraction Manifest

Create `domains/<domain>/specs/.extraction-manifest.yaml`:

```yaml
# Auto-generated by /extract-ruleset — do not edit manually
civil_file: <program>.civil.yaml
extracted_at: "YYYY-MM-DD"
source_docs:
  - path: input/policy_docs/<filename>.md
    git_sha: "<sha>"   # from: git log -1 --format="%H" -- domains/<domain>/input/policy_docs/<filename>.md
    last_extracted: "YYYY-MM-DD"
```

Get each doc's git SHA:
```bash
git log -1 --format="%H" -- domains/<domain>/input/policy_docs/<filename>.md
```
If a file is untracked (not yet committed), use `"untracked"` as the SHA.

### Step 6: Validate

```bash
python tools/validate_civil.py domains/<domain>/specs/<program>.civil.yaml
```

**On failure — retry loop (max 3 attempts):**
- Read the specific error message
- Identify the offending CIVIL section
- Re-extract or fix that section
- Re-validate

After 3 failed attempts, stop and print:
```
Validation failed after 3 attempts. Errors:
  <error list>
Fix manually, then re-run: python tools/validate_civil.py domains/<domain>/specs/<program>.civil.yaml
```

### Step 7: Human Review Gate

Partition all `rules:` entries and `computed:` fields into three buckets based on their `review:` scores:

| Bucket | Condition | Meaning |
|--------|-----------|---------|
| **Uncertain Extractions** | `extraction_fidelity` ≤ 2 OR `source_clarity` ≤ 2 | Claude wasn't confident — human must verify |
| **Complex Rules** | `logic_complexity` ≥ 4 OR `policy_complexity` ≥ 4 | Inherently dense — worth careful review |
| **Verified** | Not in either bucket above | All scores in range fidelity 3–5, clarity 3–5, logic 1–3, policy 1–3 |

Items in **both** buckets appear once under Uncertain Extractions with both flags noted.

**Summary header** (always show first):
```
Review summary: X uncertain, Y complex, Z verified  (N items total)
```

**Uncertain Extractions format** (one block per item):
```
─────────────────────────────────────────────────────────────────
⚠️  UNCERTAIN: <rule-id or "computed: <field_name>">
    Scores: fidelity:<N> clarity:<N> logic:<N> policy:<N>
    Flagged for: <"low extraction fidelity" and/or "low source clarity">
                 <+ "high logic complexity" and/or "high policy complexity" if also complex>
    Policy: "<exact source sentence(s)>"
    CIVIL:  <when: expression or expr:/conditional:>
    Notes:  <notes field content, or "(none)" if omitted>
─────────────────────────────────────────────────────────────────
```

**Complex Rules format** (one block per item; excludes items already shown under Uncertain):
```
─────────────────────────────────────────────────────────────────
🔍  COMPLEX: <rule-id or "computed: <field_name>">
    Scores: fidelity:<N> clarity:<N> logic:<N> policy:<N>
    Flagged for: <"high logic complexity" and/or "high policy complexity">
    Policy: "<exact source sentence(s)>"
    CIVIL:  <when: expression or expr:/conditional:>
    Notes:  <notes field content, or "(none)" if omitted>
─────────────────────────────────────────────────────────────────
```

**Verified compact list**:
```
✅  VERIFIED (<N> items — not uncertain, not complex)
    • FED-SNAP-DENY-001: Gross income exceeds 130% FPL limit
    • computed: gross_income — total household gross monthly income
    ...
```

**Edge cases:**
- If no uncertain items → omit the Uncertain Extractions section entirely.
- If no complex items → omit the Complex Rules section entirely.
- If no verified items → omit the Verified list.
- If ALL items verified → show: "All items verified — no uncertain or complex items."

Ask: "Does this translation correctly capture the policy intent? Any rules missing or incorrect?"

**On rejection:** Re-extract the specific disputed rule or computed field, re-validate (using the retry loop), recompute its `review:` scores, then re-present the full review gate. Do not proceed until the user confirms.

### Step 7b: Write Naming Manifest

Now that the user has approved the rule-by-rule review, write `domains/<domain>/specs/.naming-manifest.yaml` using every entry from the approved Name Inventory table (Step 3b):

```yaml
version: "1.0"
entities:
  <EntityName>:
    <field_name>:
      policy_phrase: "<exact policy phrase from Name Inventory>"
      source_doc: "<source filename>"
      section: "<section heading>"
  # repeat for each entity
computed:
  <field_name>:
    policy_phrase: "<exact policy phrase>"
    source_doc: "<source filename>"
    section: "<section heading>"
```

**If `.naming-manifest.yaml` already exists** (CREATE re-run): merge — preserve all existing entries unchanged and append only new entries.

This file is user-editable. Do **not** add an "auto-generated" comment.

---

**Extraction complete.**

If `<filename>` was given and other `.md` files exist in `domains/<domain>/input/policy_docs/` that were not processed, print:
```
Note: this domain has other policy docs not included in this run:
  - <other_file>.md
  ...
To extract from all files as a unified corpus, run without specifying a filename.
```

```
Next steps:
  1. /create-tests <domain>
  2. /transpile-and-test <domain>
```

---

## Process — UPDATE Mode

### Step 0: Load Naming Manifest and Check for Divergence

**If `domains/<domain>/specs/.naming-manifest.yaml` exists:**

1. Read all field names from the manifest (`entities.<EntityName>.<field>` keys and `computed.<field>` keys)
2. Read all fact and computed field names from `domains/<domain>/specs/<program>.civil.yaml`
3. Compare the two sets. If any field name exists in the CIVIL file but not the manifest, or exists in both but with a different spelling, **halt** and list every mismatch:

   > ⚠️ Naming manifest divergence detected:
   > - CIVIL has `income` under `Household`, but manifest expects `gross_monthly_income`
   >
   > Resolve by either:
   > a) Editing the CIVIL file to restore the manifest name, or
   > b) Editing `.naming-manifest.yaml` to acknowledge the rename
   >
   > Then re-run `/extract-ruleset <domain>`.

   Do not continue until there are no mismatches.

**If the manifest does not exist** (domain was extracted before this feature was added):

> ⚠️ No naming manifest found. Field names will not be enforced this run. A manifest will be created after this UPDATE completes.

Proceed to Step 1.

### Step 1: Load Baseline

Read `domains/<domain>/specs/.extraction-manifest.yaml` to get the git SHA for each source doc.

**Fallback chain (if manifest absent):**
1. Get the CIVIL file's last commit SHA: `git log -1 --format="%H" -- domains/<domain>/specs/<program>.civil.yaml`
2. If no git history at all → treat as CREATE mode (full re-extraction)

### Step 1b: Reconcile Manifest

Before change detection, remove stale entries from `.extraction-manifest.yaml` for files that no longer exist on disk:

```bash
# For each path listed in source_docs:
ls domains/<domain>/input/policy_docs/<path_basename> 2>/dev/null
# If the file is absent: remove that entry from source_docs and print:
#   Removed stale manifest entry: <path>
```

This runs on every UPDATE invocation, regardless of whether `<filename>` was given. It ensures deleted or renamed input files don't cause change detection failures.

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
Run with --force to re-extract regardless.
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

For each affected section, re-read the relevant parts of the changed policy doc and re-extract only that section. Do not touch sections not identified in Step 4.

When re-extracting any section that contains `facts:` or `computed:` fields, inject the frozen names from `.naming-manifest.yaml` into your extraction reasoning: "These fields must keep their exact current names: [list all names from manifest]. Only introduce new field names for policy concepts not in this list, using the 4-step algorithm: (1) exact noun phrase, (2) strip entity-name words, (3) snake_case, (4) disambiguate if needed." **Never rename an existing field.**

### Step 6: Merge into Existing CIVIL File

Update the existing `domains/<domain>/specs/<program>.civil.yaml` at section granularity:
- Replace only the affected top-level sections (`tables:`, `constants:`, `rules:`, etc.)
- Preserve all unchanged sections verbatim (including comments and formatting)
- Preserve any hand-edits in unchanged sections

### Step 7: Update Manifest

Update `domains/<domain>/specs/.extraction-manifest.yaml`:

**If `<filename>` was given (partial update):**
- Update `extracted_at` to today's date
- In `source_docs:`, find the entry for `<filename>` and update its `git_sha` and `last_extracted`
- If no entry exists yet for `<filename>`, add one
- Preserve all other `source_docs:` entries verbatim (files not processed this run keep their existing SHA)

**If `<filename>` was not given (full update):**
- Update `git_sha` for each changed source doc
- Update `extracted_at` to today's date

### Step 8: Validate

Same retry loop as CREATE Step 6:
```bash
python tools/validate_civil.py domains/<domain>/specs/<program>.civil.yaml
```
Up to 3 auto-fix attempts, then halt with error list.

### Step 9: Human Review Gate (UPDATE)

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

If any new fact or computed fields were added during this UPDATE:

1. Apply the 4-step naming algorithm (from CREATE Step 3b) to derive the canonical name for each new concept
2. Append the new entries to `domains/<domain>/specs/.naming-manifest.yaml` under the appropriate entity or `computed:` section
3. Preserve all existing manifest entries unchanged

If no naming manifest exists yet (domain was extracted before this feature was added), create it now using all current fact and computed field names from the CIVIL file.

No additional user confirmation needed; this happens automatically after the review gate passes.

### Step 9c: Write Stale-Cases Hint

After the review gate passes, write `domains/<domain>/specs/.stale-cases.yaml` for use by `/create-tests`:

```yaml
# Written by /extract-ruleset UPDATE mode. Consumed and deleted by /create-tests.
stale_cases:
  - case_id: "<case_id>"
    reason: "<what changed — e.g., 'gross_limit for household_size 3 changed from 2888 to 2945'>"
```

Include any test case whose `inputs` contain a value that was a table boundary or constant value in the old CIVIL file but has changed in the updated version. If no cases are stale, write an empty list:
```yaml
stale_cases: []
```

**Extraction complete.**

If `<filename>` was given and other `.md` files exist in `domains/<domain>/input/policy_docs/` that were not processed, print:
```
Note: this domain has other policy docs not included in this run:
  - <other_file>.md
  ...
To extract from all files as a unified corpus, run without specifying a filename.
```

```
Next steps:
  1. /create-tests <domain>
  2. /transpile-and-test <domain>
```

---

## Output

Files created or modified by this command:

| File | CREATE | UPDATE |
|------|--------|--------|
| `domains/<domain>/specs/<program>.civil.yaml` | Created | Updated (affected sections only) |
| `domains/<domain>/specs/.extraction-manifest.yaml` | Created | Updated |
| `domains/<domain>/specs/.naming-manifest.yaml` | Created (after Step 7b) | Updated (new fields appended) |
| `domains/<domain>/specs/.stale-cases.yaml` | — | Created (after Step 9c; consumed by `/create-tests`) |
| `Makefile` | Appended in pre-flight if no target existed | Not touched |

Tests, transpilation, and Rego output are handled by `/create-tests` and `/transpile-and-test`.

## Common Mistakes to Avoid

- **Don't forget `default eligible := false`** — OPA boolean rules are undefined (not false) when conditions don't match; the transpiler handles this automatically for all `bool` fields in `decisions:` and `computed:`
- **Cite the actual CFR/USC section** for each rule, not just "Program Policy Manual"
- **Use `optional: true`** for fact fields that may not always be provided (e.g., `earned_income`, `shelter_costs`)
- **Distinguish earned vs. unearned income** if any deduction applies only to earned income
- **Use `computed:` for multi-step formulas** — don't reference undefined identifiers in `when:` clauses; if a value needs multiple steps to compute, define it in `computed:` and reference it by name
- **Don't use `git diff` alone for change detection** — also run `git status` to catch untracked new files not yet committed
- **Always update the manifest after extraction** — stale git SHAs in `.extraction-manifest.yaml` will cause UPDATE mode to miss real changes on the next run
