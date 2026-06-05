---
description: "Execute a full implementation phase from the implementation plan. Reads docs, implements code, runs tests, updates docs."
agent: "agent"
argument-hint: "Phase number (e.g., 3)"
tools: [read, edit, search, execute, todo, agent]
---
# Implement Phase {{input}}

Execute the following workflow for Phase {{input}} from the implementation plan.

## Pre-flight

1. Read [docs/docs.md](docs/docs.md) to orient.
2. Read [docs/planning/implementation-plan-v1.md](docs/planning/implementation-plan-v1.md) — find Phase {{input}}.
3. Read all referenced documentation files for this phase (data-models, api-reference, logics/).
4. If the phase impacts scope/architecture/financial flows/permissions, invoke the **Plan Guard** agent first and report the verdict.

## Implementation

5. For each step in the phase:
   a. Identify the files to create or modify.
   b. Implement following the conventions in `.github/instructions/` and `.github/copilot-instructions.md`.
   c. After each major step, run lint/type checks to catch errors early.

6. After all steps complete:
   a. Run the full test suite for the affected area (`pytest -v` or `tsc --noEmit`).
   b. Fix any failures.

## Post-implementation

7. Update documentation if behavior or scope changed.
8. Mark the phase as `[completed]` in `implementation-plan-v1.md` with a `### Completed:` section.
9. Update `CHANGELOG.md` with notable changes.
10. Suggest a commit message with the appropriate prefix.

## Output

Provide a summary:
- Files created/modified
- Tests written and their pass/fail status
- Success criteria: which are met, which need follow-up
- Suggested commit message
- Any open issues or blockers for the next phase
