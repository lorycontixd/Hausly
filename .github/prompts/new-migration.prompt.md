---
description: "Create a new Alembic migration following Hausly conventions (append-only, includes RLS, reversible)."
agent: "API Implement"
argument-hint: "Migration description (e.g., 'add grocery tables')"
---
# New Migration: {{input}}

Create a new Alembic migration for: **{{input}}**

## Steps

1. Read [docs/data-models.md](docs/data-models.md) to understand the target schema.
2. Check existing migrations in `apps/api/migrations/versions/` to determine the next sequence number.
3. Generate the migration file:
   - File naming: `NNN_<snake_case_description>.py`
   - Include both `upgrade()` and `downgrade()`.
   - Add appropriate indexes for query patterns (household_id, foreign keys, common filters).
   - Add Row-Level Security policies for household-scoped tables.

4. Run `cd apps/api && alembic upgrade head` to validate.
5. Verify with `alembic check` that no drift exists.

## RLS Policy Template

```sql
ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;
CREATE POLICY <table_name>_household_isolation ON <table_name>
    USING (household_id = current_setting('app.current_household_id')::uuid);
```

## Output

- Migration file path
- Tables created/modified
- RLS policies added
- Validation result (upgrade succeeded or error)
