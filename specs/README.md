# Specifications

This directory contains shared specification files that are used by domain-specific specifications extracted from the input docs and code from the legacy system.
These specifications are used to generate the output ruleset and code for the modernized system.

The specifications capture government policies and statutes, including:
- eligibility rules
- government benefits
- tax regulations
- etc.

In addition to decision logic, the specifications cite source documents/code for traceability.


## CIVIL DSL (Civic Instructions & Validations Intermediate Language)

The [CIVIL_DSL_spec.md](CIVIL_DSL_spec.md) documents **CIVIL**, our policy specification DSL designed for government policy/regulation logic.

### Key Features

- **Multi-jurisdiction support**: Federal → state → city layering with overlays
- **Version management**: Effective date ranges and quarterly updates
- **Explainability**: Every decision includes reasons with legal citations
- **Transpiler-friendly**: Intermediate representation for multiple rule engines
- **Policy composition**: Overlay system for jurisdiction-specific rules
- **Deterministic evaluation**: Pure function from facts to decisions

### Use Cases

- Government benefit eligibility rules
- Tax filing requirements and instructions
- Complex multi-jurisdiction policy scenarios
- Rules requiring full audit trails with legal citations
- Policies that need compilation to multiple rule engines (OPA/Rego, DMN, Drools)

## Testing

All rule specifications should have corresponding test suites:
- Test format documentation: [tests/README.md](tests/README.md)
- Example test suite: [tests/example_benefit_tests.yaml](tests/example_benefit_tests.yaml)
- Tests should cover:
  - Happy path scenarios
  - Edge cases and boundary conditions
  - Invalid inputs
  - Policy reference validation

## Getting Started

1. **To define a new ruleset:** Use the CIVIL DSL format documented in [CIVIL_DSL_spec.md](CIVIL_DSL_spec.md)
2. **For schema reference:** See [ruleset_schema.yaml](ruleset_schema.yaml) for CIVIL DSL structure
3. **For examples:** See [ruleset/example_benefit.yaml](ruleset/example_benefit.yaml)
4. **To write tests:** Follow the format in [tests/README.md](tests/README.md)

## Principles

Across both formats, we maintain these core principles:

1. **Deterministic**: Same inputs + rules → same outputs
2. **Traceable**: Every decision has clear reasoning
3. **Cited**: Rules reference authoritative policy sources
4. **Versioned**: Rules have effective dates and version tracking
5. **Testable**: All rules have comprehensive test coverage
6. **Explainable**: Decisions can be explained to end users

## When adding new specifications

1. Use the CIVIL DSL format for all rulesets
2. Always include corresponding test cases
3. Document policy references and citations
4. Include effective dates and version information
5. For multi-jurisdiction rules, use the overlay system
6. Ensure rules are deterministic and explainable
