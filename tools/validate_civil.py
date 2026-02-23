#!/usr/bin/env python3
"""
CIVIL DSL Structure Validator

Validates that a CIVIL YAML file conforms to the CIVIL DSL specification
as described in specs/ruleset_schema.yaml and specs/CIVIL_DSL_spec.md.

Usage:
    python tools/validate_civil.py <path_to_civil_yaml>

Exit codes:
    0 — valid
    1 — invalid (errors printed to stderr)
"""

import sys
import yaml


REQUIRED_TOP_LEVEL = ["module", "description", "version", "jurisdiction", "effective", "facts", "decisions", "rule_set", "rules"]
VALID_JURISDICTION_LEVELS = {"federal", "state", "county", "city"}
VALID_PRIMITIVE_TYPES = {"int", "float", "bool", "string", "date", "money", "list", "set", "enum"}
VALID_PRECEDENCES = {"deny_overrides_allow", "allow_overrides_deny", "first_match", "priority_order"}
VALID_RULE_KINDS = {"deny", "allow"}
VALID_COMPUTED_TYPES = {"money", "bool", "float", "int"}


def error(msg):
    print(f"ERROR: {msg}", file=sys.stderr)


def validate(path):
    errors = []

    try:
        with open(path) as f:
            doc = yaml.safe_load(f)
    except FileNotFoundError:
        error(f"File not found: {path}")
        return False
    except yaml.YAMLError as e:
        error(f"YAML parse error: {e}")
        return False

    if not isinstance(doc, dict):
        error("Top-level document must be a YAML mapping")
        return False

    # Check required top-level keys
    for key in REQUIRED_TOP_LEVEL:
        if key not in doc:
            errors.append(f"Missing required top-level key: '{key}'")

    if errors:
        for e in errors:
            error(e)
        return False

    # Validate jurisdiction
    jur = doc["jurisdiction"]
    if not isinstance(jur, dict):
        errors.append("'jurisdiction' must be a mapping")
    else:
        level = jur.get("level")
        if level not in VALID_JURISDICTION_LEVELS:
            errors.append(f"'jurisdiction.level' must be one of {sorted(VALID_JURISDICTION_LEVELS)}, got: {level!r}")
        if "country" not in jur:
            errors.append("'jurisdiction.country' is required")

    # Validate effective
    eff = doc["effective"]
    if not isinstance(eff, dict):
        errors.append("'effective' must be a mapping")
    elif "start" not in eff:
        errors.append("'effective.start' is required")

    # Validate facts
    facts = doc["facts"]
    if not isinstance(facts, dict) or len(facts) == 0:
        errors.append("'facts' must be a non-empty mapping of entity names to definitions")
    else:
        for entity_name, entity_def in facts.items():
            if not isinstance(entity_def, dict):
                errors.append(f"facts.{entity_name}: must be a mapping")
                continue
            fields = entity_def.get("fields")
            if not fields or not isinstance(fields, dict):
                errors.append(f"facts.{entity_name}: 'fields' must be a non-empty mapping")
                continue
            for field_name, field_def in fields.items():
                if not isinstance(field_def, dict):
                    errors.append(f"facts.{entity_name}.{field_name}: must be a mapping")
                    continue
                ftype = field_def.get("type")
                if not ftype:
                    errors.append(f"facts.{entity_name}.{field_name}: 'type' is required")
                elif ftype not in VALID_PRIMITIVE_TYPES:
                    # Could be a custom type — just warn, don't fail
                    pass

    # Validate decisions
    decisions = doc["decisions"]
    if not isinstance(decisions, dict) or len(decisions) == 0:
        errors.append("'decisions' must be a non-empty mapping")
    else:
        for dec_name, dec_def in decisions.items():
            if not isinstance(dec_def, dict):
                errors.append(f"decisions.{dec_name}: must be a mapping")
                continue
            if "type" not in dec_def:
                errors.append(f"decisions.{dec_name}: 'type' is required")

    # Validate computed: section (CIVIL v2 — optional)
    computed = doc.get("computed")
    if computed is not None:
        if not isinstance(computed, dict) or len(computed) == 0:
            errors.append("'computed' must be a non-empty mapping if present")
        else:
            for field_name, field_def in computed.items():
                prefix = f"computed.{field_name}"
                if not isinstance(field_def, dict):
                    errors.append(f"{prefix}: must be a mapping")
                    continue
                ftype = field_def.get("type")
                if not ftype:
                    errors.append(f"{prefix}: 'type' is required")
                elif ftype not in VALID_COMPUTED_TYPES:
                    errors.append(f"{prefix}: 'type' must be one of {sorted(VALID_COMPUTED_TYPES)}, got: {ftype!r}")
                has_expr = "expr" in field_def
                has_cond = "conditional" in field_def
                if not has_expr and not has_cond:
                    errors.append(f"{prefix}: must have either 'expr' or 'conditional'")
                elif has_expr and has_cond:
                    errors.append(f"{prefix}: 'expr' and 'conditional' are mutually exclusive")
                elif has_expr:
                    if not isinstance(field_def["expr"], str):
                        errors.append(f"{prefix}: 'expr' must be a string")
                elif has_cond:
                    cond = field_def["conditional"]
                    if not isinstance(cond, dict):
                        errors.append(f"{prefix}: 'conditional' must be a mapping")
                    else:
                        for key in ("if", "then", "else"):
                            if key not in cond:
                                errors.append(f"{prefix}.conditional: '{key}' is required")
                            elif not isinstance(cond[key], str):
                                errors.append(f"{prefix}.conditional.{key}: must be a string")

    # Validate rule_set
    rule_set = doc["rule_set"]
    if not isinstance(rule_set, dict):
        errors.append("'rule_set' must be a mapping")
    else:
        if "name" not in rule_set:
            errors.append("'rule_set.name' is required")
        prec = rule_set.get("precedence")
        if prec and prec not in VALID_PRECEDENCES:
            errors.append(f"'rule_set.precedence' must be one of {sorted(VALID_PRECEDENCES)}, got: {prec!r}")

    # Validate rules
    rules = doc["rules"]
    if not isinstance(rules, list) or len(rules) == 0:
        errors.append("'rules' must be a non-empty list")
    else:
        seen_ids = set()
        for i, rule in enumerate(rules):
            prefix = f"rules[{i}]"
            if not isinstance(rule, dict):
                errors.append(f"{prefix}: must be a mapping")
                continue

            rule_id = rule.get("id")
            if not rule_id:
                errors.append(f"{prefix}: 'id' is required")
            elif rule_id in seen_ids:
                errors.append(f"{prefix}: duplicate rule id {rule_id!r}")
            else:
                seen_ids.add(rule_id)

            kind = rule.get("kind")
            if kind not in VALID_RULE_KINDS:
                errors.append(f"{prefix} ({rule_id!r}): 'kind' must be one of {sorted(VALID_RULE_KINDS)}, got: {kind!r}")

            if "priority" not in rule:
                errors.append(f"{prefix} ({rule_id!r}): 'priority' is required")

            if "when" not in rule:
                errors.append(f"{prefix} ({rule_id!r}): 'when' is required")

            then = rule.get("then")
            if not then or not isinstance(then, list):
                errors.append(f"{prefix} ({rule_id!r}): 'then' must be a non-empty list of actions")

    if errors:
        for e in errors:
            error(e)
        print(f"\n{len(errors)} error(s) found in {path}", file=sys.stderr)
        return False

    return True


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path_to_civil_yaml>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    if validate(path):
        print(f"✓ {path} is valid CIVIL")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
