#!/usr/bin/env python3
"""
CIVIL → OPA/Rego Transpiler

Converts a CIVIL DSL YAML module to an OPA/Rego policy file.

This transpiler handles CIVIL modules that follow the SNAP eligibility pattern:
income threshold tables, deduction chains, and gross/net income tests.

CIVIL v2 support: the `computed:` section expresses derived values with CIVIL
expressions, which are translated to Rego derived rules generically.

Usage:
    python tools/transpile_to_opa.py <civil_yaml> <output_rego>

Example:
    python tools/transpile_to_opa.py specs/ruleset/snap_eligibility.civil.yaml output/ruleset/snap_eligibility.rego

Exit codes:
    0 — success
    1 — error (message printed to stderr)
"""

import re
import sys
import os
import yaml


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def load_civil(path):
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        fail(f"File not found: {path}")
    except yaml.YAMLError as e:
        fail(f"YAML parse error: {e}")


def validate_before_transpile(path):
    """Run the CIVIL validator first. Exits 1 if invalid."""
    validator = os.path.join(os.path.dirname(__file__), "validate_civil.py")
    ret = os.system(f"python {validator} {path} > /dev/null 2>&1")
    if ret != 0:
        # Re-run with output visible
        os.system(f"python {validator} {path}")
        fail(f"CIVIL validation failed for {path}. Fix errors above before transpiling.")


def table_to_rego_dict(table_name, table_def, value_col):
    """Emit a Rego object literal from a CIVIL table."""
    rows = table_def.get("rows", [])
    key_col = table_def.get("key", [])[0]
    lines = [f"{table_name} := {{"]
    for row in rows:
        key = row[key_col]
        val = row[value_col]
        lines.append(f"    {key}: {val},")
    lines.append("}")
    return "\n".join(lines)


def _split_top_level_comma(args_str):
    """Split 'a, b' on the first comma not inside nested parentheses."""
    depth = 0
    for i, ch in enumerate(args_str):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            return args_str[:i].strip(), args_str[i + 1:].strip()
    raise ValueError(f"No top-level comma found in: {args_str!r}")


def _replace_binary_fn(expr, fn_name):
    """Replace fn_name(a, b) with fn_name([a, b]) using balanced-paren parsing."""
    result = []
    i = 0
    pattern = fn_name + "("
    while i < len(expr):
        idx = expr.find(pattern, i)
        if idx == -1:
            result.append(expr[i:])
            break
        result.append(expr[i:idx])
        start = idx + len(pattern)
        depth = 1
        j = start
        while j < len(expr) and depth > 0:
            if expr[j] == "(":
                depth += 1
            elif expr[j] == ")":
                depth -= 1
            j += 1
        args_str = expr[start:j - 1]
        a, b = _split_top_level_comma(args_str)
        result.append(f"{fn_name}([{a}, {b}])")
        i = j
    return "".join(result)


def translate_expr(expr, constants=None):
    """
    Translate a CIVIL expression string to an equivalent Rego expression string.

    Transformations applied:
    1. table('name', key).col  →  name[translated_key]  (column name dropped)
    2. Entity.field             →  input.field
    3. max(a, b)                →  max([a, b])
    4. min(a, b)                →  min([a, b])
    5. CONSTANT_NAME            →  literal value (inline substitution)
    """
    result = expr

    # Step 1: table('name', key_expr).col  →  name[key_translated]
    def replace_table(m):
        tname = m.group(1)
        key_expr = m.group(2).strip()
        # Translate the key expression (handles Entity.field inside table args)
        translated_key = re.sub(r"\b([A-Z][a-zA-Z]*)\.(\w+)", r"input.\2", key_expr)
        return f"{tname}[{translated_key}]"

    result = re.sub(
        r"table\('(\w+)',\s*([^)]+)\)\.\w+",
        replace_table,
        result
    )

    # Step 2: Entity.field  →  input.field
    result = re.sub(r"\b([A-Z][a-zA-Z]*)\.(\w+)", r"input.\2", result)

    # Step 3: max(a, b)  →  max([a, b])
    result = _replace_binary_fn(result, "max")

    # Step 4: min(a, b)  →  min([a, b])
    result = _replace_binary_fn(result, "min")

    # Step 5: Substitute UPPER_SNAKE_CASE constants with literal values
    if constants:
        for name, value in constants.items():
            result = re.sub(rf"\b{re.escape(name)}\b", str(value), result)

    return result


