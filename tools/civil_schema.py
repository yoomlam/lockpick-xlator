"""
CIVIL DSL — Pydantic v2 schema models.

This file is the single source of truth for the CIVIL DSL structure and
field-level documentation. Run as a script to regenerate specs/ruleset.schema.json:

    python tools/civil_schema.py

Expression language reference (for 'when:' conditions and 'expr:' strings):
  Literals:     42, 3.14, "text", true, false, date("2026-01-01")
  Field access: Applicant.age, CONSTANT_NAME
  Boolean:      &&  ||  !
  Comparison:   ==  !=  <  <=  >  >=
  Arithmetic:   +  -  *  /
  Functions:    table(name, key), in(value, [a,b,c]), exists(f), is_null(f),
                between(value, min, max)
  computed: only: max(a, b), min(a, b)

See specs/CIVIL_DSL_spec.md for full specification and design rationale.
"""

# IMPORTANT: If you change types, field attributes, or add new model classes,
# update specs/civil-quickref.md to match and refresh its "last verified" date.
# Also update specs/CIVIL_DSL_spec.md if the change affects the DSL design.

from __future__ import annotations

import sys
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

ScoreField = Annotated[int, Field(ge=1, le=5)]

PRIMITIVE_TYPES = {"int", "float", "bool", "string", "date", "money", "list", "set", "enum"}


# ---------------------------------------------------------------------------
# Leaf models
# ---------------------------------------------------------------------------


class ReviewBlock(BaseModel):
    """Inline extraction quality scores. All four score fields are required when present.

    Score scale: 1 = very low, 3 = moderate, 5 = very high.
    Notes are required for any score ≤ 2 or ≥ 4. Scores have no effect on
    transpilation or OPA evaluation — they exist only for human review.
    """

    extraction_fidelity: ScoreField = Field(
        description=(
            "1–5: how accurately the AI captured the policy intent. "
            "1 = guessed (source is silent), 3 = reasonable translation, "
            "5 = direct quote or explicit formula."
        )
    )
    source_clarity: ScoreField = Field(
        description=(
            "1–5: how clear and unambiguous the source policy text was. "
            "1 = contradictory or absent, 3 = reasonably clear with minor ambiguity, "
            "5 = exact thresholds or formulas stated verbatim."
        )
    )
    logic_complexity: ScoreField = Field(
        description=(
            "1–5: number of conditions, boolean depth, and table lookups. "
            "1 = single boolean or comparison, 3 = 4–6 conditions or 1 table lookup, "
            "5 = 10+ conditions, nested booleans, multiple tables."
        )
    )
    policy_complexity: ScoreField = Field(
        description=(
            "1–5: density of legalese, cross-references, and exceptions. "
            "1 = plain everyday English, 3 = moderate legalese or defined terms, "
            "5 = dense statutory language, exceptions-to-exceptions, multi-CFR cross-refs."
        )
    )
    notes: str | None = Field(
        default=None,
        description=(
            "Explanation for flagged items. Required for any score ≤ 2 or ≥ 4. "
            "May be omitted if all four scores are 3."
        ),
    )


class Citation(BaseModel):
    """A legal or policy citation supporting a rule or reason."""

    label: str = Field(description="Citation label, e.g. '42 USC § 1437a' or '7 CFR § 273.9'.")
    url: str | None = Field(default=None, description="URL to the cited document (optional).")
    excerpt: str | None = Field(
        default=None, description="Brief excerpt from the cited text (optional)."
    )


class Conditional(BaseModel):
    """An if/then/else expression for computed fields.

    Use instead of 'expr' when the computed value depends on a boolean condition.
    All three branches (if, then, else) are required.
    """

    model_config = ConfigDict(populate_by_name=True)
    if_: str = Field(alias="if", description="Boolean CIVIL expression — condition to test.")
    then: str = Field(description="CIVIL expression for the true branch.")
    else_: str = Field(alias="else", description="CIVIL expression for the false branch.")


# ---------------------------------------------------------------------------
# Facts, decisions, tables, constants
# ---------------------------------------------------------------------------


