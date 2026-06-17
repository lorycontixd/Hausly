# Hausly MVP (v1) — Step-by-Step Implementation Plan

- Read: false
- Approved: false
- Notes: NA

---

## Purpose

This document is a sequential, step-by-step implementation plan for the Hausly MVP (v1).
It is designed to be consumed by a coding agent. Each phase has clear inputs, outputs, and success criteria.

**Source of truth:** `docs/planning/hausly-project-master-plan.md`
**Data models:** `docs/data-models.md`
**API contracts:** `docs/api-reference.md`
**Feature logic:** `docs/logics/`

---

## Scope Summary (v1 only)

Modules shipping in v1:
1. **Shared Grocery List** (with shopping session and expense integration)
2. **Shared Expense Tracker** (with recurring expenses and settlement)
3. **Meal Planner** (diary-style, text-only, no recipes)
4. **Chore System** (per-chore recurrence, rotation, overdue blocking)

Out of scope for v1: Pinboard, Recipe book, AI features, Analytics dashboard.

---

## Phase Overview

| Phase | Focus | Depends On |
|-------|-------|-----------|
| 0 | Project scaffolding & tooling | Nothing |
| 1 | Backend: Database & Auth | Phase 0 |
| 2 | Backend: Household management | Phase 1 |
| 3 | Backend: Grocery module | Phase 2 |
| 4 | Backend: Expense module | Phase 2 |
| 5 | Backend: Meal planner module | Phase 2 |
| 6 | Backend: Chore module | Phase 2 |
| 7 | Backend: Real-time (SignalR) | Phases 3–6 |
| 8 | Backend: Recurring expense cron + chore assignment cron | Phases 4, 6 |
| 9 | Mobile: Project setup & auth | Phase 0 |
| 10 | Mobile: Navigation & shared UI | Phase 9 |
| 11 | Mobile: Household management | Phases 2, 10 |
| 12 | Mobile: Grocery module | Phases 3, 7, 10 |
| 13 | Mobile: Expense module | Phases 4, 7, 10 |
| 14 | Mobile: Meal planner module | Phases 5, 7, 10 |
| 15 | Mobile: Chore module | Phases 6, 7, 10 |
| 16 | Integration testing & polish | All |

---

## Phase 0 — Project Scaffolding & Tooling [completed]

**Goal:** Establish the monorepo structure, tooling configs, and CI/CD.

### Steps

0.1. Create monorepo directory structure per `docs/project-structure.md`:
- `apps/mobile/` — Expo project
- `apps/api/` — FastAPI project
- `packages/types/` — Shared TypeScript types
- `infra/` — Azure Bicep templates (placeholder)
- `docs/` — Already exists

0.2. Initialize the API project (`apps/api/`):
- Create `pyproject.toml` with dependencies: fastapi, uvicorn, sqlmodel, asyncpg, sqlalchemy[asyncio], alembic, pydantic-settings, firebase-admin, python-jose, httpx
- Dev dependencies: pytest, pytest-asyncio, ruff, mypy
- Configure ruff (linting + formatting)
- Create `alembic.ini` and `migrations/env.py`
- Create `Dockerfile` (multi-stage: dev + prod)
- Create `hausly/__init__.py`, `hausly/main.py`, `hausly/config.py`, `hausly/database.py`

0.3. Initialize the mobile project (`apps/mobile/`):
- Run `npx create-expo-app` with TypeScript template
- Add dependencies: expo-router, @tanstack/react-query, zustand, expo-sqlite, @microsoft/signalr
- Configure `tsconfig.json` with strict mode and path aliases
- Configure `app.json` with bundle ID and plugins
- Set up `babel.config.js` with module resolver for path aliases

0.4. Initialize the shared types package (`packages/types/`):
- Create `package.json` and `tsconfig.json`
- Create `src/index.ts` placeholder

0.5. Create root-level files:
- `Makefile` with commands: `start-api`, `start-mobile`, `test-api`, `lint`, `migrate`
- `.env.example` documenting all required env vars
- Root `README.md`

### Success Criteria
- `cd apps/api && uvicorn hausly.main:app` starts without error
- `cd apps/mobile && npx expo start` launches the dev server
- `make lint` runs ruff on the API codebase

---

## Phase 1 — Backend: Database & Auth

**Goal:** Set up PostgreSQL connection, SQLModel base, Alembic migrations, and Firebase auth middleware.

### Steps

1.1. **Database connection** (`hausly/database.py`):
- Async SQLAlchemy engine using asyncpg
- `AsyncSession` factory
- `get_db` dependency for FastAPI
- Connection string from `config.py` (pydantic-settings)

