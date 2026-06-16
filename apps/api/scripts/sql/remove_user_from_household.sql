-- remove_user_from_household.sql
-- Soft-removes a user from their active household membership and archives
-- the household if no active members remain.
--
-- Usage: Replace 'testuser1@test.com' with the target user's email.
--
-- How it works:
--   1. Sets `left_at = NOW()` on the active membership (soft delete, preserves audit trail)
--   2. Archives any household that has zero active members remaining
--
-- Constraints respected:
--   - Membership row is preserved (not hard-deleted) for historical reference
--   - Partial unique index on (user_id) WHERE left_at IS NULL is freed,
--     allowing the user to join a new household
--   - Household is archived (not deleted) when empty
--
-- NOTE: This bypasses service-layer checks (last-admin guard, module cleanup).
--       Use only for dev/test resets.

-- Step 1: Soft-delete the membership
UPDATE household_memberships
SET left_at = NOW()
WHERE user_id = (SELECT id FROM users WHERE email = 'testuser1@test.com')
  AND left_at IS NULL;

-- Step 2: Archive households with no remaining active members
UPDATE households
SET archived_at = NOW()
WHERE id IN (
  SELECT h.id FROM households h
  WHERE h.archived_at IS NULL
    AND NOT EXISTS (
      SELECT 1 FROM household_memberships hm
      WHERE hm.household_id = h.id AND hm.left_at IS NULL
    )
);
