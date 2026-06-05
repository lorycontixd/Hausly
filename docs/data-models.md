# Data Models

> Derived from docs/planning/hausly-project-master-plan.md §4.5 and module descriptions.
> This is a **planning reference**, not generated ORM code.

---

## Conventions

- Every household-scoped table carries a `household_id` FK and is protected by Row-Level Security (RLS).
- All timestamps are UTC, stored as `timestamptz`.
- Soft deletes use an `archived_at` column where applicable.
- IDs are UUIDs unless noted otherwise.

---

## Core Entities

### Household

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| name | text | Display name |
| type | enum | couple / friends / students / family / custom |
| invite_code | text | Short alphanumeric, unique |
| subscription_tier | enum | free / paid     |
| subscription_owner_id | UUID | FK → User. The member who pays. |
| created_at | timestamptz | |
| archived_at | timestamptz | Nullable. Set when last member leaves. |

Constraints:
- `invite_code` is unique and regenerable by admin.
- `subscription_owner_id` must reference an active member of the household.
- A `HouseholdSettings` row is created atomically with the Household (never nullable).

---

### HouseholdSettings

| Column | Type | Notes |
|--------|------|-------|
| household_id | UUID | PK + FK → Household (1:1) |
| default_currency | text | ISO 4217 code. Default: 'EUR'. |
| enabled_modules | text[] | Array of module identifiers: grocery / expense / meal / chores / pinboard |
| notification_level | enum | low / medium / high. Default: medium. |
| created_at | timestamptz | |
| updated_at | timestamptz | |

Constraints:
- Created atomically with Household in the same transaction.
- `enabled_modules` is bounded by `subscription_tier`: free tier allows grocery + expense + chores + meal; paid tier allows all modules.
- Module API endpoints check `module_name IN enabled_modules` before allowing access (returns 403 `MODULE_DISABLED` if not enabled).

---

### User

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| firebase_uid | text | Unique. From Firebase Auth. |
| display_name | text | |
| email | text | |
| avatar_url | text | Nullable |
| created_at | timestamptz | |

Constraints:
- A user can belong to multiple households (via HouseholdMembership) at the data model level, but **v1 enforces single active membership** at the application level. Joining a new household requires leaving the current one.
- Recipes are owned at this level, not household level.

---

### HouseholdMembership

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| household_id | UUID | FK → Household |
| user_id | UUID | FK → User |
| role | enum | admin / member |
| joined_at | timestamptz | |
| left_at | timestamptz | Nullable. Set on leave; row retained for history. |

Constraints:
- Unique active membership per (household_id, user_id) where `left_at IS NULL`.
- At least one admin must exist while the household has active members.
- **v1 constraint:** a user may have at most one active membership (`left_at IS NULL`) across all households. Enforced at application level, not DB constraint (allows future multi-household support).

---

## Grocery Module

### GroceryList

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| household_id | UUID | FK → Household |
| name | text | Default: "Shopping List" |
| is_active | bool | Only one active list per household at a time |
| created_at | timestamptz | |
| archived_at | timestamptz | Nullable. Set by "Clear list". |

### GroceryItem

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| list_id | UUID | FK → GroceryList |
| household_id | UUID | FK → Household (denormalized for RLS) |
| name | text | |
| quantity | numeric | Nullable |
| unit | text | Nullable |
| is_bought | bool | Default false |
| bought_by_user_id | UUID | Nullable. FK → User |
| bought_at | timestamptz | Nullable |
| added_by_user_id | UUID | FK → User |
| source | enum | manual / meal_plan / ai_suggestion |
| is_personal | bool | Default false. Personal items are excluded from expense generation. |
| personal_for_user_id | UUID | Nullable. FK → User. Set when is_personal = true. |
| personal_visibility | enum | visible / hidden. Default: visible. Only applies when is_personal = true. Hidden items are only shown to the owner. |
| is_archived | bool | Default false. Set true when the parent list is archived. Keeps item data for statistics/history. |
| created_at | timestamptz | |

Constraints:
- Duplicate detection is application-level (case-insensitive name match within the active list).
- `personal_for_user_id` must be set when `is_personal = true`.
- Personal items with `personal_visibility = hidden` are filtered from API responses for non-owner users.

---

## Expense Module