1.2. **Config** (`hausly/config.py`):
- Use `pydantic-settings` with `.env` file support
- Fields: `DATABASE_URL`, `FIREBASE_PROJECT_ID`, `SIGNALR_CONNECTION_STRING`, `AI_PROVIDER`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_KEY`, `CORS_ORIGINS`

1.3. **Base model** (create `hausly/models/base.py`):
- `Base` class extending SQLModel with common fields (id as UUID, created_at)
- `HouseholdScopedBase` adding `household_id` FK

1.4. **User model** (`hausly/modules/users/models.py`):
- `User` table: id, firebase_uid, display_name, email, avatar_url, created_at

1.5. **Firebase auth** (`hausly/auth/firebase.py`):
- Initialize Firebase Admin SDK
- `verify_firebase_token(token: str) -> dict` — verifies JWT, returns uid + claims
- `get_current_user` FastAPI dependency: extracts Bearer token, verifies, looks up or creates User row

1.6. **Shared dependencies** (`hausly/dependencies.py`):
- `get_current_user` — returns authenticated User
- `get_db` — yields AsyncSession
- `get_household_membership` — validates user belongs to the household in the path param, returns membership with role

1.7. **First migration** (`migrations/versions/001_initial.py`):
- Create `users` table

### Success Criteria
- `POST /auth/verify` with a valid Firebase token returns user profile
- Invalid tokens return 401
- Alembic migration runs cleanly against a fresh DB

---

## Phase 2 — Backend: Household Management [completed]

**Goal:** Implement household CRUD, membership, invite codes, and the leave flow.

### Steps

2.1. **Models** (`hausly/modules/household/models.py`):
- `Household`: id, name, type (enum), invite_code, subscription_tier, subscription_owner_id, created_at, archived_at
- `HouseholdSettings`: household_id (PK/FK), default_currency, enabled_modules (text[]), notification_level, created_at, updated_at
- `HouseholdMembership`: id, household_id, user_id, role (enum), joined_at, left_at

2.2. **Schemas** (`hausly/modules/household/schemas.py`):
- `HouseholdCreate`: name, type
- `HouseholdResponse`: all fields + settings + members
- `HouseholdSettingsUpdate`: enabled_modules, default_currency, notification_level
- `InvitePreviewResponse`: household_name, member_count, type
- `JoinRequest`: invite_code
- `LeaveResponse`: unsettled_expenses, pending_chores
- `MemberResponse`: user_id, display_name, role, joined_at

2.3. **Service** (`hausly/modules/household/service.py`):
- `create_household(user, data)` → creates Household + Settings + Membership(admin) atomically
- `get_household(household_id)` → with settings and active members
- `update_household(household_id, data)` → admin only
- `update_settings(household_id, data)` → admin only, validate modules against tier
- `preview_invite(code)` → returns name + count (no auth)
- `join_household(user, invite_code)` → validate single membership constraint, create Membership
- `leave_household(user, household_id)` → return unsettled data, then remove membership
- `remove_member(admin_user, household_id, target_user_id)` → admin removes member
- `change_role(admin_user, household_id, target_user_id, new_role)` → role change
- `regenerate_invite_code(household_id)` → generate new code, invalidate old

2.4. **Router** (`hausly/modules/household/router.py`):
- Mount all endpoints per `docs/api-reference.md` under households section
- Apply auth + membership guards

2.5. **Module check middleware** (`hausly/dependencies.py`):
- `require_module(module_name)` dependency factory: checks `module_name IN household.settings.enabled_modules`, returns 403 `MODULE_DISABLED` if not

2.6. **Migration** (`migrations/versions/002_households.py`):
- Create `households`, `household_settings`, `household_memberships` tables
- Add RLS policies

### Success Criteria
- Full household lifecycle works: create → invite → join → leave
- Single-membership constraint enforced (409 on second join)
- Module enable/disable reflected in settings
- RLS policies tested (cross-household query returns empty)

### Completed:
- Implemented Household, HouseholdSettings, HouseholdMembership models with enums.
- Created full service layer: create, join, leave, remove, change role, settings update, invite preview, code regeneration.
- Built router with auth + admin guards, matching all endpoints from api-reference.md.
- Added `require_module` and `get_household_membership` dependencies.
- Created migration 002_households with RLS policies and partial unique index.
- Updated auth/verify to return active household memberships.
- 9 unit tests covering constraints (single-membership, last-admin, tier limits, invalid modules).

---

## Phase 3 — Backend: Grocery Module [completed]

**Goal:** Full grocery list CRUD, personal items, shopping session completion with expense integration.

**Reference:** `docs/logics/grocery-session.md`, `docs/api-reference.md`

### Steps

3.1. **Models** (`hausly/modules/grocery/models.py`):
- `GroceryList`: id, household_id, name, is_active, created_at, archived_at
- `GroceryItem`: all fields per `docs/data-models.md`

3.2. **Schemas** (`hausly/modules/grocery/schemas.py`):
- `GroceryItemCreate`: name, quantity?, unit?, source?, is_personal?, personal_visibility?
- `GroceryItemUpdate`: name?, quantity?, unit?, is_personal?, personal_visibility?
- `GroceryItemResponse`: full item data
- `SessionCompleteRequest`: bought_item_ids, receipt_total, create_expense
- `SessionCompleteResponse`: items_removed, expense_draft_id?, expense_draft?
- `ArchiveRequest`: confirm (bool)

3.3. **Service** (`hausly/modules/grocery/service.py`):
- `get_active_list(household_id)` → get or create active list
- `get_items(household_id, list_id, user_id)` → filter hidden personal items for non-owners
- `add_items(household_id, items, user_id)` → duplicate detection (case-insensitive), add to active list
- `update_item(item_id, data)` → validate ownership rules for personal items
- `delete_item(item_id)`
- `complete_session(household_id, user_id, data)` → mark bought, archive items, optionally create draft expense (calls expense service)
- `archive_list(household_id)` → archive active list, does NOT create expense

3.4. **Router** (`hausly/modules/grocery/router.py`):
- Mount all grocery endpoints with `require_module("grocery")` dependency
- Apply auth + household membership guards

3.5. **Migration** (`migrations/versions/003_grocery.py`):
- Create `grocery_lists`, `grocery_items` tables with indexes and RLS

### Success Criteria
- Add/update/delete items works
- Personal items hidden from non-owners
- Session complete: items archived, draft expense created
- Duplicate detection prevents same-name item in active list
- Archive list works without creating expense

### Completed:
- Implemented GroceryList and GroceryItem SQLModel models with all fields from data-models.md.
- Created schemas: GroceryItemCreate, GroceryItemUpdate, GroceryItemResponse, GroceryListResponse, SessionCompleteRequest, SessionCompleteResponse, ArchiveRequest.
- Built full service layer: get_active_list (auto-creates), get_items (with personal item filtering), add_items (with case-insensitive duplicate detection), update_item, delete_item, complete_session (with expense draft generation), archive_list.
- Router with all 7 endpoints, require_module("grocery") guard, auth + membership dependencies.
- Migration 003_grocery: grocery_lists (with unique active list constraint), grocery_items tables, RLS enabled.
- 17 unit tests covering: list management, personal item visibility, duplicate detection, CRUD operations, session completion with/without expense, personal item exclusion from expenses, archive flow.
- All 49 tests pass (17 new + 32 existing).

---

## Phase 4 — Backend: Expense Module [completed]

**Goal:** Expense CRUD, splits validation, draft→confirm flow, balance calculation, settlement suggestions.

**Reference:** `docs/logics/expense-splits.md`, `docs/api-reference.md`

### Steps

4.1. **Models** (`hausly/modules/expense/models.py`):
- `Expense`: all fields per data model (status enum: draft/confirmed, source enum: manual/grocery_integration/recurring_auto)
- `ExpenseSplit`: expense_id, user_id, share_amount, is_settled, settled_at

4.2. **Schemas** (`hausly/modules/expense/schemas.py`):
- `ExpenseCreate`: title, amount, currency, category?, paid_by_user_id, splits[], status, source?
- `SplitInput`: user_id, share_amount
- `ExpenseResponse`: full expense with splits
- `BalanceResponse`: list of `{ user_a_id, user_b_id, net_amount, direction }`
- `SettlementSuggestion`: from_user_id, to_user_id, amount

4.3. **Service** (`hausly/modules/expense/service.py`):
- `create_expense(household_id, data)` → validate sum(splits) == amount, create expense + splits
- `get_expense(expense_id)` → with splits
- `list_expenses(household_id, filters)` → pagination, filter by status/category/date
- `update_expense(expense_id, data)` → only if draft
- `confirm_expense(expense_id)` → set status=confirmed, set confirmed_at
- `delete_expense(expense_id)` → only if draft; confirmed expenses get archived
- `get_balances(household_id)` → compute net balances between all member pairs (confirmed only)
- `get_settlements(household_id)` → minimum-transactions algorithm
- `settle_split(split_id)` → mark is_settled=true

4.4. **Balance algorithm** (inside service or utility):
```
For each pair (A, B):
    A_owes_B = sum of A's splits where paid_by = B and status = confirmed and not settled
    B_owes_A = sum of B's splits where paid_by = A and status = confirmed and not settled
    net = A_owes_B - B_owes_A
