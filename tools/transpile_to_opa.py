#!/usr/bin/env python3
"""
CIVIL → OPA/Rego Transpiler

Converts any CIVIL DSL YAML module to an OPA/Rego policy file.

All domain-specific values (package name, tables, constants, computed fields,
rules, and the decision object shape) are derived from the CIVIL YAML itself.
The only external input is the OPA package name, supplied via --package.

Usage:
    python tools/transpile_to_opa.py <civil_yaml> <output_rego> --package <name>

Example:
    python tools/transpile_to_opa.py \\
        domains/snap/specs/eligibility.civil.yaml \\
        domains/snap/output/eligibility.rego \\
        --package snap.eligibility

Exit codes:
    0 — success
    1 — error (message printed to stderr)
"""

import re
import sys
import os
import argparse
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
        key_repr = f'"{key}"' if isinstance(key, str) else key
        lines.append(f"    {key_repr}: {val},")
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


def translate_expr(expr, constants=None, optional_fields=None):
    """
    Translate a CIVIL expression string to an equivalent Rego expression string.

    Transformations applied:
    1. table('name', key).col  →  name[translated_key]  (column name dropped)
    2. Entity.field             →  input.field
                                   (optional fields → object.get(input, "field", default))
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
    # Optional fields use object.get(input, "field", default) so absent values
    # don't cause undefined cascades through computed rules.
    def replace_field(m):
        field_name = m.group(2)
        if optional_fields and field_name in optional_fields:
            default = optional_fields[field_name]
            if isinstance(default, bool):
                default_str = "false" if not default else "true"
            elif isinstance(default, str):
                default_str = f'"{default}"'
            else:
                default_str = str(default)
            return f'object.get(input, "{field_name}", {default_str})'
        return f"input.{field_name}"

    result = re.sub(r"\b([A-Z][a-zA-Z]*)\.(\w+)", replace_field, result)

    # Step 3: max(a, b)  →  max([a, b])
    result = _replace_binary_fn(result, "max")

    # Step 4: min(a, b)  →  min([a, b])
    result = _replace_binary_fn(result, "min")

    # Step 5: Substitute UPPER_SNAKE_CASE constants with literal values
    if constants:
        for name, value in constants.items():
            result = re.sub(rf"\b{re.escape(name)}\b", str(value), result)

    return result


def _split_on_and(expr):
    """Split expr on && at the top level (not inside parentheses)."""
    parts = []
    depth = 0
    current = []
    i = 0
    while i < len(expr):
        if expr[i] == "(":
            depth += 1
            current.append(expr[i])
        elif expr[i] == ")":
            depth -= 1
            current.append(expr[i])
        elif expr[i:i + 2] == "&&" and depth == 0:
            parts.append("".join(current).strip())
            current = []
            i += 2
            continue
        else:
            current.append(expr[i])
        i += 1
    if current:
        parts.append("".join(current).strip())
    return [p for p in parts if p]


def translate_when_to_rego_body(when_expr, constants=None, optional_fields=None):
    """
    Translate a CIVIL when: expression to a list of Rego body condition strings.

    &&  → split into separate conditions (each on its own line)
    !x  → not x
    Entity.field → input.field (via translate_expr)
    table(...) → table_name[key] (via translate_expr)
    """
    if when_expr.strip() == "true":
        return ["true"]

    clauses = _split_on_and(when_expr)
    result = []
    for clause in clauses:
        clause = clause.strip()
        if clause.startswith("!"):
            inner = translate_expr(clause[1:].strip(), constants, optional_fields)
            result.append(f"not {inner}")
        else:
            result.append(translate_expr(clause, constants, optional_fields))
    return result


def emit_computed_section(computed_fields, constants=None, skip=None, optional_fields=None):
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
        "# COMPUTED VALUES (from CIVIL v2 computed: section)",
        "# =============================================================================",
        "",
    ]

    for field_name, field_def in computed_fields.items():
        if field_name in skip:
            lines.append(f"# {field_name}: handled elsewhere")
            lines.append("")
            continue

        ftype = field_def.get("type")
        description = field_def.get("description", "")
        has_cond = "conditional" in field_def

        if description:
            lines.append(f"# {description}")

        if has_cond:
            cond = field_def["conditional"]
            if_expr = translate_expr(cond["if"], constants, optional_fields)
            then_expr = translate_expr(cond["then"], constants, optional_fields)
            else_expr = translate_expr(cond["else"], constants, optional_fields)
            lines.append(f"{field_name} := {then_expr} if {{ {if_expr} }} else := {else_expr}")
        else:
            expr = field_def["expr"]
            rego_expr = translate_expr(expr, constants, optional_fields)
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


def transpile(doc, output_path, package):
    """
    Generic CIVIL → Rego transpiler.

    Derives all domain-specific values from the CIVIL YAML:
    - constants:  → inline-substituted in expressions
    - tables:     → emitted as Rego object literals
    - computed:   → emitted as Rego derived rules
    - rules:      → deny-kind rules emitted as denial_reasons contains ...
    - decisions:  → bool decisions derived from count(denial_reasons) == 0
    """
    tables = doc.get("tables", {})
    constants = doc.get("constants", {})
    computed = doc.get("computed", {})
    rules = doc.get("rules", [])
    decisions = doc.get("decisions", {})

    # Build optional_fields map: field_name → Rego default value for absent inputs.
    # Optional money/int/float fields default to 0; bool fields default to False.
    _type_defaults = {"money": 0, "int": 0, "float": 0, "bool": False, "string": ""}
    optional_fields = {}
    for entity_def in doc.get("facts", {}).values():
        for field_name, field_def in entity_def.get("fields", {}).items():
            if field_def.get("optional"):
                ftype = field_def.get("type", "money")
                optional_fields[field_name] = _type_defaults.get(ftype, 0)

    civil_path = sys.argv[1]

    lines = [
        f"# Generated by tools/transpile_to_opa.py from {os.path.basename(civil_path)}",
        f"# Module: {doc.get('module')}",
        f"# Description: {doc.get('description')}",
        f"# Version: {doc.get('version')}",
        f"# Effective: {doc.get('effective', {}).get('start')} – {doc.get('effective', {}).get('end')}",
        "#",
        "# DO NOT EDIT — regenerate with:",
        f"#   python tools/transpile_to_opa.py {civil_path} {output_path} --package {package}",
        "",
        f"package {package}",
        "",
        "import future.keywords.if",
        "import future.keywords.contains",
        "",
    ]

    # Tables
    if tables:
        lines += [
            "# =============================================================================",
            "# LOOKUP TABLES (from CIVIL tables:)",
            "# =============================================================================",
            "",
        ]
        for table_name, table_def in tables.items():
            desc = table_def.get("description", "")
            value_col = table_def.get("value", [None])[0]
            if not value_col:
                fail(f"Table '{table_name}' missing 'value:' column definition")
            if desc:
                lines.append(f"# {desc}")
            lines += table_to_rego_dict(table_name, table_def, value_col).split("\n")
            lines.append("")

    # Computed section
    if computed:
        lines += emit_computed_section(computed, constants=constants, optional_fields=optional_fields)

    # Deny rules → denial_reasons
    deny_rules = [r for r in rules if r.get("kind") == "deny"]
    if deny_rules:
        lines += [
            "# =============================================================================",
            "# DENY RULES (from CIVIL rules:)",
            "# =============================================================================",
            "",
        ]
        for rule in deny_rules:
            rule_id = rule.get("id", "")
            desc = rule.get("description", "")
            when = rule.get("when", "true")
            actions = rule.get("then", [])

            if desc:
                lines.append(f"# {rule_id}: {desc}")

            when_body = translate_when_to_rego_body(when, constants, optional_fields)

            for action in actions:
                if "add_reason" in action:
                    reason_def = action["add_reason"]
                    code = reason_def["code"]
                    message = reason_def["message"]
                    citations = reason_def.get("citations", [])
                    citation = citations[0]["label"] if citations else ""

                    lines.append("denial_reasons contains reason if {")
                    for cond in when_body:
                        lines.append(f"    {cond}")
                    lines.append("    reason := {")
                    lines.append(f'        "code": "{code}",')
                    lines.append(f'        "message": "{message}",')
                    if citation:
                        lines.append(f'        "citation": "{citation}"')
                    lines.append("    }")
                    lines.append("}")
                    lines.append("")

    # Eligibility decisions (bool decisions from decisions: section)
    bool_decisions = {k: v for k, v in decisions.items() if v.get("type") == "bool"}
    if bool_decisions:
        lines += [
            "# =============================================================================",
            "# ELIGIBILITY DECISION",
            "# =============================================================================",
            "",
        ]
        for field_name in bool_decisions:
            lines.append(f"default {field_name} := false")
            lines.append("")
            lines.append(f"{field_name} if {{")
            lines.append("    count(denial_reasons) == 0")
            lines.append("}")
            lines.append("")

    # Structured decision object
    lines += [
        "# =============================================================================",
        "# STRUCTURED DECISION OBJECT",
        "# =============================================================================",
        "",
        "decision := {",
    ]
    for field_name, field_def in decisions.items():
        ftype = field_def.get("type")
        if ftype == "bool":
            lines.append(f'    "eligible": {field_name},')
        elif ftype == "list":
            lines.append(f'    "denial_reasons": [r | r := denial_reasons[_]],')
    if computed:
        computed_keys = list(computed.keys())
        lines.append('    "computed": {')
        for i, cfield in enumerate(computed_keys):
            comma = "," if i < len(computed_keys) - 1 else ""
            lines.append(f'        "{cfield}": {cfield}{comma}')
        lines.append("    }")
    lines.append("}")

    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"✓ Transpiled to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Transpile a CIVIL DSL YAML module to OPA/Rego"
    )
    parser.add_argument("civil_yaml", help="Path to the CIVIL YAML module")
    parser.add_argument("output_rego", help="Path for the generated Rego file")
    parser.add_argument(
        "--package",
        required=True,
        help="OPA package name, e.g. snap.eligibility",
    )
    args = parser.parse_args()

    validate_before_transpile(args.civil_yaml)
    doc = load_civil(args.civil_yaml)
    transpile(doc, args.output_rego, package=args.package)


if __name__ == "__main__":
    main()
