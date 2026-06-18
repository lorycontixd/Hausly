-- nuke_all_data.sql
-- Deletes ALL data from every table in the database.
--
-- Purpose: Full database reset for development/testing.
-- Usage:   psql -d hausly_dev -f nuke_all_data.sql
--
-- Constraints respected:
--   - Truncation order respects foreign key dependencies (children first).
--   - CASCADE ensures referential integrity is maintained.
--   - Alembic migration history (alembic_version) is preserved.
--
-- ⚠️  WARNING: This is destructive and irreversible.
-- ⚠️  Dev/test use ONLY — never run against production.

BEGIN;

-- Level 3: deepest children
TRUNCATE TABLE expense_splits CASCADE;
TRUNCATE TABLE grocery_items CASCADE;
TRUNCATE TABLE chore_assignees CASCADE;
TRUNCATE TABLE chore_assignments CASCADE;

-- Level 2: intermediate tables
TRUNCATE TABLE expenses CASCADE;
TRUNCATE TABLE grocery_lists CASCADE;
TRUNCATE TABLE chores CASCADE;

-- Level 1: direct dependents of root tables
TRUNCATE TABLE meal_plan_entries CASCADE;
TRUNCATE TABLE household_settings CASCADE;
TRUNCATE TABLE household_memberships CASCADE;

-- Level 0: root tables
TRUNCATE TABLE households CASCADE;
TRUNCATE TABLE users CASCADE;

COMMIT;