```

4.5. **Settlement algorithm** (greedy minimum-transactions):
```
1. Compute net balance per person (total_owed - total_credited)
2. Sort into debtors (negative) and creditors (positive)
3. Match largest debtor with largest creditor, transfer min(abs(debt), credit)
4. Repeat until all nets are zero
```

4.6. **Router** (`hausly/modules/expense/router.py`):
- Mount all expense endpoints with `require_module("expense")` dependency

4.7. **Migration** (`migrations/versions/004_expenses.py`):
- Create `expenses`, `expense_splits` tables with indexes and RLS

### Success Criteria
- Create expense validates sum(splits) == amount
- Only confirmed expenses affect balances
- Draft→confirm flow works
- Balance calculation correct for multiple payers/participants
- Settlement algorithm minimizes transactions
- Grocery integration: session complete creates a proper draft expense

### Completed:
- Implemented Expense and ExpenseSplit SQLModel models with all fields from data-models.md (status enum, source enum, household_id denormalized on splits for RLS).
- Created schemas: ExpenseCreate (with splits sum validation), ExpenseUpdate, ExpenseResponse, SplitInput, SplitResponse, BalanceEntry, BalanceResponse, SettlementSuggestion, SettlementResponse.
- Built full service layer: create_expense (with auto-generated-must-be-draft guard), get_expense, list_expenses (cursor pagination + status/category filters), update_expense (draft-only), confirm_expense, delete_expense (draft-only), get_balances (confirmed + unsettled splits only), get_settlements (greedy minimum-transactions), settle_split (with confirmed-expense check).
- Router with 9 endpoints: list, create, get, update, confirm, delete, balances, settlements, settle_split — all gated by require_module("expense").
- Migration 004_expenses: expenses and expense_splits tables with indexes, FKs, and RLS policies.
- 18 unit tests covering: creation, splits validation, auto-generated-must-be-draft, confirm flow, update restrictions, delete restrictions, balance calculation, settlement algorithm (2 and 3 users), settle_split guards, 404 handling.
- All 77 tests pass (18 new + 59 existing).

---

## Phase 5 — Backend: Meal Planner Module [completed]

**Goal:** Weekly meal diary with slot ownership and headcount.

**Reference:** `docs/api-reference.md`, master plan §2.1

### Steps

5.1. **Models** (`hausly/modules/meal/models.py`):
- `MealPlanEntry`: id, household_id, date, slot (enum: lunch/dinner), text, headcount, linked_recipe_id (nullable, unused in v1), owner_user_id, created_at

5.2. **Schemas** (`hausly/modules/meal/schemas.py`):
- `MealEntryCreate`: date, slot, text, headcount?
- `MealEntryUpdate`: text?, headcount?
- `MealEntryResponse`: full entry with owner display_name

5.3. **Service** (`hausly/modules/meal/service.py`):
- `get_entries(household_id, start_date, end_date)` → list entries in range
- `create_entry(household_id, user_id, data)` → check slot not taken (409 if exists), set owner_user_id
- `update_entry(entry_id, user_id, user_role, data)` → only owner or admin can edit
- `delete_entry(entry_id, user_id, user_role)` → only owner or admin can delete
- `on_member_leave(household_id, user_id)` → delete future entries owned by leaving user

5.4. **Router** (`hausly/modules/meal/router.py`):
- Mount all meal endpoints with `require_module("meal")` dependency
- Ownership check in PATCH/DELETE

5.5. **Migration** (`migrations/versions/005_meals.py`):
- Create `meal_plan_entries` table with unique constraint on (household_id, date, slot)

### Success Criteria
- First-come-first-served slot claiming works (409 on conflict)
- Only owner/admin can edit/delete
- Headcount defaults to household member count
- Member leave deletes their future entries

### Completed:
- Implemented MealPlanEntry model with MealSlot enum (lunch/dinner), unique constraint on (household_id, date, slot).
- Created schemas: MealEntryCreate, MealEntryUpdate, MealEntryResponse (with owner_display_name).
- Built full service layer: get_entries (date range query), create_entry (slot conflict detection, default headcount from member count), update_entry (owner/admin guard), delete_entry (owner/admin guard), on_member_leave (deletes future entries).
- Router with 4 endpoints: GET (date range), POST (claim slot), PATCH (update), DELETE — all gated by require_module("meal").
- Migration 005_meals: meal_plan_entries table with unique constraint, indexes, and RLS policy.
- 13 unit tests covering: date range queries, slot claiming, 409 on conflict, default headcount, owner/admin edit/delete, forbidden for non-owners, 404 handling, member leave cleanup.
- All 100 tests pass (13 new + 87 existing).

---

## Phase 6 — Backend: Chore Module [completed]

**Goal:** Full chore system with recurrence, rotation, assignment generation, and overdue blocking.

**Reference:** `docs/logics/chore-schedule.md`, `docs/api-reference.md`

### Steps

6.1. **Models** (`hausly/modules/chores/models.py`):
- `Chore`: id, household_id, name, created_by_user_id, is_recurring, recurrence_interval, recurrence_unit (enum), start_date, rotation_enabled, is_active, created_at
- `ChoreAssignee`: id, chore_id, user_id, position
- `ChoreAssignment`: id, chore_id, household_id, assigned_to_user_id, due_date, postponed_to, status (enum: pending/completed/cancelled), completed_at, completed_by_user_id, created_at

6.2. **Schemas** (`hausly/modules/chores/schemas.py`):
- `ChoreCreate`: name, start_date, is_recurring, recurrence_interval?, recurrence_unit?, assignee_user_ids, rotation_enabled?
- `ChoreUpdate`: name?, recurrence_interval?, recurrence_unit?, assignee_user_ids?, rotation_enabled?
- `ChoreResponse`: full chore with assignees
- `AssignmentResponse`: full assignment details
- `PostponeRequest`: postpone_to (date)

6.3. **Service** (`hausly/modules/chores/service.py`):
- `create_chore(household_id, user_id, data)` → validate creator in assignees, create chore + assignees, generate initial assignments
- `get_chores(household_id)` → active chores with assignees
- `get_chore(chore_id)` → with assignees
- `update_chore(chore_id, data)` → update fields, recompute assignees if changed
- `delete_chore(chore_id)` → set is_active=false, delete future pending assignments
- `get_assignments(household_id, filters)` → filter by status/user/date range
- `complete_assignment(assignment_id, user_id)` → set completed, record completer
- `postpone_assignment(assignment_id, new_date)` → only if overdue, set postponed_to
- `cancel_assignment(assignment_id)` → only if pending/overdue
- `generate_assignments(chore)` → assignment generation logic (used by cron and on-create)
- `on_member_leave(household_id, user_id)` → remove from assignees, delete future assignments, recompute rotation

6.4. **Assignment generation logic** (core algorithm):
```python
def generate_assignments(chore, assignees, existing_assignments, horizon_days=14):
    """Generate assignments up to `horizon_days` ahead. Idempotent."""
    # Check for overdue blocking
    # Calculate next_due_date from start_date + interval
    # For each due date within horizon:
    #   If rotation: pick assignee by occurrence_index % len(assignees)
    #   Else: create assignment for each assignee
    #   Skip if assignment already exists for (chore_id, due_date, assignee)
