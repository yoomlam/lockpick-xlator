# Ruleset Command — Shared Content

Shared by `/extract-ruleset` and `/update-ruleset`. Read via directive at the start of each command.
Do not invoke this file directly.

---

## Pre-flight Checks 3–6

3. **Input docs present?**
   - `domains/<domain>/input/policy_docs/` missing or empty → Print: no input documents found, suggest adding `.md` files. Stop.

4. **`<filename>` valid (if given)?**
   - If `<filename>` has no `.md` extension, append it automatically (e.g., `APA` → `APA.md`)
   - Verify `domains/<domain>/input/policy_docs/<filename>` exists on disk
   - If not found: print file not found, list available `.md` files, then stop.

5. **Load `ai-guidance.yaml`**

   Check for `domains/<domain>/specs/ai-guidance.yaml`:

   **If it exists:**
   - Read the file
   - Print: `Using goal: <display_name> (source: <source_template>)`
   - Store its content for injection in Step 1

   **If it does not exist:**
   - Print: no `ai-guidance.yaml` found for this domain, suggest running `/refine-guidance <domain>` then re-running. Stop.

6. **Multiple input docs + no `<filename>`?**
   - If `domains/<domain>/input/policy_docs/` contains 2+ `.md` files and `<filename>` was **not** given:

   **If `domains/<domain>/specs/input-index.yaml` exists**, read it and display a context-rich selection prompt:
     ```
     Multiple policy documents found. Consulting specs/input-index.yaml for context...

       1. input/policy_docs/<file1>.md
          Tags: [tag1, tag2, tag3]
          <section heading> — <summary>
          <section heading> — <summary>

       2. input/policy_docs/<file2>.md
          Tags: [tag1, tag2]
          <section heading> — <summary>
          ...

       a. All files (unified corpus)

     Process which file(s)? Enter a number, comma-separated numbers, or 'a' for all:
     ```
   Show only the file's top-level H1 sections from the index (level `#` entries) to keep the prompt scannable. Omit H2/H3 entries.
   Selecting comma-separated numbers (e.g., `1,3`) reads those files as a unified corpus for the rest of the run.

   **If `input-index.yaml` does not exist**, ask the user whether to generate it first:
     ```
     specs/input-index.yaml not found. An index enables faster and richer file selection with summaries and tags.
     Run /index-inputs <domain> now? [y (recommended) / n — continue without index]:
     ```
   - **y (or Enter):** Run `/index-inputs <domain>` now (creating `specs/input-index.yaml`), then re-display the selection prompt using the rich indexed format (same as the "exists" path above).
   - **n:** Fall back to the plain filename list:
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

> **Do NOT read `tools/civil_schema.py`, `tools/transpile_to_opa.py`, or any other file in `tools/`
> before authoring any CIVIL YAML.** All syntax needed for authoring is here.

<!-- Last verified: 2026-03-04 -->

Quick reference for expression syntax and field-traceability conventions.
For full schema attribute tables, see [`core/civil-quickref.md`](civil-quickref.md).

---

### Expression Language

For `when:` conditions and `computed:` expressions:

- **Field access:** `Household.household_size`, `Applicant.age`
- **Constants:** `MIN_AGE`, `INCOME_MULTIPLIER`
- **Table lookup:** `table('gross_income_limits', Household.household_size).max_gross_monthly`
- **Boolean:** `&&`, `||`, `!`
- **Comparison:** `==`, `!=`, `<`, `<=`, `>`, `>=`
- **Arithmetic:** `+`, `-`, `*`, `/`
- **Functions:** `exists(field)`, `is_null(field)`, `between(value, min, max)`, `in(value, [a, b, c])`
- **`computed:` only:** `max(a, b)`, `min(a, b)` — computed field names as bare identifiers

**Multi-step formulas (CIVIL v2):** Use a `computed:` section for chains where each step depends on
the prior (e.g., a deduction chain). The `when:` clause references the final computed field name directly.

---

### `source:` vs `citations:` — They Are Distinct

- **`source:`** on a field, table, rule, or computed field identifies *where in the policy document
  the element was defined* — developer traceability. Example: `"7 CFR § 273.9(a) — Income and Deductions"`

- **`citations:`** inside an `add_reason` action contains the *legal authority shown to applicants
  in a denial explanation* — the statutory basis displayed in user-facing output.

A deny rule may have the same CFR section in both `source:` and `citations:` — that is expected
and not redundant. They serve different audiences.

---

## Shared Procedures

The following subroutines are referenced from the steps above. When a step says "Run **Sub-X: ...**", execute the full procedure below.

### Sub-A: Validate

```bash
python tools/validate_civil.py domains/<domain>/specs/<program>.civil.yaml
```

**On failure — retry loop (max 3 attempts):**
- Read the specific error message
- Identify the offending CIVIL section
- For more schema details, see [`core/civil-quickref.md`](civil-quickref.md)
- Re-extract or fix that section
- Re-validate

After 3 failed attempts, stop and print:
```
Validation failed after 3 attempts. Errors:
  <error list>
Fix manually, then re-run: python tools/validate_civil.py domains/<domain>/specs/<program>.civil.yaml
```

### Sub-B: Generate Computation Graph

```bash
python tools/computation_graph.py domains/<domain>/specs/<program>.civil.yaml
```

On success the tool prints both output file paths. On failure, print:
```
Warning: computation graph could not be refreshed. The draft graph at domains/<domain>/specs/<program>.graph.md may reflect pre-approval state.
```
Continue — the CIVIL file and manifests are already written. Do NOT stop the extraction.

### Sub-C: Extraction Complete Footer

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

## Common Mistakes to Avoid

- **Don't forget `default eligible := false`** — OPA boolean rules are undefined (not false) when conditions don't match; the transpiler handles this automatically for all `bool` fields in `decisions:` and `computed:`
- **Cite the actual CFR/USC section** for each rule, not just "Program Policy Manual"
- **Use `optional: true`** for fact fields that may not always be provided (e.g., `earned_income`, `shelter_costs`)
- **Distinguish earned vs. unearned income** if any deduction applies only to earned income
- **Use `computed:` for multi-step formulas** — don't reference undefined identifiers in `when:` clauses; if a value needs multiple steps to compute, define it in `computed:` and reference it by name
- **Don't use `git diff` alone for change detection** — also run `git status` to catch untracked new files not yet committed
- **Always update the manifest after extraction** — stale git SHAs in `extraction-manifest.yaml` will cause UPDATE mode to miss real changes on the next run
