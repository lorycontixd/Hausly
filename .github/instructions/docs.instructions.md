---
description: "Use when reading, creating, or updating project documentation. Covers the docs/ folder workflow and maintenance rules."
applyTo: "docs/**"
---
# Documentation Conventions (docs/)

## Mandatory Workflow

1. **Always read `docs/docs.md` first** before touching any documentation file.
2. Use `docs/docs.md` to identify which file owns the topic you need.
3. `docs/planning/hausly-project-master-plan.md` is canonical for product scope and architecture.
4. If a code change conflicts with documentation, surface the conflict explicitly.

## File Roles

| File | Owns |
|------|------|
| `docs/docs.md` | Index — what each doc covers |
| `planning/hausly-project-master-plan.md` | Product scope, architecture, decisions |
| `planning/implementation-plan-v1.md` | Phase-by-phase implementation steps |
| `data-models.md` | Database entity definitions |
| `api-reference.md` | Endpoint contracts |
| `signalr-architecture.md` | Real-time architecture |
| `logics/*.md` | Feature behaviour and algorithms |

## Maintenance Rules

- Keep edits minimal and factual. Prefer short additions over rewrites.
- Do not duplicate information across files. Cross-reference instead.
- Update `docs/docs.md` if a new file is added or a file's purpose changes.
- Planning documents must include at the top:
  ```
  - Read: false
  - Approved: false
  - Notes: NA
  ```

## Phase Completion Marking

When an implementation phase is complete, mark it in `implementation-plan-v1.md`:

```markdown
## Phase N — Title [completed]
### Completed:
- Brief summary of what was accomplished.
- Any important notes for future reference.
```

## Decision Log

Non-trivial decisions go in the Decision Log (§10 of the master plan). Format:
`| Decision | Rationale | Date |`

Never silently overturn a logged decision.