class FactField(BaseModel):
    """A single typed field within a fact entity."""

    type: str = Field(
        description=(
            "Data type. Primitives: int, float, bool, string, date, money. "
            "Complex: list, set, enum. Custom: any type defined in the 'types' section."
        )
    )
    description: str | None = Field(default=None, description="Human-readable field description.")
    source: str | None = Field(
        default=None,
        description=(
            "Policy document location where this field is defined, "
            "e.g. '7 CFR § 273.9(a) — Income and Deductions'."
        ),
    )
    optional: bool = Field(
        default=False,
        description="Whether this field may be absent in input (default: false = always required).",
    )
    currency: str | None = Field(
        default=None, description="Currency code for money type, e.g. 'USD'."
    )
    values: list[str] | None = Field(
        default=None, description="Valid values for enum type, e.g. ['single', 'mfj', 'mfs']."
    )

    @field_validator("type")
    @classmethod
    def warn_unknown_type(cls, v: str) -> str:
        if v not in PRIMITIVE_TYPES:
            print(
                f"WARNING: unknown fact field type '{v}' (may be a custom type)",
                file=sys.stderr,
            )
        return v


class FactEntity(BaseModel):
    """An input entity (e.g., Household, Applicant) with named typed fields.

    Entity names use PascalCase. Field names use snake_case.
    """

    description: str | None = Field(default=None, description="Description of this entity.")
    fields: dict[str, FactField] = Field(
        description="Named fields of this entity (snake_case → field definition)."
    )


class DecisionField(BaseModel):
    """An output decision value produced by rule evaluation."""

    type: str = Field(
        description="Output type, e.g. 'bool', 'list', 'money', 'set', 'string'."
    )
    default: Any = Field(
        default=None,
        description="Default value when no rules fire, e.g. false for bool or [] for list.",
    )
    description: str | None = Field(
        default=None, description="Description of what this decision represents."
    )
    item: str | None = Field(
        default=None,
        description="Item type for list/set decisions, e.g. 'Reason' or 'string'.",
    )


class TableDef(BaseModel):
    """A lookup table mapping key values to output values.

    Tables are referenced in CIVIL expressions as:
      table('table_name', key_expr).value_column
    """

    description: str | None = Field(
        default=None, description="Description of what this table represents."
    )
    source: str | None = Field(
        default=None,
        description=(
            "Policy document location where this table is defined, "
            "e.g. '7 CFR § 273.9(a)(1) — Gross Income Limits Table'."
        ),
    )
    key: list[str] = Field(description="Key column name(s) used for lookup.")
    value: list[str] = Field(description="Value column name(s) returned by lookup.")
    rows: list[dict[str, Any]] = Field(description="Table data rows as a list of dicts.")


# ---------------------------------------------------------------------------
# Computed fields
# ---------------------------------------------------------------------------


class ComputedField(BaseModel):
    """A derived intermediate value (CIVIL v2).

    Computed fields are NOT primary decision outputs — they are intermediate values
    available to rules (in 'when:' expressions) and to other computed fields.
    Define in dependency order: no forward references allowed.

    Each field must have exactly one of 'expr' or 'conditional'.
    """

    type: Literal["money", "bool", "float", "int"] = Field(
        description="Value type: money, bool, float, or int."
    )
    currency: str | None = Field(
        default=None, description="Currency code for money type, e.g. 'USD'."
    )
    description: str | None = Field(
        default=None,
        description="Human-readable explanation of what this field computes.",
    )
    source: str | None = Field(
        default=None,
        description=(
            "Policy document location where this computed field is derived from, "
            "e.g. '7 CFR § 273.9(d)(1) — Earned Income Deduction'."
        ),
    )
    expr: str | None = Field(
        default=None,
        description=(
            "CIVIL expression producing the computed value. "
            "Mutually exclusive with 'conditional'. "
            "May reference fact fields, constants, other computed fields, and table lookups. "
            "In computed: context, max(a, b) and min(a, b) are also available."
        ),
    )
    conditional: Conditional | None = Field(
        default=None,
        description=(
            "If/then/else branch for conditional computed values. "
            "Mutually exclusive with 'expr'."
        ),
    )
    review: ReviewBlock | None = Field(
        default=None, description="Extraction quality scores for this computed field."
    )

    @model_validator(mode="after")
    def expr_xor_conditional(self) -> "ComputedField":
        has_expr = self.expr is not None
        has_cond = self.conditional is not None
        if has_expr == has_cond:  # both or neither
            raise ValueError("ComputedField must have exactly one of 'expr' or 'conditional'")
        return self


