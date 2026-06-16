# Changelog

## [Unreleased]

### Added (Phase 11 — Mobile: Household Management)
- Enhanced onboarding flow (`app/(auth)/onboarding.tsx`): multi-step create (name → type selection) and join (code → preview → confirm) using TanStack Query mutations
- Household settings screen (`app/(tabs)/settings/index.tsx`): displays household info, invite code with share, module toggles (admin), member list, leave button
- Member management screen (`app/(tabs)/settings/member.tsx`): admin-only role change and member removal with confirmation dialogs
- Guided leave flow (`app/(tabs)/settings/leave.tsx`): fetches outstanding items preview, displays unsettled expenses/pending chores, confirmation before leaving
- Settings navigation layout (`app/(tabs)/settings/_layout.tsx`): nested stack for settings, member, leave screens
- `useHouseholdMutations` hook (`hooks/useHouseholdMutations.ts`): TanStack Query mutations for create, join, update, settings, role change, remove, leave, regenerate invite, preview invite
- Added Settings tab to bottom navigation with header delegation to nested stack

### Added (Phase 10 — Mobile: Navigation & Shared UI)
- Tab navigation layout (`app/(tabs)/_layout.tsx`): bottom tabs for Home, Grocery, Expenses, Meals, Chores with conditional visibility based on `household.settings.enabled_modules`
- Design system theme (`constants/theme.ts`): colors, spacing, borderRadius, typography tokens
- UI primitives (`components/ui/`): Button (primary/secondary/destructive, loading state), Card (with elevation), Sheet (bottom sheet modal), Input (with label/error/focus states), Avatar (image + initials fallback), LoadingSpinner, EmptyState
- Barrel export for UI primitives (`components/ui/index.ts`)
- Household Zustand store (`stores/householdStore.ts`): current household state (id, name, members, settings, invite code)
- `useHousehold` hook (`hooks/useHousehold.ts`): TanStack Query fetch + Zustand store sync
- SignalR client (`services/signalr.ts`): negotiate, connect/disconnect, automatic reconnect, event handlers for all 15 event types (grocery, expense, meal, chore, member) that invalidate relevant TanStack Query caches

### Added (Phase 9 — Mobile: Project Setup & Auth)
- Firebase Auth service (`services/firebase.ts`): Google Sign-In, Apple Sign-In, sign-out, auth state listener, token retrieval
- Typed API client (`services/api.ts`): auto-injected Bearer token, typed request/error handling, CRUD methods
- Auth flow screens: login with Google/Apple buttons, register (redirect), onboarding (create/join household)
- Auth state hook (`hooks/useAuth.ts`) and context provider (`providers/AuthProvider.tsx`)
- TanStack Query provider (`providers/QueryProvider.tsx`) with stale/GC/retry defaults
- Root layout auth guard: redirects based on auth status and household membership
- Added dependencies: expo-apple-authentication, @react-native-google-signin/google-signin, expo-secure-store, expo-crypto

### Added (Phase 8 — Background Jobs / Cron)
- Recurring expense job (`hausly/jobs/recurring_expenses.py`): daily generation of draft expenses from confirmed recurring templates, RRULE parsing (FREQ=DAILY/WEEKLY/MONTHLY), staleness cap (pauses at 3 unconfirmed drafts), automatic `next_occurrence_date` advancement
- Chore assignment job (`hausly/jobs/chore_assignments.py`): daily generation of assignments for active recurring chores up to 14-day rolling window, delegates to existing `generate_assignments` (overdue blocking, rotation, idempotency)
- Job scheduler (`hausly/jobs/__init__.py`): APScheduler `AsyncIOScheduler` with CronTrigger (02:00 and 02:05 UTC), startup catch-up run, FastAPI lifespan integration
- Wired scheduler into `hausly/main.py` via `lifespan_jobs` context manager
- 16 unit tests covering RRULE parsing, date advancement, draft generation, staleness cap, overdue blocking, empty-state handling

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