def emit_computed_section(computed_fields, constants=None, skip=None):
    """
    Emit Rego rules for all fields in the computed: section.

    - expr (non-bool):  field_name := <translated_expr>
    - expr (bool):      default field_name := false
                        field_name if { <translated_expr> }
    - conditional:      field_name := <then> if { <if> } else := <else>

    Fields in `skip` are noted with a comment and skipped (already emitted elsewhere).
    Returns a list of Rego source lines.
    """
    skip = skip or set()
    lines = [
        "# =============================================================================",
        "# DEDUCTION CHAIN (from CIVIL v2 computed: section)",
        "# =============================================================================",
        "",
    ]

    for field_name, field_def in computed_fields.items():
        if field_name in skip:
            lines.append(f"# {field_name}: handled by SNAP-specific lookup rule above")
            lines.append("")
            continue

        ftype = field_def.get("type")
        description = field_def.get("description", "")
        has_cond = "conditional" in field_def

        if description:
            lines.append(f"# {description}")

        if has_cond:
            cond = field_def["conditional"]
            if_expr = translate_expr(cond["if"], constants)
            then_expr = translate_expr(cond["then"], constants)
            else_expr = translate_expr(cond["else"], constants)
            lines.append(f"{field_name} := {then_expr} if {{ {if_expr} }} else := {else_expr}")
        else:
            expr = field_def["expr"]
            rego_expr = translate_expr(expr, constants)
            if ftype == "bool":
                # Rego rule bodies don't support || — split OR clauses into multiple rules
                or_clauses = [c.strip() for c in rego_expr.split("||")]
                lines.append(f"default {field_name} := false")
                for clause in or_clauses:
                    lines.append(f"{field_name} if {{ {clause} }}")
            else:
                lines.append(f"{field_name} := {rego_expr}")

        lines.append("")

    return lines