# ---------------------------------------------------------------------------
# Rules and actions
# ---------------------------------------------------------------------------


class AddReasonContent(BaseModel):
    """Content for an add_reason action."""

    code: str = Field(description="Machine-readable reason code (UPPER_SNAKE_CASE).")
    message: str = Field(description="Human-readable explanation shown to caseworkers.")
    citations: list[Citation] = Field(
        default=[], description="Legal citations supporting this denial reason."
    )


class AddInstructionContent(BaseModel):
    """Content for an add_instruction action."""

    step: str = Field(description="Step identifier or label.")
    message: str = Field(description="Instruction text.")
    citations: list[Citation] = Field(
        default=[], description="Supporting citations for this instruction."
    )


class Action(BaseModel):
    """A single action in a rule's 'then' block.

    Must have exactly one action-type key. Available actions:
      set             — set a decision output to a value
      add_reason      — append a Reason to a list-typed decision
      add_instruction — append an Instruction to a list-typed decision
      add_to_set      — add a value to a set-typed decision
      append_to_list  — append a value to a list-typed decision
    """

    add_reason: AddReasonContent | None = Field(
        default=None,
        description="Append a Reason to a list-typed decision (typically 'denial_reasons').",
    )
    set: dict[str, Any] | None = Field(
        default=None,
        description="Set a decision output to a specific value, e.g. {eligible: true}.",
    )
    add_instruction: AddInstructionContent | None = Field(
        default=None,
        description="Append an Instruction to a list-typed decision.",
    )
    add_to_set: dict[str, Any] | None = Field(
        default=None, description="Add a value to a set-typed decision."
    )
    append_to_list: dict[str, Any] | None = Field(
        default=None, description="Append a value to a list-typed decision."
    )

    @model_validator(mode="before")
    @classmethod
    def one_action_type(cls, data: Any) -> Any:
        if isinstance(data, dict):
            known = {"add_reason", "set", "add_instruction", "add_to_set", "append_to_list"}
            present = [k for k in data if k in known]
            if len(present) != 1:
                raise ValueError(
                    f"Each 'then' action must have exactly one type; got {present}"
                )
        return data


class Rule(BaseModel):
    """A single deny or allow rule.

    Rules are evaluated according to the rule_set.precedence strategy.
    The 'when' condition is a boolean CIVIL expression; if it evaluates to true,
    all 'then' actions are executed.
    """

    id: str = Field(
        description=(
            "Unique rule identifier. Recommended format: "
            "'<JURISDICTION>-<TOPIC>-<KIND>-<SEQ>', e.g. 'FED-SNAP-DENY-001'."
        )
    )
    kind: Literal["deny", "allow"] = Field(
        description="Rule type: 'deny' to deny eligibility, 'allow' to grant it."
    )
    priority: int = Field(
        description=(
            "Evaluation priority — lower number = higher priority. "
            "Allow rules typically use priority 100+."
        )
    )
    when: str = Field(
        description=(
            "Boolean CIVIL expression — the condition under which this rule fires. "
            "May reference fact fields (Household.field), constants, and computed fields. "
            "See module docstring for expression language reference."
        )
    )
    then: list[Action] = Field(
        description="Actions to take when the 'when' condition is true. Must be non-empty."
    )
    description: str | None = Field(
        default=None, description="Optional human-readable description of this rule."
    )
    source: str | None = Field(
        default=None,
        description=(
            "Policy document location where this rule is defined, "
            "e.g. '7 CFR § 273.9(a)(1) — Gross Income Test'."
        ),
    )
    review: ReviewBlock | None = Field(
        default=None, description="Extraction quality scores for this rule."
    )


# ---------------------------------------------------------------------------
# Top-level module
# ---------------------------------------------------------------------------


