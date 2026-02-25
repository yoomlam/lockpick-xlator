# Extract or Update Ruleset from Policy Documents

Create or incrementally update a CIVIL DSL ruleset for a domain, based on documents in its `input/policy_docs/` subfolder. Handles both first-time extraction (CREATE) and updating an existing ruleset when input documents have changed (UPDATE).

## Input

```
/extract-ruleset <domain>               # auto-detect program or prompt if ambiguous
/extract-ruleset <domain> <program>     # target a specific <program>.civil.yaml
```

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

3. **OPA available?**
   ```bash
   which opa
   ```
   - NOT in PATH → Warn: "OPA not found — transpile and test steps will be skipped." Continue; skip Steps 9–10 at the end.

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

## Process — CREATE Mode

### Step 1: Read All Policy Documents

Read every `.md` file in `domains/<domain>/input/policy_docs/` as a unified policy corpus. Identify:

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
2. **Strip** any words that duplicate the entity name (e.g., entity is `Household` → strip "household" from "household gross income" → `gross income`)
3. Convert to **`snake_case`**
4. If the result would be **ambiguous** with another field in the same entity, append a disambiguating qualifier from the policy text

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
  <field_name_2>:
    type: money
    description: "..."
    conditional:
      if: "<bool expression>"
      then: "<value expression>"
      else: "<value expression>"

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
```

**Reference:** See `domains/snap/specs/eligibility.civil.yaml` for a complete working example.

**CIVIL Expression Language** (for `when:` and `computed:` expressions):
- Field access: `Household.household_size`, `Applicant.age`
- Constants: `MIN_AGE`, `INCOME_MULTIPLIER`
- Table lookup: `table('gross_income_limits', Household.household_size).max_gross_monthly`
- Boolean: `&&`, `||`, `!`
- Comparison: `==`, `!=`, `<`, `<=`, `>`, `>=`
- Arithmetic: `+`, `-`, `*`, `/`
- Functions: `exists(field)`, `is_null(field)`, `between(value, min, max)`, `in(value, [a, b, c])`
- `computed:` only: `max(a, b)`, `min(a, b)` — computed field names as bare identifiers

**Multi-step formulas (CIVIL v2):** Use a `computed:` section for chains where each step depends on the prior (e.g., a deduction chain). The `when:` clause references the final computed field name directly.

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

### Step 7: Draft Test Cases

Create `domains/<domain>/specs/tests/<program>_tests.yaml` with at least 6 cases:

| Tag | What to cover |
|-----|---------------|
| `allow` | All conditions comfortably met |
| `deny` + gross test | Fails gross income test (if one exists) |
| `deny` + net test | Passes gross, fails net after deductions |
| `allow` + exemption | Elderly, disabled, or other exemption path |
| `allow` + boundary | Income exactly at a threshold (≤ limit = pass) |
| `deny` + edge | Large household (size 9+), all-zero income, or other extreme |

Test format (inputs always flat key-value, never nested by entity name):
```yaml
test_suite:
  spec: "<program>.civil.yaml"
  description: "..."
  version: "1.0"

tests:
  - case_id: "allow_001"
    description: "..."
    inputs:
      household_size: 3
      gross_monthly_income: 1800
      # ... flat key-value
    expected:
      eligible: true
      denial_reasons: []
    tags: ["happy_path", "allow"]
```

**Reference:** See `domains/snap/specs/tests/eligibility_tests.yaml`.

### Step 8: Human Review Gate

Present a rule-by-rule summary:

For each rule in `rules:`:
- **Rule ID and description**
- **Source policy quote** — the exact sentence(s) in the input doc that this rule implements
- **CIVIL `when:` expression** — how it was encoded

Ask: "Does this translation correctly capture the policy intent? Any rules missing or incorrect?"

**On rejection:** Re-extract the specific disputed rule, re-validate (using the retry loop), then re-present the review gate. Do not proceed to transpilation until the user confirms.

### Step 8b: Write Naming Manifest

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

### Step 9: Scaffold Makefile Target

Check if a target for `<domain>` already exists:
```bash
grep -n "<domain>-validate" Makefile
```

If missing, append a new block to `Makefile`, modeled exactly on the SNAP block:

```makefile
# ---------------------------------------------------------------------------
# <DOMAIN_UPPER> — <description from CIVIL module>
# ---------------------------------------------------------------------------

<DOMAIN>_CIVIL    := domains/<domain>/specs/<program>.civil.yaml
<DOMAIN>_TESTS    := domains/<domain>/specs/tests/<program>_tests.yaml
<DOMAIN>_REGO     := domains/<domain>/output/<program>.rego
<DOMAIN>_PACKAGE  := <domain>.<program>
<DOMAIN>_OPA_PATH := /v1/data/<domain>/<program>/decision

<domain>: <domain>-validate <domain>-transpile <domain>-test

<domain>-validate:
	python tools/validate_civil.py $(<DOMAIN>_CIVIL)

<domain>-transpile: <domain>-validate
	python tools/transpile_to_opa.py $(<DOMAIN>_CIVIL) $(<DOMAIN>_REGO) --package $(<DOMAIN>_PACKAGE)

<domain>-test:
	python tools/run_tests.py $(<DOMAIN>_TESTS) --opa-path $(<DOMAIN>_OPA_PATH)

<domain>-demo:
	bash domains/<domain>/demo/start.sh