def transpile_snap(doc, output_path):
    """
    Transpile the SNAP CIVIL module to OPA/Rego.

    CIVIL v2: the `computed:` section defines the deduction chain. The transpiler
    emits those fields generically via emit_computed_section(). SNAP-specific
    threshold lookup rules (with size 9+ fallbacks) are still emitted here.
    """
    tables = doc.get("tables", {})
    constants = doc.get("constants", {})

    # Extract table data
    gross_limits = tables.get("gross_income_limits", {})
    net_limits = tables.get("net_income_limits", {})
    std_deds = tables.get("standard_deductions", {})

    gross_rows = {r["household_size"]: r["max_gross_monthly"] for r in gross_limits.get("rows", [])}
    net_rows = {r["household_size"]: r["max_net_monthly"] for r in net_limits.get("rows", [])}
    std_rows = {r["household_size"]: r["deduction_amount"] for r in std_deds.get("rows", [])}

    # Extract constants
    shelter_cap = constants.get("SHELTER_DEDUCTION_CAP", 744)
    earned_rate = constants.get("EARNED_INCOME_DEDUCTION_RATE", 0.20)
    shelter_rate = constants.get("SHELTER_EXCESS_THRESHOLD_RATE", 0.50)
    gross_incr = constants.get("GROSS_INCOME_INCREMENT_9PLUS", 596)
    net_incr = constants.get("NET_INCOME_INCREMENT_9PLUS", 459)

    # Build Rego
    lines = [
        f"# Generated by tools/transpile_to_opa.py from {os.path.basename(sys.argv[1])}",
        f"# Module: {doc.get('module')}",
        f"# Description: {doc.get('description')}",
        f"# Version: {doc.get('version')}",
        f"# Effective: {doc.get('effective', {}).get('start')} – {doc.get('effective', {}).get('end')}",
        "#",
        "# DO NOT EDIT — regenerate with:",
        "#   python tools/transpile_to_opa.py specs/ruleset/snap_eligibility.civil.yaml output/ruleset/snap_eligibility.rego",
        "",
        "package snap.eligibility",
        "",
        "import future.keywords.if",
        "import future.keywords.contains",
        "",
        "# =============================================================================",
        "# FY2026 INCOME THRESHOLDS (from CIVIL tables)",
        "# =============================================================================",
        "",
    ]

    # Gross income limits dict
    lines.append("# Gross income limits: 130% FPL monthly (7 CFR § 273.9(a)(1))")
    lines.append("gross_income_limits := {")
    for size in sorted(gross_rows):
        lines.append(f"    {size}: {gross_rows[size]},")
    lines.append("}")
    lines.append("")

    # Net income limits dict
    lines.append("# Net income limits: 100% FPL monthly (7 CFR § 273.9(a)(2))")
    lines.append("net_income_limits := {")
    for size in sorted(net_rows):
        lines.append(f"    {size}: {net_rows[size]},")
    lines.append("}")
    lines.append("")

    # Standard deductions dict
    lines.append("# Standard deductions by household size (7 CFR § 273.9(c))")
    lines.append("standard_deductions := {")
    for size in sorted(std_rows):
        lines.append(f"    {size}: {std_rows[size]},")
    lines.append("}")
    lines.append("")

    lines += [
        "# =============================================================================",
        "# INCOME THRESHOLD LOOKUPS (with size 9+ formula fallback)",
        "# =============================================================================",
        "",
        "# Gross income limit for this household",
        "gross_limit := gross_income_limits[input.household_size] if {",
        "    input.household_size <= 8",
        f"}} else := {gross_rows[8]} + (input.household_size - 8) * {gross_incr}",
        "",
        "# Net income limit for this household",
        "net_limit := net_income_limits[input.household_size] if {",
        "    input.household_size <= 8",
        f"}} else := {net_rows[8]} + (input.household_size - 8) * {net_incr}",
        "",
        "# Standard deduction for this household (size 7+ same as size 6)",
        "standard_deduction := standard_deductions[input.household_size] if {",
        "    input.household_size <= 6",
        f"}} else := {std_rows[6]}",
        "",
    ]

    # CIVIL v2: emit computed: section generically
    computed = doc.get("computed", {})
    if not computed:
        fail("No computed: section found in CIVIL module. Expected CIVIL v2 with computed: fields.")
    # standard_deduction is already emitted above with size 7+ fallback; skip it
    lines += emit_computed_section(computed, constants=constants, skip={"standard_deduction"})

    lines += [
        "# =============================================================================",
        "# INCOME TESTS",
        "# =============================================================================",
        "",
        "# Gross income test: non-exempt households must pass",
        "# default false: OPA boolean rules are undefined (not false) when conditions don't match",
        "default passes_gross_test := false",
        "passes_gross_test if { is_exempt_household }",
        "passes_gross_test if {",
        "    not is_exempt_household",
        "    input.gross_monthly_income <= gross_limit",
        "}",
        "",
        "# Net income test: all households must pass",
        "default passes_net_test := false",
        "passes_net_test if { net_income <= net_limit }",
        "",
        "# =============================================================================",
        "# ELIGIBILITY DECISION",
        "# =============================================================================",
        "",
        "default eligible := false",
        "",
        "eligible if {",
        "    passes_gross_test",
        "    passes_net_test",
        "}",
        "",
        "# denial_reasons: collected from failing tests",
        "denial_reasons contains reason if {",
        "    not passes_gross_test",
        '    reason := {',
        '        "code": "GROSS_INCOME_EXCEEDS_LIMIT",',
        '        "message": "Gross monthly income exceeds 130% of the Federal Poverty Level for this household size",',
        '        "citation": "7 CFR § 273.9(a)(1)"',
        "    }",
        "}",
        "",
        "denial_reasons contains reason if {",
        "    passes_gross_test",
        "    not passes_net_test",
        '    reason := {',
        '        "code": "NET_INCOME_EXCEEDS_LIMIT",',
        '        "message": "Net monthly income after allowable deductions exceeds 100% of the Federal Poverty Level for this household size",',
        '        "citation": "7 CFR § 273.9(a)(2)"',
        "    }",
        "}",
        "",
        "# =============================================================================",
        "# STRUCTURED DECISION OBJECT",
        "# =============================================================================",
        "",
        "decision := {",
        '    "eligible": eligible,',
        '    "denial_reasons": [r | r := denial_reasons[_]],',
        '    "computed": {',
        '        "gross_monthly_income": input.gross_monthly_income,',
        '        "gross_limit": gross_limit,',
        '        "passes_gross_test": passes_gross_test,',
        '        "earned_income_deduction": earned_income_deduction,',
        '        "standard_deduction": standard_deduction,',
        '        "dependent_care_deduction": dependent_care_deduction,',
        '        "shelter_deduction": shelter_deduction,',
        '        "net_income": net_income,',
        '        "net_limit": net_limit,',
        '        "passes_net_test": passes_net_test',
        "    }",
        "}",
    ]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"✓ Transpiled to {output_path}")


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <civil_yaml> <output_rego>", file=sys.stderr)
        sys.exit(1)

    civil_path = sys.argv[1]
    output_path = sys.argv[2]

    validate_before_transpile(civil_path)
    doc = load_civil(civil_path)
    transpile_snap(doc, output_path)


if __name__ == "__main__":
    main()
