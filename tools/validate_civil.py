#!/usr/bin/env python3
"""
CIVIL DSL Structure Validator

Validates that a CIVIL YAML file conforms to the CIVIL DSL specification.
Schema is defined in tools/civil_schema.py (Pydantic v2 models).

Usage:
    python tools/validate_civil.py <path_to_civil_yaml>

Exit codes:
    0 — valid
    1 — invalid (errors printed to stderr)
"""

import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from civil_schema import CivilModule  # noqa: E402

from pydantic import ValidationError  # noqa: E402


def validate(path: str) -> bool:
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"ERROR: File not found: {path}", file=sys.stderr)
        return False
    except yaml.YAMLError as e:
        print(f"ERROR: YAML parse error: {e}", file=sys.stderr)
        return False

    try:
        CivilModule.model_validate(data)
        return True
    except ValidationError as e:
        for err in e.errors():
            loc = " → ".join(str(x) for x in err["loc"]) if err["loc"] else "(root)"
            print(f"ERROR: {loc}: {err['msg']}", file=sys.stderr)
        print(f"\n{e.error_count()} error(s) found in {path}", file=sys.stderr)
        return False


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path_to_civil_yaml>", file=sys.stderr)
        sys.exit(1)

    if validate(sys.argv[1]):
        print(f"✓ {sys.argv[1]} is valid CIVIL")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
