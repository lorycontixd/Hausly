---
description: "Run a pre-merge review of current changes against project conventions and implementation plan."
agent: "Reviewer"
argument-hint: "Phase or feature name to review (e.g., 'Phase 3 - Grocery')"
---
# Review: {{input}}

Perform a thorough pre-merge review of the implementation for: **{{input}}**

## Review Scope

1. Read the relevant phase from [implementation-plan-v1.md](docs/planning/implementation-plan-v1.md).
2. Read the implementation code that was produced.
3. Check all items on the review checklist (architecture, conventions, docs, tests, security, anti-patterns).

## Focus Areas

- Does the implementation match the phase's success criteria?
- Are conventions from `.github/instructions/` followed?
- Are architectural non-negotiables respected?
- Are tests present and meaningful?
- Is documentation updated where needed?

## Output

Produce the full review report with:
- Verdict (Ready / Changes Requested / Blocked)
- Findings table with severity, file, issue, and suggestion
- Documentation status
- Success criteria coverage map
