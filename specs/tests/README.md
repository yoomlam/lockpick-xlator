# Ruleset Test Specifications

Test cases to validate that policy rulesets produce correct, deterministic results.

## Purpose

Every ruleset specification must have corresponding test cases to ensure:
1. **Correctness**: Rules produce expected outputs for known inputs
2. **Completeness**: All rule paths are exercised
3. **Regression Prevention**: Changes don't break existing behavior
4. **Documentation**: Tests serve as executable examples

## Test File Structure

Each test file should:
- Correspond to a specific ruleset specification file
- Be named `<ruleset_name>_tests.yaml`
- Include comprehensive test coverage

### Required Elements

```yaml
test_suite:
  spec: "example_benefit.yaml"          # Reference to ruleset file
  description: "Test suite description" # What is being tested
  version: "1.0"                        # Test suite version

tests:
  - case_id: "test_001"                 # Unique test identifier
    description: "Test scenario description"
    inputs:                             # Input facts/data
      age: 25
      monthly_income: 1500
      household_size: 1
    expected:                           # Expected outputs
      eligible: true
      reasons: []                       # Optional: expected reasons
    tags: ["happy_path", "adult"]       # Optional: test categorization
```

## Test Categories

Organize tests to cover:

### 1. Happy Path Tests
Valid inputs that should result in successful outcomes:
```yaml
- case_id: "happy_001"
  description: "Eligible adult with qualifying income"
  inputs:
    age: 25
    monthly_income: 1500
    household_size: 1
  expected:
    eligible: true
  tags: ["happy_path"]
```

### 2. Boundary Conditions
Test values at the edges of valid ranges:
```yaml
- case_id: "boundary_001"
  description: "Exactly at age threshold (18)"
  inputs:
    age: 18
    monthly_income: 1000
    household_size: 1
  expected:
    eligible: true
  tags: ["boundary", "age"]
```

### 3. Edge Cases
Unusual but valid scenarios:
```yaml
- case_id: "edge_001"
  description: "Very large household size"
  inputs:
    age: 40
    monthly_income: 5000
    household_size: 10
  expected:
    eligible: true
  tags: ["edge_case", "household"]
```

### 4. Invalid Inputs
Inputs that should be rejected or result in ineligibility:
```yaml
- case_id: "invalid_001"
  description: "Under minimum age"
  inputs:
    age: 17
    monthly_income: 1000
    household_size: 1
  expected:
    eligible: false
    reasons: ["AGE_REQUIREMENT_NOT_MET"]
  tags: ["invalid", "age"]
```

### 5. Multiple Rule Interactions
Test how rules interact with each other:
```yaml
- case_id: "interaction_001"
  description: "Fails multiple requirements"
  inputs:
    age: 17
    monthly_income: 10000
    household_size: 1
  expected:
    eligible: false
    reasons: ["AGE_REQUIREMENT_NOT_MET", "INCOME_TOO_HIGH"]
  tags: ["multi_rule"]
```

## Best Practices

### Naming Conventions
- **case_id**: Use format `<category>_<number>` (e.g., `boundary_001`, `invalid_002`)
- **description**: Clear, specific description of what is being tested
- **tags**: Categorize tests for filtering and reporting

### Coverage Requirements
Each ruleset should have tests covering:
- ✅ All rules individually (at least one test per rule)
- ✅ All conditions (true and false paths)
- ✅ All computed variables
- ✅ Boundary values for numeric comparisons
- ✅ All referenced policy citations (validate they're correct)
- ✅ Rule priority/precedence if applicable

### Documentation in Tests
Include comments for complex scenarios:
```yaml
- case_id: "complex_001"
  description: "Income limit varies by household size"
  # This tests the variable calculation: federal_poverty_level * 1.5 * household_size / 12
  # For household_size=3, FPL=$14,580, limit should be ~$2,740/month
  inputs:
    age: 30
    monthly_income: 2700
    household_size: 3
  expected:
    eligible: true
  tags: ["variable_calculation"]
```

## Running Tests

Tests in this format are intended to be:
1. **Machine-readable**: Can be executed by a test runner
2. **Human-readable**: Serve as documentation
3. **Version-controlled**: Track changes over time

Test execution will validate:
- All required inputs are provided
- Outputs match expected results
- Reasons/explanations are correct
- No unexpected side effects

## Example

See [example_benefit_tests.yaml](example_benefit_tests.yaml) for a complete, working example.

## Future Enhancements

As we move toward CIVIL DSL (see [../ruleset/README.md](../ruleset/README.md)), tests will also include:
- Multi-jurisdiction scenarios
- Effective date handling
- Citation validation
- Policy version testing
- Explanation/reasoning validation