```

Also add `.PHONY: <domain> <domain>-validate <domain>-transpile <domain>-test <domain>-demo` to the `.PHONY` line at the top of the Makefile.

Derive `<DOMAIN>_PACKAGE` from the CIVIL `module:` field (e.g., `"eligibility.wic_federal"` → package `wic.eligibility`). If ambiguous, prompt the user.

### Step 10: Transpile and Test

```bash
make <domain>-transpile && make <domain>-test
```

Or if OPA was not detected in pre-flight, run only:
```bash
python tools/transpile_to_opa.py \
    domains/<domain>/specs/<program>.civil.yaml \
    domains/<domain>/output/<program>.rego \
    --package <opa.package.name>
opa check domains/<domain>/output/<program>.rego
```

**On test failure:** Show the failing case ID(s) and actual vs. expected output. Ask the user:
- Is this a **rule error** (the CIVIL `when:` expression is wrong)?
- Is this a **test expectation error** (the test case itself has wrong expected values)?
- Is this a **transpiler bug** (the Rego generation is incorrect)?

Then loop back to the appropriate fix (Step 4, Step 7, or file a transpiler issue).

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

### Step 2: Detect Changes

```bash
# Changes committed since baseline
git diff <baseline-sha>..HEAD -- domains/<domain>/input/policy_docs/

# Untracked new files (not yet committed)
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
- Update the `git_sha` for each changed source doc
- Update `extracted_at` to today's date

### Step 8: Validate

Same retry loop as CREATE Step 6:
```bash
python tools/validate_civil.py domains/<domain>/specs/<program>.civil.yaml
```
Up to 3 auto-fix attempts, then halt with error list.

### Step 9: Identify Stale Test Cases

Examine the changed CIVIL sections to find test cases that may now use outdated values:
- If `tables:` changed → find test cases whose `inputs` contain values that were table boundaries (exact threshold amounts)
- If `constants:` changed → find test cases whose expected outcomes depend on the old constant value

List these by `case_id` with a note about which value likely changed.

### Step 10: Human Review Gate (UPDATE)

Present a **diff-style summary** (not the full ruleset):

```
Changed input docs:
  - input/policy_docs/<filename>.md

Updated CIVIL sections:
  tables.gross_income_limits:
    OLD: household_size=3 → max_gross_monthly: $2,888
    NEW: household_size=3 → max_gross_monthly: $2,945
    Source: "<quote from policy doc>"

  (repeat for each changed row/constant/rule)

Possibly stale test cases:
  - boundary_gross_001 (uses old threshold $2,888)
  - deny_gross_001 (uses old threshold $2,888)
```

Ask: "Does this update look correct? Any changes missing or incorrect?"

**On rejection:** Re-extract the specific disputed section, re-merge, re-validate, re-present. Do not proceed until confirmed.

### Step 10b: Update Naming Manifest

If any new fact or computed fields were added during this UPDATE:

1. Apply the 4-step naming algorithm (from CREATE Step 3b) to derive the canonical name for each new concept
2. Append the new entries to `domains/<domain>/specs/.naming-manifest.yaml` under the appropriate entity or `computed:` section
3. Preserve all existing manifest entries unchanged

If no naming manifest exists yet (domain was extracted before this feature was added), create it now using all current fact and computed field names from the CIVIL file.

No additional user confirmation needed; this happens automatically after the review gate passes.

### Step 11: Update Test Cases

For each stale test case identified in Step 9:
- Update threshold values in `inputs` and `expected` to match new table values
- Add any new test cases required by new rules (same 6-case coverage as CREATE)

### Step 12: Transpile and Test

Same as CREATE Step 10:
```bash
make <domain>-transpile && make <domain>-test
```
On failure → show failing cases, ask user to diagnose.

---

## Output

Files created or modified by this command:

| File | CREATE | UPDATE |
|------|--------|--------|
| `domains/<domain>/specs/<program>.civil.yaml` | Created | Updated (affected sections only) |
| `domains/<domain>/specs/.extraction-manifest.yaml` | Created | Updated |
| `domains/<domain>/specs/.naming-manifest.yaml` | Created (after Step 8b) | Updated (new fields appended) |
| `domains/<domain>/specs/tests/<program>_tests.yaml` | Created | Updated (stale cases fixed) |
| `domains/<domain>/output/<program>.rego` | Created | Regenerated |
| `Makefile` | Appended (if no target existed) | Not touched |

## Common Mistakes to Avoid

- **Don't nest inputs by entity name** in test cases — inputs are always flat key-value
- **Don't forget `default eligible := false`** — OPA boolean rules are undefined (not false) when conditions don't match; the transpiler handles this automatically for all `bool` fields in `decisions:` and `computed:`
- **Cite the actual CFR/USC section** for each rule, not just "Program Policy Manual"
- **Use `optional: true`** for fact fields that may not always be provided (e.g., `earned_income`, `shelter_costs`)
- **Distinguish earned vs. unearned income** if any deduction applies only to earned income
- **Use `computed:` for multi-step formulas** — don't reference undefined identifiers in `when:` clauses; if a value needs multiple steps to compute, define it in `computed:` and reference it by name
- **Don't use `git diff` alone for change detection** — also run `git status` to catch untracked new files not yet committed
- **Always update the manifest after extraction** — stale git SHAs in `.extraction-manifest.yaml` will cause UPDATE mode to miss real changes on the next run
