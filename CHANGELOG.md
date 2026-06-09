# Changelog

## [Unreleased]

### Added (Phase 5 — Meal Planner Module)
- MealPlanEntry model with MealSlot enum (lunch/dinner), unique constraint on (household_id, date, slot)
- Meal service: get_entries (date range), create_entry (first-come-first-served slot claiming), update/delete (owner/admin only), on_member_leave (future entry cleanup)
- Headcount defaults to active household member count when not specified
- Router with 4 endpoints under `/api/v1/households/{id}/meals/`, `require_module("meal")` guard
- Migration 005: meal_plan_entries table with unique constraint, indexes, and RLS policy
- 13 unit tests covering slot conflicts, ownership guards, default headcount, member leave

### Added (Phase 4 — Expense Module)
- Expense and ExpenseSplit models with status (draft/confirmed), source (manual/grocery_integration/recurring_auto)
- Expense service: create (with splits validation), get, list (cursor pagination + filters), update (draft-only), confirm, delete (draft-only)
- Balance calculation: net balances between member pairs from confirmed unsettled splits
- Settlement suggestions: greedy minimum-transactions algorithm
- Settle split endpoint: marks individual splits as settled (confirmed expenses only)
- Auto-generated expenses enforced to start as draft (no silent financial writes)
- Router with 9 endpoints under `/api/v1/households/{id}/expenses/`, `require_module("expense")` guard
- Migration 004: expenses, expense_splits tables with indexes and RLS policies
- 18 unit tests covering CRUD, confirm flow, balance math, settlement algorithm, and guard logic

### Added (Phase 3 — Grocery Module)
- GroceryList and GroceryItem models with full data-models.md field coverage
- Grocery service: active list auto-creation, CRUD, duplicate detection, personal item filtering
- Shopping session completion: marks items bought/archived, generates expense draft with equal split
- Archive list endpoint (clear list without expense)
- Router with 7 endpoints under `/api/v1/households/{id}/grocery/`, `require_module("grocery")` guard
- Migration 003: grocery_lists (unique active constraint), grocery_items tables with RLS
- 17 unit tests covering all service layer functions

### Added (Phase 2 — Household Management)
- Household CRUD: create, get, update (admin only)
- Household settings: enabled_modules, default_currency, notification_level with tier validation
- Membership lifecycle: join via invite code, leave (with last-admin guard), remove member, change role
- Invite system: preview (unauthenticated), regenerate code (admin only)
- `require_module` dependency factory for per-module access control
- `get_household_membership` shared dependency for membership validation
- Migration 002: households, household_settings, household_memberships tables with RLS
- Auth/verify now returns active household memberships
- 9 unit tests for household service layer
