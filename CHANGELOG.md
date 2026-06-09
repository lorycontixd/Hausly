# Changelog

## [Unreleased]

### Added (Phase 7 — Real-Time SignalR)
- `SignalRService` class (`hausly/realtime/signalr.py`): Azure SignalR serverless integration with connection string parsing, JWT generation, and fire-and-forget group broadcasting
- Negotiate endpoint (`POST /api/v1/hubs/household/negotiate`): returns SignalR connection info with auto-join group claim for the user's household
- Type-safe event wrappers for all 15 real-time event types (grocery, expense, meal, chore, member)
- Broadcast calls integrated into grocery, expense, meal, and chore routers after successful mutations
- Graceful degradation: mutations never fail due to SignalR being unavailable (fire-and-forget with warning logs)
- 18 unit tests for SignalR service (parsing, tokens, broadcasts, error handling, event wrappers)

### Added (Phase 6 — Chore Module)
- Chore, ChoreAssignee, ChoreAssignment models with RecurrenceUnit (days/weeks/months) and AssignmentStatus (pending/completed/cancelled) enums
- Chore service: create (creator-in-assignees validation), get/list, update (assignee recomputation), delete (deactivation + future cleanup)
- Assignment generation: idempotent rolling 14-day window, rotation cycling, overdue blocking
- Complete assignment: any household member can mark any assignment done; one-off chores auto-deactivate when all resolved
- Postpone/cancel assignment with status guards
- Member leave: removes from assignees, deletes future assignments, recomputes rotation, deactivates if sole assignee
- Router with 9 endpoints under `/api/v1/households/{id}/chores/`, `require_module("chores")` guard
- Migration 006: chores, chore_assignees, chore_assignments tables with indexes and RLS policies
- Added python-dateutil dependency for monthly recurrence support
- 24 unit tests covering all service operations and edge cases

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