```

6.5. **Router** (`hausly/modules/chores/router.py`):
- Mount all chore endpoints with `require_module("chores")` dependency

6.6. **Migration** (`migrations/versions/006_chores.py`):
- Create `chores`, `chore_assignees`, `chore_assignments` tables with indexes and RLS

### Success Criteria
- Creator must be in assignees (validation error otherwise)
- Rotation correctly cycles through assignees
- Overdue assignment blocks new generation for that chore
- Postpone updates effective date, unblocks generation
- Anyone can complete any assignment
- Member leave correctly recomputes rotation
- One-off chore auto-deactivates when resolved

### Completed:
- Implemented Chore, ChoreAssignee, ChoreAssignment SQLModel models with enums (RecurrenceUnit, AssignmentStatus).
- Created schemas: ChoreCreate (with recurrence validation), ChoreUpdate, ChoreResponse, AssignmentResponse, PostponeRequest (future-date validation).
- Built full service layer: create_chore (creator-in-assignees validation, initial assignment generation), get_chores, get_chore, update_chore (assignee recomputation), delete_chore (deactivation + cleanup), get_assignments (multi-filter), complete_assignment (with one-off auto-deactivate), postpone_assignment, cancel_assignment, generate_assignments (idempotent, overdue blocking, rotation), on_member_leave (remove assignees, delete futures, recompute rotation, deactivate if sole).
- Router with 9 endpoints: list chores, create, get, update, delete, list assignments, complete, postpone, cancel — all gated by require_module("chores").
- Migration 006_chores: chores, chore_assignees, chore_assignments tables with indexes, FKs, and RLS policies.
- Added python-dateutil dependency for monthly recurrence (relativedelta).
- 24 unit tests covering: creation, creator validation, one-off chores, get/list, complete (any member), auto-deactivate, postpone, cancel, delete, assignments with filters, generation (one-off shared, overdue blocking, empty assignees), member leave (remove + deactivate), recurrence validation.
- All 132 tests pass (24 new + 108 existing).

---

## Phase 7 — Backend: Real-Time (SignalR) [completed]

**Goal:** Set up Azure SignalR integration to broadcast mutations to household members.

### Steps

7.1. **SignalR service** (`hausly/realtime/signalr.py`):
- Initialize Azure SignalR Management SDK client
- `broadcast_to_household(household_id, event_name, payload)` → send to group `household:{household_id}`
- Helper functions for each event type (type-safe wrappers)

7.2. **Integrate into module services:**
- Grocery service: broadcast on item_added, item_updated, item_removed, list_archived, session_completed
- Expense service: broadcast on expense created, confirmed, settled
- Meal service: broadcast on entry created, updated, removed
- Chore service: broadcast on chore created, deleted, assignment completed/updated

7.3. **SignalR hub endpoint** (negotiation):
- `POST /hubs/household/negotiate` → returns SignalR connection info for the client
- Include household_id group assignment based on authenticated user's active membership

### Success Criteria
- Client can negotiate and connect to SignalR hub
- Mutations in one client trigger events received by other connected household members
- Events contain correct payloads matching `docs/api-reference.md`

### Completed:
- Implemented `SignalRService` class in `hausly/realtime/signalr.py` with connection string parsing, JWT generation (HS256), fire-and-forget broadcasting via Azure SignalR REST API.
- Created negotiate endpoint (`POST /api/v1/hubs/household/negotiate`) returning `{ url, accessToken }` with group claim for auto-join.
- Added type-safe event wrappers for all 15 event types from api-reference.md (grocery, expense, meal, chore, member events).
- Integrated broadcasts into all four module routers (grocery, expense, meal, chores) at the router layer after successful service calls.
- Graceful degradation: broadcasts are fire-and-forget with warning logging; mutations succeed even if SignalR is down.
- 18 unit tests covering: connection string parsing, JWT generation, client token structure, broadcast mechanics (success/failure/disabled), and event wrapper correctness.
- All 165 tests pass (18 new + 147 existing).

---

## Phase 8 — Backend: Background Jobs (Cron) [completed]

**Goal:** Implement recurring expense generation and chore assignment generation as scheduled tasks.

### Steps

8.1. **Recurring expense job** (`hausly/jobs/recurring_expenses.py`):
- Run daily (or on app startup + scheduled)
- For each recurring expense where `next_occurrence_date <= today`:
  - Skip if 3+ unconfirmed drafts exist (staleness cap)
  - Create draft expense with same splits
  - Advance `next_occurrence_date` per RRULE
  - Notify household members

8.2. **Chore assignment generation job** (`hausly/jobs/chore_assignments.py`):
- Run daily (or on app startup + scheduled)
- For each active recurring chore:
  - Skip if has unresolved overdue assignment
  - Generate assignments up to 14 days ahead (idempotent)

8.3. **Job runner** (`hausly/jobs/__init__.py`):
- Use `apscheduler` or FastAPI's `on_event("startup")` with `asyncio` background tasks
- Both jobs run daily at a configurable time (default: 02:00 UTC)

### Success Criteria
- Recurring expenses generate drafts correctly on schedule
- Staleness cap (3 unconfirmed) pauses generation
- Chore assignments generated for 2-week rolling window
- Overdue blocking prevents new assignments for that chore
- Jobs are idempotent (safe to re-run)

### Completed:
- Implemented `process_recurring_expenses` in `hausly/jobs/recurring_expenses.py`: queries due recurring expenses, enforces staleness cap (3 unconfirmed drafts), clones template splits into draft expenses, advances `next_occurrence_date` per RRULE parsing.
- Implemented `process_chore_assignments` in `hausly/jobs/chore_assignments.py`: iterates active recurring chores, loads assignees, delegates to existing `generate_assignments` service (which handles overdue blocking and idempotency).
- Implemented job scheduler in `hausly/jobs/__init__.py` using APScheduler `AsyncIOScheduler` with `CronTrigger` (02:00 and 02:05 UTC). Runs both jobs at startup for catch-up. Integrated via FastAPI lifespan context manager.
- Wired `lifespan_jobs` into `hausly/main.py` as the app lifespan handler.
- 16 unit tests covering: RRULE parsing, date advancement, draft generation, staleness cap, missing recurrence_rule handling, chore assignment generation, overdue blocking, no-assignees skip, empty-state handling, idempotency (date advancement verification).
- All 194 tests pass (16 new + 178 existing).

---

## Phase 9 — Mobile: Project Setup & Auth [completed]

**Goal:** Configured Expo project with Firebase auth, API client, and navigation shell.

### Steps

9.1. **Firebase setup** (`services/firebase.ts`):
- Initialize Firebase Auth with Expo config
- Google Sign-In and Apple Sign-In providers
- `signIn()`, `signOut()`, `onAuthStateChanged()` hooks
- Token retrieval for API calls

9.2. **API client** (`services/api.ts`):
- Typed HTTP client (fetch or axios)
- Base URL from config
- Auto-inject Firebase token in Authorization header
- Response/error interceptors
- Type-safe request/response (from `packages/types`)

9.3. **Auth flow** (`app/(auth)/`):
- `login.tsx`: Google/Apple sign-in buttons
- `register.tsx`: same as login (Firebase handles both)
- `onboarding.tsx`: household type selection + create/join flow

9.4. **Auth state management** (`hooks/useAuth.ts`):
- Track auth state (loading, authenticated, unauthenticated)
- Persist token for offline use
- Redirect logic: unauthenticated → login, no household → onboarding

9.5. **TanStack Query setup** (`providers/QueryProvider.tsx`):
- Configure QueryClient with sensible defaults
- Online/offline detection

### Success Criteria
- User can sign in with Google/Apple
- Auth state persists across app restarts
- API calls include valid auth token
- Unauthenticated users see login screen

### Completed:
- Implemented Firebase Auth service with Google/Apple sign-in, sign-out, token retrieval, and auth state listener.
- Built typed API client with auto-injected Firebase Bearer token and error handling.
- Created auth flow screens: login (Google/Apple buttons), register (redirect to login), onboarding (create/join household).
- Implemented `useAuth` hook and `AuthProvider` context for shared auth state management.
- Set up TanStack Query provider with sensible defaults (stale time, GC, retry).
- Wired root layout with auth guard: redirects unauthenticated → login, authenticated without household → onboarding.
- TypeScript strict mode passes with zero errors.

---

## Phase 10 — Mobile: Navigation & Shared UI [completed]

**Goal:** Tab navigation, design system primitives, and household context.
Focus on clean, friendly UI/UX.

### Steps

10.1. **Layout** (`app/_layout.tsx`):
- Root layout with auth guard
- QueryProvider + Zustand providers wrapping the app

10.2. **Tab navigation** (`app/(tabs)/`):
- Bottom tabs: Home, Grocery, Expenses, Meals, Chores
- Tab icons and labels
- Conditionally show tabs based on enabled_modules from household settings

10.3. **UI primitives** (`components/ui/`):
- `Button.tsx` — primary, secondary, destructive variants
- `Card.tsx` — standard card container
- `Sheet.tsx` — bottom sheet (for create/edit flows)
- `Input.tsx` — text input with label and error state
- `Avatar.tsx` — user avatar with fallback initials
- `LoadingSpinner.tsx`
- `EmptyState.tsx` — placeholder for empty lists
- Co-locate styles: `Component.styles.ts` next to each component

10.4. **Household context** (`hooks/useHousehold.ts`, `stores/householdStore.ts`):
- Zustand store: current household, members, settings
- `useHousehold()` hook for components
- Fetch household data on app load, cache with TanStack Query

10.5. **SignalR client** (`services/signalr.ts`):
- Connect to Azure SignalR after auth
- Join household group
- Event listeners that invalidate relevant TanStack Query caches

### Success Criteria
- Tab navigation works with correct icons
- UI primitives render correctly
- Household data loaded and available to all screens
- SignalR connection established and events received

### Completed:
- Created tab layout (`app/(tabs)/_layout.tsx`) with bottom tabs (Home, Grocery, Expenses, Meals, Chores), conditional visibility driven by `household.settings.enabled_modules` from Zustand store.
- Built design tokens file (`constants/theme.ts`) with colors, spacing, borderRadius, shadows, and typography primitives. Applied "Soft Pop" theme (see `docs/design-system.md`): indigo-violet primary, per-module accent colors, semantic shadow system, refined border radii.
- Implemented 7 UI primitives in `components/ui/`: Button (3 variants + size + loading), Card (with elevation), Sheet (bottom modal), Input (label + error + focus), Avatar (image + initials fallback), LoadingSpinner, EmptyState. All co-located with `.styles.ts`.
- Implemented household Zustand store (`stores/householdStore.ts`): id, name, inviteCode, members, settings with set/clear actions.
- Created `useHousehold` hook (`hooks/useHousehold.ts`): fetches via TanStack Query, syncs result into Zustand store.
- Implemented full SignalR client (`services/signalr.ts`): negotiate, connect/disconnect, automatic reconnect, 15 event handlers that invalidate relevant query caches (grocery, expense, meal, chore, member events).
- Zero TypeScript errors across all new files.

---

## Phase 11 — Mobile: Household Management [completed]

**Goal:** Create/join household flows, member list, settings, leave flow.

### Steps

11.1. **Onboarding flow** (`app/(auth)/onboarding.tsx`):
- Step 1: "Create new household" or "Join existing"
- Create path: name input → type selection → module defaults → confirm
- Join path: invite code input → preview → confirm

11.2. **Household settings screen**:
- Display household name, type, invite code (copy button)
- Module toggles (admin only)
- Member list with roles
- "Leave Group" button

11.3. **Member management** (admin only):
- Change role (member ↔ admin)
- Remove member (with guided flow data)

11.4. **Leave flow** (guided):
- Fetch leave data (unsettled expenses, pending chores)
- Step through resolution: settle/forgive expenses, reassign chores
- Final confirmation

### Success Criteria
- User can create a household and see it on home screen
- User can join via invite code
- Admin can manage members and settings
- Leave flow presents unsettled data before confirming

### Completed:
- Enhanced onboarding with multi-step creation (name → household type picker) and join (code → preview → confirm) using TanStack Query mutations.
- Built household settings screen: household info, invite code sharing, module toggles (admin-only), member list with role badges, leave button.
- Created admin member management screen with role change and removal (with confirmation alerts).
- Implemented guided leave flow: fetches outstanding items preview, displays unsettled expenses/pending chores, final confirmation alert.
- Created `useHouseholdMutations` hook with all household mutations (create, join, update, settings, role, remove, leave, regenerate code, preview).
- Added Settings tab to navigation with nested stack layout.
- All production TypeScript passes type checking.

---

## Phase 11.5 — Mobile: Global Actions (User-Level Header Buttons) [completed]

**Goal:** Add persistent user-level header buttons (avatar + three-dots menu) across all tab screens, with modal screens for profile, developer info, recipes (v2 placeholder), and preferences (placeholder).

**Plan:** `docs/planning/global-actions-plan.md`

### Steps

11.5.1. **GlobalActions header component** (`components/GlobalActions.tsx`):
- Two `Pressable` buttons in `headerRight`: user avatar (28px, initials) + three-dots icon (Ionicons)
- Avatar navigates to profile modal; three-dots opens bottom Sheet with 4 menu items

11.5.2. **Modal route group** (`app/(modals)/`):
- Stack layout with `presentation: "modal"` — automatic back arrow on all screens
- Profile: avatar (80px), display name, email, current household (read-only)
- Dev Info: app version (expo-constants), API version, platform, environment
- My Recipes: EmptyState placeholder (v2 scope)
- Preferences: EmptyState placeholder (no UserSettings API yet)

11.5.3. **Wiring:**
- `headerRight: () => <GlobalActions />` in tabs screenOptions and settings nested Stack
- `(modals)` registered in root Stack
- i18n strings added to `i18n/en.json`

### Success Criteria
- Avatar + three-dots visible on all tab headers (right-aligned)
- Sheet opens with Developer Info, My Recipes, Preferences, Log Out
- Log Out shows confirmation alert before calling `signOut()`
- All 4 modal screens render correctly with back navigation
- Zero TypeScript errors

### Completed:
- Created `GlobalActions` component with avatar button + three-dots Sheet menu (4 items).
- Created `(modals)` route group with 4 modal screens: profile, dev-info, recipes, preferences.
- Wired `headerRight` into tabs layout and settings nested Stack.
- Registered `(modals)` in root layout. Added i18n strings.
- Zero new dependencies. Zero TypeScript errors.

---

## Phase 12 — Mobile: Grocery Module [completed]

**Goal:** Shared grocery list with real-time sync, personal items, and shopping session.

### Steps

12.1. **Grocery list screen** (`app/(tabs)/grocery.tsx`):
- Display active list items
- Add item (inline input or sheet)
- Edit item (tap to edit)
- Delete item (swipe or long-press)
- Visual marker for personal items
- Filter: show/hide personal items

12.2. **TanStack Query hooks** (`hooks/useGrocery.ts`):
- `useGroceryItems(household_id)` → fetch + cache items
- `useAddItem()` → mutation + optimistic update
- `useUpdateItem()` → mutation
- `useDeleteItem()` → mutation
- SignalR events invalidate the query cache

12.3. **Shopping session mode**:
- "Start Shopping" button → enter session mode
- Items become checkable (tap to toggle)
- Session state in Zustand store (local only)
- "Done" → summary screen
- Summary: checked shared items, checked personal items, receipt total input, create expense toggle
- "Confirm" → call `POST /grocery/session/complete`
- Show resulting draft expense link

12.4. **Offline support** (`stores/groceryStore.ts`):
- Pending operations queue for offline mutations
- Sync on reconnect
- Session "Done" while offline: store payload locally, sync when online

12.5. **Clear list action**:
- "Clear List" with confirmation dialog
- Calls archive endpoint

### Completed:
- Implemented grocery list screen with FlatList, item rendering, and personal item markers.
- Built TanStack Query hooks with optimistic updates for add/update/delete/session-complete/archive.
- Implemented shopping session mode with Zustand store (start, toggle, done, cancel).
- Built session summary screen with shared/personal split, receipt total input, and expense toggle.
- Added offline support via pending operations queue in Zustand store.
- Clear list action with confirmation dialog calls archive endpoint.
- Components: GroceryHeader, GroceryItemRow, AddItemInput, SessionSummary with co-located styles.
- 15 unit tests passing (store + extracted logic).

### Success Criteria
- Items sync in real-time between devices
- Personal items visible only to owner (hidden) or marked (visible)
- Shopping session → expense draft flow works end-to-end
- Offline add/session works and syncs on reconnect

---

## Phase 13 — Mobile: Expense Module [completed]

**Goal:** Expense tracking with splits, balances, settlement, and draft confirmation.

### Steps

13.1. **Expense list screen** (`app/(tabs)/expense.tsx`):
- List of expenses (confirmed + drafts)
- Filter by status, category, date
- Balance summary widget at top

13.2. **Create expense flow** (sheet/modal):
- Amount input
- Title input
- Paid by selector (defaults to current user)
- Participant selector (checkboxes for household members)
- Split mode toggle: Equal / Custom / Percentage
- Equal: auto-calculate per-person
- Custom: manual amount per person (validate sum)
- Percentage: manual % per person (validate 100%)
- Save as draft or confirm

13.3. **Expense detail screen**:
- Show amount, payer, splits
- Confirm button (if draft)
- Edit button (if draft)

13.4. **Balance & settlement screens**:
- Balance summary: net amount per member pair
- Settle up: suggested transactions from settlement endpoint
- "Mark as settled" per transaction

13.5. **Draft confirmation cards**:
- Push notification or in-app badge for pending drafts
- Draft card with Edit/Discard/Confirm actions

13.6. **TanStack Query hooks** (`hooks/useExpenses.ts`):
- `useExpenses(household_id, filters)`
- `useBalances(household_id)`
- `useSettlements(household_id)`
- Mutations for create, confirm, settle
- SignalR events invalidate caches

### Success Criteria
- Create expense with all split modes works
- Balance calculation matches server
- Draft→confirm flow works
- Grocery-generated drafts appear for confirmation
- Settlement suggestions display correctly

### Completed:
- Implemented full expense list screen with tab navigation (Expenses, Balances, Settlements) and status filter chips (All, Draft, Confirmed).
- Built CreateExpenseSheet with amount input, title, category, paid-by selector, participant checkboxes, and three split modes (Equal with remainder handling, Custom with sum validation, Percentage with 100% validation). Save as draft or confirm.
- Created ExpenseDetail bottom sheet showing amount, status badge, source tag, payer, category, date, per-split breakdown with settled/unsettled status, and Confirm/Delete actions for drafts.
- Built BalanceSummary component showing net amounts per member pair with color-coded owed/owed-to direction.
- Built SettlementList component with suggested transactions and per-suggestion "Settle" button that settles relevant splits.
- Implemented `hooks/useExpenses.ts` with 7 TanStack Query hooks: useExpenses (with filters), useExpense, useBalances, useSettlements, useCreateExpense, useConfirmExpense, useDeleteExpense, useUpdateExpense, useSettleSplit — all with proper cache invalidation.
- Implemented `stores/expenseStore.ts` Zustand store for local UI state: form state, selected expense, status filter, active tab.
- Created 6 expense components with co-located styles in `components/expense/`.
- 19 new tests (7 store + 12 split logic) all passing. Full mobile suite: 94/95 pass (1 pre-existing SignalR failure unrelated).
- Zero TypeScript errors in all new files.

---

## Phase 14 — Mobile: Meal Planner Module [completed]

**Goal:** Weekly diary view with slot claiming and headcount.

### Steps

14.1. **Meal planner screen** (`app/(tabs)/meal.tsx`):
- Weekly view: 7 days × 2 slots (lunch/dinner)
- Each slot shows: text + owner name (or empty/claimable)
- Swipe or button to navigate weeks
- Tap empty slot → create entry
- Tap owned slot → view/edit (if owner or admin)

14.2. **Create/Edit entry** (sheet):
- Date + slot (pre-filled from tapped cell)
- Text input (what to eat)
- Headcount stepper (default: household member count)
- Save → `POST /meals`

14.3. **TanStack Query hooks** (`hooks/useMeals.ts`):
- `useMealEntries(household_id, start, end)` → weekly fetch
- `useCreateMeal()` → mutation (handle 409 conflict)
- `useUpdateMeal()` → mutation (owner/admin only)
- `useDeleteMeal()` → mutation
- SignalR events refresh weekly data

### Success Criteria
- Weekly view displays correctly
- First-come-first-served: 409 shown as friendly message
- Only owner/admin can edit/delete
- Headcount defaults correctly

### Completed:
- Implemented weekly diary view with day-by-day layout (Mon–Sun) and lunch/dinner slot cards.
- MealEntrySheet handles create (with 409 conflict alert) and edit (owner/admin guarded).
- Headcount defaults to household member count via Zustand store.
- TanStack Query hooks fetch by date range and invalidate on mutations.
- SignalR event handlers were already wired from Phase 7.
- 10 unit tests pass covering week computation, slot lookup, and permission logic.

---

## Phase 15 — Mobile: Chore Module

**Goal:** Chore list, creation, assignments, overdue handling, and completion.

### Steps

15.1. **Chore list screen** (`app/(tabs)/chores.tsx`):
- Assignments grouped by date: Today, Tomorrow, This Week, Overdue
- Each card shows: chore name, assignee, due date
- Overdue cards highlighted with action buttons

15.2. **Create chore flow** (sheet):
- Name input
- Start date picker
- Recurring toggle → interval + unit selectors
- Assignee selector (multi-select, creator must be included)
- Rotation toggle (if >1 assignee)
- Preview: "Your turn every X [unit]"

15.3. **Chore detail & management**:
- View chore definition + assignee list
- Edit chore (name, recurrence, assignees)
- Delete chore (any member, with confirmation)

15.4. **Assignment actions**:
- "Mark as Done" button on any assignment → calls complete endpoint
- Overdue actions: Done / Postpone (date picker) / Cancel
- Completion shows "Completed by [name]" tag

15.5. **TanStack Query hooks** (`hooks/useChores.ts`):
- `useChores(household_id)` → chore definitions
- `useAssignments(household_id, filters)` → assignments for display
- Mutations: create, update, delete chore; complete, postpone, cancel assignment
- SignalR events refresh data

### Success Criteria
- Assignments display grouped by date
- Create chore validates creator in assignees
- Rotation preview shows correct frequency
- Complete/postpone/cancel work
- Overdue blocking visible (no new assignments generated)

---

## Phase 16 — Integration Testing & Polish

**Goal:** End-to-end flows work correctly, cross-module integration verified.

### Steps

16.1. **Backend integration tests** (`apps/api/tests/`):
- Auth flow: token verify, user creation
- Household lifecycle: create → join → leave
- Grocery→Expense chain: add items → session complete → draft expense → confirm
- Recurring expense generation (mock clock)
- Chore assignment generation + overdue blocking
- RLS tests: verify cross-household isolation

16.2. **Cross-module integration verification**:
- Shopping session → draft expense → balance update
- Member leave → chore reassignment + expense resolution prompt
- Meal entry headcount defaults to member count

16.3. **Error handling & edge cases**:
- Network errors show user-friendly messages
- Optimistic updates rollback on failure
- Concurrent slot claiming (meal planner) shows conflict message
- Empty states for all lists

16.4. **Performance baseline**:
- API response time < 200ms for standard queries
- SignalR event delivery < 500ms
- App cold start < 3s

### Success Criteria
- All integration tests pass
- Cross-module flows work end-to-end
- No broken states on network errors
- App is usable with poor connectivity (offline queuing works)

---

## Appendix A — Environment Variables

```env
# Backend
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/hausly
FIREBASE_PROJECT_ID=hausly-dev
FIREBASE_SERVICE_ACCOUNT_PATH=./firebase-sa.json
SIGNALR_CONNECTION_STRING=Endpoint=https://...
AI_PROVIDER=azure_openai  # unused in v1, but wired
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_KEY=sk-...
CORS_ORIGINS=http://localhost:8081

# Mobile
EXPO_PUBLIC_API_URL=http://localhost:8000/api/v1
EXPO_PUBLIC_FIREBASE_API_KEY=...
EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN=...
EXPO_PUBLIC_FIREBASE_PROJECT_ID=hausly-dev
EXPO_PUBLIC_SIGNALR_URL=https://...
```

---

## Appendix B — Key Constraints Checklist

Before marking any phase complete, verify:

- [ ] All financial mutations produce drafts requiring user confirmation
- [ ] All DB queries scoped by household_id
- [ ] No `any` types without inline justification
- [ ] No raw ORM objects returned from API
- [ ] All async I/O uses await
- [ ] SignalR broadcasts on every mutation
- [ ] Module access gated by enabled_modules check
- [ ] Personal items excluded from expense generation
- [ ] Payer included in splits array
- [ ] sum(splits) == expense.amount validated server-side