### Expense

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| household_id | UUID | FK → Household |
| title | text | |
| amount | numeric(12,2) | Positive |
| currency | text | ISO 4217 code. Default from household settings. |
| category | text | Nullable. Free-text tag. |
| paid_by_user_id | UUID | FK → User |
| is_recurring | bool | |
| recurrence_rule | text | Nullable. RRULE string (for recurring). |
| next_occurrence_date | date | Nullable. Next date a draft should be generated. Used by the recurring expense cron job. |
| status | enum | draft / confirmed |
| source | enum | manual / grocery_integration / recurring_auto |
| confirmed_at | timestamptz | Nullable. Set when user confirms. |
| created_at | timestamptz | |

Constraints:
- `status` must be `confirmed` before balances are affected. Draft entries are invisible to settlement logic.
- Auto-generated entries (recurring, grocery integration) always start as `draft`.

### ExpenseSplit

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| expense_id | UUID | FK → Expense |
| household_id | UUID | FK → Household (denormalized for RLS) |
| user_id | UUID | FK → User |
| share_amount | numeric(12,2) | The participant's owed portion |
| is_settled | bool | Default false |
| settled_at | timestamptz | Nullable |

Constraints:
- Sum of `share_amount` across splits must equal `expense.amount`.
- Settlement is marked manually (external payment).

---

## Meal Planner Module

### MealPlanEntry

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| household_id | UUID | FK → Household |
| date | date | |
| slot | enum | lunch / dinner |
| text | text | Free-form description |
| headcount | int | Defaults to household member count |
| linked_recipe_id | UUID | Nullable. FK → Recipe (v2+) |
| owner_user_id | UUID | FK → User. The member who claimed/created this slot. |
| created_at | timestamptz | |

Constraints:
- One entry per (household_id, date, slot). First-come-first-served: only the `owner_user_id` or an admin can edit/delete.
- `linked_recipe_id` references the owner's own recipe fork.
- When the owner leaves the household, their future meal entries (date > leave_date) are auto-deleted. Past entries are retained.

---

## Recipe Module (v2)

### Recipe

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| owner_user_id | UUID | FK → User. **User-level, not household.** |
| name | text | |
| base_servings | int | e.g. 4 |
| notes | text | Nullable. Free-text instructions. |
| forked_from_recipe_id | UUID | Nullable. FK → Recipe (self-ref). Informational only. |
| created_at | timestamptz | |

Constraints:
- Recipes are **not** scoped by household_id. They belong to the user across households.
- Fork-on-save: saving another user's recipe creates a new row with `owner_user_id` = saver.

### RecipeIngredient

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| recipe_id | UUID | FK → Recipe |
| name | text | |
| quantity | numeric | Nullable |
| unit | text | Nullable |
| position | int | Display order |

---

## Chore Module

### Chore

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| household_id | UUID | FK → Household |
| name | text | e.g. "Clean bathroom" |
| created_by_user_id | UUID | FK → User. Must be in assignees. |
| is_recurring | bool | |
| recurrence_interval | int | Nullable. Only if recurring. e.g. 1, 2, 3 |
| recurrence_unit | enum | Nullable. days / weeks / months |
| start_date | date | First occurrence. Anchors day-of-week for weekly recurrence. |
| rotation_enabled | bool | Default false. Only meaningful with >1 assignee. |
| is_active | bool | Default true. False when deleted or one-off completed. |
| created_at | timestamptz | |

Constraints:
- `created_by_user_id` must appear in the `ChoreAssignee` list.
- `recurrence_interval` and `recurrence_unit` required when `is_recurring = true`.
- Any household member can create or delete a chore.

### ChoreAssignee

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| chore_id | UUID | FK → Chore |
| household_id | UUID | FK → Household (denormalized for RLS) |
| user_id | UUID | FK → User |
| position | int | Rotation order (0-indexed) |

Constraints:
- Creator must be included as an assignee.
- `position` determines rotation order when `rotation_enabled = true`.
- On member leave: row is deleted, future assignments removed, rotation recomputes with remaining members.

### ChoreAssignment

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| chore_id | UUID | FK → Chore |
| household_id | UUID | FK → Household (denormalized for RLS) |
| assigned_to_user_id | UUID | FK → User |
| due_date | date | Original scheduled date |
| postponed_to | date | Nullable. New effective date if postponed. |
| status | enum | pending / completed / cancelled |
| completed_at | timestamptz | Nullable |
| completed_by_user_id | UUID | Nullable. FK → User. May differ from assignee. |
| created_at | timestamptz | |

