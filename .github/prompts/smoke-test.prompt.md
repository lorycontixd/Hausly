---
description: "Generate a smoke test to validate a completed feature works end-to-end."
agent: "Test"
argument-hint: "Feature to smoke-test (e.g., 'grocery session complete')"
---
# Smoke Test: {{input}}

Create a smoke test that exercises the core functionality of: **{{input}}**

## Steps

1. Read the relevant phase from [implementation-plan-v1.md](docs/planning/implementation-plan-v1.md) for success criteria.
2. Read relevant `docs/logics/` documentation for expected behavior.
3. Read the implementation code to understand the actual flow.

4. Write a test that:
   - Sets up realistic test data (household, users, relevant entities).
   - Exercises the main happy path end-to-end.
   - Validates the key invariants and success criteria.
   - Checks at least one important edge case.

5. Run the test and confirm it passes.

## Test Style

- Descriptive name: `test_<feature>_end_to_end_<scenario>`
- Use existing fixtures from `conftest.py`
- Assert on business outcomes, not implementation details
- Include comments mapping assertions to success criteria

## Output

- Test file path
- Test function names
- Pass/fail result
- Which success criteria are now verified