class Jurisdiction(BaseModel):
    """Jurisdiction metadata for a CIVIL module."""

    level: Literal["federal", "state", "county", "city"] = Field(
        description="Jurisdiction level: federal, state, county, or city."
    )
    country: str = Field(description="ISO country code, e.g. 'US'.")
    state: str | None = Field(default=None, description="State/province code (optional).")
    county: str | None = Field(default=None, description="County name (optional).")
    city: str | None = Field(default=None, description="City name (optional).")


class Effective(BaseModel):
    """Effective date range for this ruleset."""

    start: Any = Field(description="Effective start date (YYYY-MM-DD).")
    end: Any = Field(
        default=None,
        description="Effective end date (YYYY-MM-DD) — optional for time-bounded policies.",
    )


class RuleSet(BaseModel):
    """Rule set configuration controlling evaluation strategy."""

    name: str = Field(description="Rule set identifier.")
    precedence: (
        Literal["deny_overrides_allow", "allow_overrides_deny", "first_match", "priority_order"]
        | None
    ) = Field(
        default=None,
        description=(
            "Evaluation strategy. "
            "deny_overrides_allow: any deny wins; "
            "allow_overrides_deny: any allow wins; "
            "first_match: first matching rule wins; "
            "priority_order: evaluate in priority order."
        ),
    )
    description: str | None = Field(
        default=None, description="Description of this rule set."
    )


class CivilModule(BaseModel):
    """Top-level CIVIL DSL module. One file per program or policy area.

    CIVIL (Civic Instructions & Validations Intermediate Language) is designed
    for government policy/regulation logic with full traceability to source law.

    Required sections: module, description, version, jurisdiction, effective,
                       facts, decisions, rule_set, rules.
    Optional sections: tables, constants, computed, types.
    """

    module: str = Field(
        description="Unique module identifier, e.g. 'eligibility.housing_assistance'."
    )
    description: str = Field(description="Human-readable description of the module.")
    version: str = Field(description="Version identifier, e.g. '2026Q1'.")
    jurisdiction: Jurisdiction = Field(description="Jurisdiction metadata.")
    effective: Effective = Field(description="Effective date range for this ruleset.")
    facts: dict[str, FactEntity] = Field(
        description=(
            "Input fact types. Keys are entity names (PascalCase), "
            "values are entity definitions with typed fields."
        )
    )
    decisions: dict[str, DecisionField] = Field(
        description=(
            "Output decision values produced by rule evaluation. "
            "Common pattern: eligible (bool) + denial_reasons (list[Reason])."
        )
    )
    rule_set: RuleSet = Field(description="Rule set configuration.")
    rules: list[Rule] = Field(description="Ordered list of allow/deny rules.")
    # optional sections
    tables: dict[str, TableDef] | None = Field(
        default=None,
        description=(
            "Lookup tables for threshold values, e.g. income limits by household size. "
            "Reference in expressions as: table('table_name', key_expr).value_column"
        ),
    )
    constants: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Named constant values (UPPER_SNAKE_CASE). "
            "Examples: MIN_AGE, FEDERAL_POVERTY_LEVEL, EARNED_INCOME_RATE."
        ),
    )
    computed: dict[str, ComputedField] | None = Field(
        default=None,
        description=(
            "Derived intermediate values (CIVIL v2). Use for multi-step formulas "
            "where each step depends on prior results (e.g., a deduction chain). "
            "Define in dependency order — no forward references. "
            "Computed field names are available as bare identifiers in 'when:' clauses."
        ),
    )
    types: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Custom type definitions (PascalCase). Built-in types Reason, Citation, "
            "and Instruction are available without definition."
        ),
    )

    @model_validator(mode="after")
    def unique_rule_ids(self) -> "CivilModule":
        seen: set[str] = set()
        for rule in self.rules:
            if rule.id in seen:
                raise ValueError(f"Duplicate rule id: '{rule.id}'")
            seen.add(rule.id)
        return self


# ---------------------------------------------------------------------------
# JSON Schema generation
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import pathlib

    schema = CivilModule.model_json_schema()
    out = pathlib.Path("specs/ruleset.schema.json")
    out.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"Generated {out}")