Constraints:
- Anyone in the household can mark any assignment as done.
- Effective due date: `COALESCE(postponed_to, due_date)`.
- Overdue = `status = pending` AND `COALESCE(postponed_to, due_date) < today`.
- Overdue assignments **block** generation of new assignments for the same chore.
- One-off chore auto-deactivates when all its assignments reach terminal status (completed/cancelled).

---

## Pinboard Module (v2)

### PinboardNote

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| household_id | UUID | FK → Household |
| author_user_id | UUID | FK → User |
| content | text | |
| photo_url | text | Nullable. Azure Blob Storage path. |
| is_pinned | bool | Default false |
| expires_at | timestamptz | Nullable. Opt-in expiry. |
| created_at | timestamptz | |

Constraints:
- Notes are permanent by default (`expires_at` NULL).
- Pinned notes sort first regardless of creation date.

---

## Relationships Diagram (textual)

```
User ──┬── HouseholdMembership ──── Household ──── HouseholdSettings (1:1)
       │
       ├── Recipe ── RecipeIngredient
       │
       ├── Expense (paid_by)
       │      └── ExpenseSplit (per participant)
       │
       ├── MealPlanEntry (owner_user_id)
       │
       └── (references across modules via user_id FKs)

Household ──┬── HouseholdSettings (1:1)
            ├── GroceryList ── GroceryItem (includes personal items)
            ├── MealPlanEntry ──→ Recipe (optional link)
            ├── Chore ── ChoreAssignee + ChoreAssignment
            ├── PinboardNote
            └── Expense
```

---

## RLS Policy Design

### Principles

1. **One session variable only:** `app.current_household_id`. No `app.current_user_id` at the RLS level.
2. **Uniform policy** across all household-scoped tables. No business logic in RLS.
3. **Denormalize `household_id`** onto child tables (`expense_splits`, `chore_assignees`) rather than using subquery policies.
4. **RLS is the safety net, not the access control.** Application code remains responsible for filtering, authorization, personal item visibility, and role-based access. RLS catches the case where a developer forgets to scope a query.

### Session Variable Setup

Application code sets `app.current_household_id` per request using `SET LOCAL` (transaction-scoped, safe for connection pooling):

```sql
SET LOCAL app.current_household_id = '<uuid>';
```

### Policy Template

Every household-scoped table uses this identical policy:

```sql
ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON <table>
  USING (household_id = current_setting('app.current_household_id')::uuid)
  WITH CHECK (household_id = current_setting('app.current_household_id')::uuid);
```

For the `households` table itself, the policy filters on `id` instead of `household_id`:

```sql
CREATE POLICY tenant_isolation ON households
  USING (id = current_setting('app.current_household_id')::uuid)
  WITH CHECK (id = current_setting('app.current_household_id')::uuid);
```

### Per-Table Summary

| Table | RLS | Filter Column |
|-------|-----|---------------|
| `households` | Yes | `id` |
| `household_settings` | Yes | `household_id` |
| `household_memberships` | Yes | `household_id` |
| `grocery_lists` | Yes | `household_id` |
| `grocery_items` | Yes | `household_id` |
| `expenses` | Yes | `household_id` |
| `expense_splits` | Yes | `household_id` (denormalized) |
| `meal_plan_entries` | Yes | `household_id` |
| `chores` | Yes | `household_id` |
| `chore_assignees` | Yes | `household_id` (denormalized) |
| `chore_assignments` | Yes | `household_id` (already denormalized) |
| `users` | **No** | N/A — not tenant-scoped |

### Why `users` Has No RLS

The `users` table contains non-sensitive display data (name, avatar). It is not scoped to a household — users exist independently. The API layer controls what fields are exposed. Adding RLS here would complicate the join flow, invite preview, and internal service calls with no security gain.

### Special Cases

- **Join flow:** When a user is joining a household (no `app.current_household_id` set yet), the service temporarily sets the session variable to the target household after validating the invite code.
- **Background jobs:** Cron tasks iterate over multiple households. They set `app.current_household_id` per iteration before executing queries.
- **Personal item visibility:** Handled in application code (query filtering), not RLS. RLS only ensures tenant isolation.
