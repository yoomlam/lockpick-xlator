# Brainstorm: Confidence & Complexity Scoring for `/extract-ruleset`

**Date:** 2026-02-25
**Status:** Ready for planning
**Author:** Brainstorm session

---

## What We're Building

Annotate every extracted rule and computed field with four 1–5 scores that signal how much human attention each item deserves. Scores are written inline into the CIVIL YAML during extraction and used at the Step 8 human review gate to surface the highest-risk items first.

---

## Why This Approach

**Inline scoring during extraction** was chosen over a separate scoring pass because:
- No extra LLM call needed — scores come "for free" while the AI already has the source text and CIVIL expression in context
- Scores are committed to the CIVIL file alongside the rules they annotate, versioned together
- Step 8 can immediately use scores to prioritize without re-reading source docs

**Inline in CIVIL YAML** was chosen over a separate manifest because:
- Portable: scores travel with the rule, not in a side file
- Visible during editing: a developer inspecting the YAML sees the score at a glance
- Consistent with how `citations:` already annotates rules inline

---

## Key Decisions

### 1. Four Scores, 1–5 Scale

Each rule and computed field gets a `review:` block with four integer fields:

```yaml
review:
  extraction_fidelity: 4   # How accurately did the AI capture the policy intent?
  source_clarity: 3        # How clear/unambiguous was the source policy text?
  logic_complexity: 2      # How many conditions, boolean depth, field references?
  policy_complexity: 2     # How dense/technical is the source policy language?
```

**Scale convention:**
- `extraction_fidelity`: 1 = very uncertain / likely wrong, 5 = highly confident / direct quote match
- `source_clarity`: 1 = vague/ambiguous/contradictory, 5 = explicit and unambiguous
- `logic_complexity`: 1 = single comparison, 5 = many nested conditions + table lookups + computed deps
- `policy_complexity`: 1 = plain English, 5 = dense legalese, cross-references, exceptions-to-exceptions

### 2. Scope: Rules + Computed Fields

Scores apply to:
- Every entry in `rules:` (deny and allow rules)
- Every entry in `computed:` (derived fields)

Facts and tables are **not scored** — extraction errors there are caught by validation rather than judgment.

### 3. Schema Change

`review:` is an optional block appended after `then:` on rules and after `expr:`/`conditional:` on computed fields. The validator should accept (but not require) this block, so older CIVIL files without scores remain valid.

Example rule:
```yaml
rules:
  - id: FED-SNAP-DENY-001
    kind: deny
    priority: 1
    description: "Deny if gross income exceeds 130% FPL limit"
    when: "Household.gross_income > gross_limit"
    then:
      - add_reason:
          code: GROSS_INCOME_EXCEEDED
          message: "Gross income exceeds the 130% FPL limit"
    review:
      extraction_fidelity: 5
      source_clarity: 5
      logic_complexity: 2
      policy_complexity: 1
      notes: "Direct threshold test; well-specified in 7 CFR § 273.9(a)(1)"
```

### 4. Step 8 Review Gate Enhancement

The human review output sorts items into two buckets:

**⚠️ HIGH PRIORITY** — any item where **any score ≤ 2 or ≥ 4** (i.e., anything unusual in any dimension):
- Shown first, with source policy quote + CIVIL expression + score breakdown
- AI-written `notes:` field explains the uncertainty

**✅ LOW PRIORITY** — all four scores equal exactly 3, shown in a compact list at the end

> **Note:** Because the threshold triggers on any score ≤ 2 or ≥ 4, complex-but-correctly-extracted rules (e.g. `logic_complexity: 4`) will still be flagged HIGH PRIORITY. This is intentional — high complexity warrants a review pass even if extraction was confident.

### 5. Scoring Rubric (Prompt Instructions)

The scoring rubric will be embedded in the `extract-ruleset.md` command prompt as a reference table the AI uses when generating scores. This ensures consistent scoring across domains and extraction runs.

Draft rubric to embed:

| Score | extraction_fidelity | source_clarity | logic_complexity | policy_complexity |
|-------|--------------------|--------------------|------------------|-------------------|
| 1 | Guessed; source is silent on this | Contradictory or absent | Single boolean or comparison | Plain everyday English |
| 2 | Inferred with low confidence | Vague; multiple interpretations | 2–3 conditions, no tables | Some jargon or cross-refs |
| 3 | Reasonable translation | Reasonably clear with minor gaps | 4–6 conditions or 1 table lookup | Moderate legalese |
| 4 | Strong match to source text | Clear but uses defined terms | 7+ conditions or 2+ table lookups | Dense statutory language |
| 5 | Direct quote / explicit formula | Exact numbers/thresholds stated | Nested conditions + multiple tables | Exceptions-to-exceptions, multi-CFR |

`notes:` is always written for flagged items (any score ≤ 2 or ≥ 4). For low-priority items it is optional.

---

## Resolved Questions

| Question | Decision |
|----------|----------|
| What does "confidence" measure? | Two separate scores: extraction fidelity + source clarity |
| What does "complexity" measure? | Two separate scores: logic complexity + policy complexity |
| Where do scores live? | Inline in CIVIL YAML under `review:` block |
| Score format? | Numeric 1–5 |
| Scope? | Rules + computed fields |
| Scoring method? | Inline during extraction (no separate pass) |
| Review UX? | Sort by priority, flag low scores at Step 8 |
| Flagging threshold? | Any score ≤ 2 or ≥ 4 → HIGH PRIORITY |
| UPDATE mode behavior? | Reset scores on re-extraction (no human_reviewed flag) |
| `notes:` field? | Formal optional string in schema |

---

## Out of Scope (for now)

- A separate `/score-ruleset` command for post-hoc rescoring
- Scores on facts, tables, or constants
- Aggregate domain-level score dashboards
- CI gates that fail on low-confidence rules
