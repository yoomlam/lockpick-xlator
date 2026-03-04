# Extract Ruleset from Policy Documents

Create a CIVIL DSL ruleset for a domain from documents in its `input/policy_docs/` subfolder.

## Input

```
/extract-ruleset <domain>                          # auto-detect program or prompt if ambiguous
/extract-ruleset <domain> <program>                # target a specific <program>.civil.yaml
/extract-ruleset <domain> <program> <filename>     # scope extraction to one input file
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

2. **CIVIL file already exists?**
   - **If `<program>` was given:** check if `domains/<domain>/specs/<program>.civil.yaml` exists → if yes, redirect:
     ```
     A ruleset already exists for <program>. To update it, run:
       /update-ruleset <domain> <program>
     ```
     Then stop. Continue if not found.
   - **If `<program>` was not given:** check `domains/<domain>/specs/*.civil.yaml`:
     - 0 files → continue (no existing ruleset)
     - 1 file → redirect:
       ```
       A ruleset already exists for this domain. To update it, run:
         /update-ruleset <domain>
       ```
       Then stop.
     - 2+ files → list them and prompt:
       ```
       Existing rulesets found:
         - <program1>
         - <program2>
         ...
       To update one of these, use /update-ruleset <domain> <program>.
       To create a new program, provide a name: /extract-ruleset <domain> <new_program>
       ```
       Then stop.

Run shared pre-flight checks 3–6 from `core/ruleset-shared.md`.

---

## Process

### Step 1: Read Policy Documents

**If `ai-guidance.yaml` was loaded in pre-flight**, internalize the following before reading any policy documents:

```
---
[ai-guidance.yaml content — paste verbatim as loaded]
---

Use this goal to scope your reading:
- Prioritize policy sections relevant to the input_variables categories listed above.
- Watch for intermediate values matching the intermediate_variables categories.
- Target a <output_variables.primary.type> primary output (mapped to CIVIL decisions[0]).
- Apply all constraints and standards listed above throughout Steps 1–7.
```

If `<filename>` is given, read only `domains/<domain>/input/policy_docs/<filename>`.
Otherwise, read the files selected via the pre-flight prompt (all files if `a` was chosen, or the specific file(s) selected by number).

**If `specs/input-index.yaml` exists**, use the index as a reading guide: skim the index entries for the selected files to understand their structure before reading the full content. This helps prioritize which sections to extract from when the docs are long.

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

**If `domains/<domain>/specs/naming-manifest.yaml` already exists** (CREATE re-run after a previous successful extraction):
- Pre-populate the table with the frozen names from the manifest
- Only derive new names for policy concepts not already listed

Ask: "Do the field names in this table match your intent? You may edit any name." If the user changes any name, update the table and re-present. Loop until the user explicitly approves. Use the approved names in Step 4 onward.

**`source:` population:** In Step 4, populate `source:` on every `FactField`, `ComputedField`, `TableDef`, and `Rule` using the "Source Section" value from the Name Inventory table above, *combined* with the surrounding document heading:

- Format: `"<§ citation> — <heading>"`, e.g. `"7 CFR § 273.9(a) — Income and Deductions"`
- If the "Source Section" column contains only a bare citation (`"§ 273.9(a)"`), prepend the full CFR title reference and append the heading from the enclosing document section
- For `Rule` entries (not in the Name Inventory table), derive `source:` from the heading and paragraph of the policy text where the rule's condition is stated
- `source:` is optional — if the policy document has no clear section for a given element, omit it rather than guessing

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
        source: "<§ citation> — <heading>"  # e.g., "7 CFR § 273.9(a) — Income and Deductions"
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
    source: "<§ citation> — <heading>"  # e.g., "7 CFR § 273.9(a)(1) — Gross Income Limits Table"
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
    source: "<§ citation> — <heading>"  # e.g., "7 CFR § 273.9(d)(1) — Earned Income Deduction"
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
    source: "<§ citation> — <heading>"
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
    source: "<§ citation> — <heading>"  # e.g., "7 CFR § 273.9(a)(1) — Gross Income Test"
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

**Scoring:** Assign `review:` blocks to every entry in `rules:` and `computed:` as you draft them. Use the Scoring Rubric from `core/ruleset-shared.md`. Write scores while the source policy text is in context — do not defer to a separate pass.

**Reference:** See the **CIVIL Reference** section in `core/ruleset-shared.md` for expression language syntax and multi-step formula guidance.

### Step 5: Write Extraction Manifest

Create `domains/<domain>/specs/extraction-manifest.yaml`:

```yaml
# Auto-generated by /extract-ruleset — do not edit manually
programs:
  <program>:
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

Run **Sub-A: Validate**.

### Step 6b: Generate Computation Graph (Preview)

```bash
python tools/computation_graph.py domains/<domain>/specs/<program>.civil.yaml
```

Always run unconditionally — regenerates even if graph files already exist from a prior run.
Capture stdout. Do not echo verbatim.

**On success (exit 0):**
Read `domains/<domain>/specs/<program>.graph.yaml`. Extract all nodes where `kind == "computed"`.

**On failure (exit 1):**
Print `Warning: computation graph preview could not be generated — continuing to review.`
Proceed to Step 7 without showing graph content.

### Step 7: Human Review Gate

**If Step 6b succeeded**, show the following block before the `Review summary:` header:

```
✓ Draft graph: domains/<domain>/specs/<program>.graph.md

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

Then embed the fenced `mermaid` block from `<program>.graph.md` exactly as written (do not re-generate):

````mermaid
[contents of <program>.graph.md — the flowchart LR block]
````

---

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

Now that the user has approved the rule-by-rule review, write `domains/<domain>/specs/naming-manifest.yaml` using every entry from the approved Name Inventory table (Step 3b):

```yaml
version: "1.0"
entities:
  <EntityName>:
    <field_name>:
      policy_phrase: "<exact policy phrase from Name Inventory>"
      source_doc: "<source filename>"
      section: "<source title, heading, and paragraph>"
  # repeat for each entity
computed:
  <field_name>:
    policy_phrase: "<exact policy phrase>"
    source_doc: "<source filename>"
    section: "<source title, heading, and paragraph>"
```

**If `naming-manifest.yaml` already exists** (CREATE re-run): merge — preserve all existing entries unchanged and append only new entries.

This file is user-editable. Do **not** add an "auto-generated" comment.

### Step 7c: Refresh Computation Graph

Run **Sub-B: Generate Computation Graph**.

---

Run **Sub-C: Extraction Complete Footer**.

---

## Output

Files created or modified by this command:

| File | Action |
|------|--------|
| `domains/<domain>/specs/<program>.civil.yaml` | Created |
| `domains/<domain>/specs/extraction-manifest.yaml` | Created |
| `domains/<domain>/specs/naming-manifest.yaml` | Created (after Step 7b) |
| `domains/<domain>/specs/<program>.graph.yaml` | Generated (Step 6b) / Refreshed (Step 7c) |
| `domains/<domain>/specs/<program>.graph.md` | Generated (Step 6b) / Refreshed (Step 7c) |
| `domains/<domain>/specs/input-index.yaml` | Read-only (if present) |
| `domains/<domain>/specs/ai-guidance.yaml` | Read-only (required — run `/refine-guidance <domain>` first) |

Tests, transpilation, and Rego output are handled by `/create-tests` and `/transpile-and-test`.
