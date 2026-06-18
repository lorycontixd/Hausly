# API Reference

> Derived from docs/planning/hausly-project-master-plan.md.
> This is a **planning draft** — exact schemas will be generated from FastAPI's OpenAPI spec once code lands.

---

## Conventions

- Base URL: `/api/v1`
- Auth: Firebase Auth JWT in `Authorization: Bearer <token>` header. All endpoints require auth unless noted.
- Household context: Most endpoints require `household_id` path param or derive it from the authenticated user's active membership.
- Response envelope: `{ "data": ..., "meta": { ... } }` for collections; raw object for single items.
- Errors: `{ "detail": "message", "code": "ERROR_CODE" }`
- Pagination: cursor-based via `?cursor=<opaque>&limit=<int>` on list endpoints.

---

## Auth

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/verify` | Verify Firebase token, return Hausly user profile + active households. Creates user row on first call. |
| POST | `/auth/refresh` | Exchange a Firebase refresh token for a new ID token. Proxies Firebase token refresh so the client has a single backend entrypoint. |

**Verify request:** empty body (token in header).
**Verify response:** `{ user_id, display_name, email, households: [{ id, name, role }] }`

**Refresh request:** `{ refresh_token }`
**Refresh response:** `{ id_token, refresh_token, expires_in }`

Note: Login and logout are handled entirely by the Firebase Auth SDK on the client (Google, Apple, or email+password). The backend only verifies/refreshes tokens — it does not manage sessions or distinguish between sign-in providers.

---

## Households

| Method | Path | Description |
|--------|------|-------------|
| POST | `/households` | Create household. Caller becomes admin. Creates HouseholdSettings atomically. |
| GET | `/households/{household_id}` | Get household details (includes settings). |
| PATCH | `/households/{household_id}` | Update name, type (admin only). |
| PATCH | `/households/{household_id}/settings` | Update household settings: enabled_modules, default_currency, notification_level (admin only). |
| GET | `/invites/{code}/preview` | Preview household before joining. Returns name + member count. **No auth required.** |
| POST | `/households/join` | Join via invite code. Server resolves household from code. |
| POST | `/households/{household_id}/leave` | Leave household (triggers guided flow data). |
| GET | `/households/{household_id}/members` | List active members. |
| DELETE | `/households/{household_id}/members/{user_id}` | Admin removes a member. |
| PATCH | `/households/{household_id}/members/{user_id}/role` | Change member role (admin only). |
| POST | `/households/{household_id}/invite-code/regenerate` | Regenerate invite code (admin only). |

**Create request:** `{ name, type }`

Note: `enabled_modules` is stored in `HouseholdSettings` (created atomically with Household). On create, module defaults are inferred from `type`. Managed via `PATCH /households/{household_id}/settings`.

**Preview response (unauthenticated):** `{ household_name, member_count, type }`
**Join request:** `{ invite_code }`
**Join constraint (v1):** Server rejects join if the user already has an active household membership. Returns `409 { "code": "ALREADY_IN_HOUSEHOLD" }`.
**Leave response:** `{ unsettled_expenses: [...], pending_chores: [...] }` — client uses this to present the guided flow.

---

## Grocery

| Method | Path | Description |
|--------|------|-------------|
| GET | `/households/{household_id}/grocery/lists` | Get active + archived lists. |
| GET | `/households/{household_id}/grocery/lists/{list_id}/items` | Get items in a list. Filters hidden personal items for non-owners. |
| POST | `/households/{household_id}/grocery/items` | Add item(s) to active list. |
| PATCH | `/households/{household_id}/grocery/items/{item_id}` | Update item (name, quantity, unit, is_personal, personal_visibility). |
| DELETE | `/households/{household_id}/grocery/items/{item_id}` | Remove item. |
| POST | `/households/{household_id}/grocery/session/complete` | Complete shopping session: mark items as bought, remove from list, create draft expense. |
| POST | `/households/{household_id}/grocery/lists/archive` | Archive current list ("Clear list"). Requires confirmation. Does NOT trigger expense. |

**Add item request:** `{ name, quantity?, unit?, source?, is_personal?, personal_visibility? }`

**Session complete request:**
```json
{
  "bought_item_ids": ["uuid", "uuid", ...],
  "receipt_total": 45.60,
  "create_expense": true
}
```

**Session complete response:**
```json
{
  "items_removed": 8,
  "expense_draft_id": "uuid",
  "expense_draft": { ... }
}
```

**Behaviour:**
- `bought_item_ids` lists the items checked during the shopping session.
- Non-personal items in `bought_item_ids` are marked as bought and removed from the active list.
- Personal items in `bought_item_ids` are marked as bought and removed but excluded from the expense.
- If `create_expense = true`: a draft expense is created with `receipt_total` as amount, item names as description, and an equal split across all active household members.
- If `create_expense = false`: items are removed but no expense is generated.

**Archive request:** empty body. Server requires client to pass `{ confirm: true }` to prevent accidental clears.

---

## Expenses

| Method | Path | Description |
|--------|------|-------------|
| GET | `/households/{household_id}/expenses` | List expenses (filter: status, category, date range). |
| POST | `/households/{household_id}/expenses` | Create expense (starts as draft or confirmed). |
| GET | `/households/{household_id}/expenses/{expense_id}` | Get expense with splits. |
| PATCH | `/households/{household_id}/expenses/{expense_id}` | Update expense (draft only). |
| POST | `/households/{household_id}/expenses/{expense_id}/confirm` | Confirm a draft expense. Activates balance impact. |
| DELETE | `/households/{household_id}/expenses/{expense_id}` | Delete (draft only; confirmed expenses are archived). |
| GET | `/households/{household_id}/expenses/balances` | Outstanding balances between all members. |
| GET | `/households/{household_id}/expenses/settlements` | Suggested settlement transactions (minimize count). |
| POST | `/households/{household_id}/expenses/splits/{split_id}/settle` | Mark a split as settled. |

**Create request:**
```json
{
  "title": "Groceries",
  "amount": 45.60,
  "currency": "EUR",
  "category": "food",
  "paid_by_user_id": "uuid",
  "splits": [
    { "user_id": "uuid", "share_amount": 22.80 },
    { "user_id": "uuid", "share_amount": 22.80 }
  ],
  "status": "draft",
  "source": "grocery_integration"
}
```

**Constraint:** Auto-generated expenses (recurring, grocery integration) always start as `draft`. The client must call `/confirm` after user review.

---

## Meal Planner

| Method | Path | Description |
|--------|------|-------------|
| GET | `/households/{household_id}/meals` | Get entries for a date range (?start=&end=). |
| POST | `/households/{household_id}/meals` | Claim a meal slot. Fails with 409 if slot already taken. |
| PATCH | `/households/{household_id}/meals/{entry_id}` | Update text, headcount, or linked recipe. **Owner or admin only.** |
| DELETE | `/households/{household_id}/meals/{entry_id}` | Remove entry. **Owner or admin only.** |
| POST | `/households/{household_id}/meals/push-ingredients` | Push linked recipe ingredients to grocery list (single entry). |
| POST | `/households/{household_id}/meals/generate-shopping-list` | Consolidate all linked-recipe entries for a week into a shopping list preview. |

**Create request:** `{ date, slot, text, headcount?, linked_recipe_id? }`
**Create constraint:** Returns `409 CONFLICT` if an entry already exists for (household_id, date, slot). The existing owner must delete their entry before another member can claim the slot.
**Ownership:** `owner_user_id` is set to the authenticated caller. Only the owner or a household admin can PATCH or DELETE.
**Push ingredients response:** `{ items_added: [...], duplicates_skipped: [...] }`
**Generate shopping list response:** `{ consolidated_items: [{ name, total_quantity, unit }] }` — client displays for review before adding to grocery list.

---

## Recipes (v2)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/users/me/recipes` | List authenticated user's recipes. |
| POST | `/users/me/recipes` | Create a recipe. |
| GET | `/users/me/recipes/{recipe_id}` | Get recipe with ingredients. |
| PATCH | `/users/me/recipes/{recipe_id}` | Update recipe. |
| DELETE | `/users/me/recipes/{recipe_id}` | Delete recipe. |
| POST | `/users/me/recipes/{recipe_id}/fork` | Fork another user's recipe to own book. |
| GET | `/households/{household_id}/recipes` | Browse recipes from all household members (read-only). |

**Create request:**
```json
{
  "name": "Pasta al pomodoro",
  "base_servings": 4,
  "notes": "Optional instructions",
  "ingredients": [
    { "name": "spaghetti", "quantity": 400, "unit": "g" },
    { "name": "olive oil", "quantity": null, "unit": null }
  ]
}
```

**Note:** Recipes are user-scoped, not household-scoped. No `household_id` in recipe CRUD.

---

## Chores

| Method | Path | Description |
|--------|------|-------------|
| GET | `/households/{household_id}/chores` | List active chores with assignees. |
| POST | `/households/{household_id}/chores` | Create a chore (any member). |
| GET | `/households/{household_id}/chores/{chore_id}` | Get chore detail with assignees. |
| PATCH | `/households/{household_id}/chores/{chore_id}` | Update chore (name, recurrence, assignees). |
| DELETE | `/households/{household_id}/chores/{chore_id}` | Delete chore (any member). Deactivates + removes future assignments. |
| GET | `/households/{household_id}/chores/assignments` | List assignments (filter: status, user, date range). |
| POST | `/households/{household_id}/chores/assignments/{id}/complete` | Mark assignment as done (any member). |
| POST | `/households/{household_id}/chores/assignments/{id}/postpone` | Postpone overdue assignment to a new date. |
| POST | `/households/{household_id}/chores/assignments/{id}/cancel` | Cancel an overdue assignment. |

**Create request:**
```json
{
  "name": "Clean house",
  "start_date": "2026-06-08",
  "is_recurring": true,
  "recurrence_interval": 1,
  "recurrence_unit": "weeks",
  "assignee_user_ids": ["uuid-a", "uuid-b", "uuid-c"],
  "rotation_enabled": true
}
```

**Constraint:** Caller's user_id must be in `assignee_user_ids`. Server generates initial assignments immediately on creation.

**Complete request:** empty body. Server records `completed_by_user_id` = caller.
**Postpone request:** `{ "postpone_to": "2026-06-10" }`. Only valid on overdue assignments.
**Cancel request:** empty body. Only valid on pending (including overdue) assignments.

**Assignment generation:** Daily cron generates assignments up to 2 weeks ahead. Overdue assignments block generation for that chore.

---

## Pinboard (v2)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/households/{household_id}/pinboard` | List notes (pinned first, then by created_at desc). |
| POST | `/households/{household_id}/pinboard` | Create note. |
| PATCH | `/households/{household_id}/pinboard/{note_id}` | Update content, pin status, expiry. |
| DELETE | `/households/{household_id}/pinboard/{note_id}` | Delete note (author or admin). |

**Create request:** `{ content, photo_url?, is_pinned?, expires_at? }`

---

## AI Endpoints (v3, paid tier only)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/households/{household_id}/ai/scan-receipt` | Upload receipt image → OCR → draft expense. |
| POST | `/households/{household_id}/ai/suggest-meal-plan` | Generate weekly meal plan from constraints. |
| POST | `/households/{household_id}/ai/parse-grocery-input` | NLP text → structured grocery items. |
| POST | `/users/me/recipes/ai/suggest-ingredients` | Recipe name → suggested ingredient list. |
| POST | `/users/me/recipes/ai/import-url` | URL → extracted recipe draft. |

**All AI responses** return drafts/proposals. The client must present them for user review and call the normal CRUD endpoint to commit.

**Auth guard:** Server rejects AI calls from free-tier households with `403 { "code": "TIER_REQUIRED", "detail": "..." }`.

---

## Real-Time (WebSocket via Azure SignalR)

### Connection

Client connects to the SignalR hub at `/hubs/household` after auth. Server assigns the connection to a group named `household:{household_id}`.

### Events (Server → Client)

| Event | Payload | Trigger |
|-------|---------|---------|
| `grocery_item_added` | `{ item }` | New item added to active list |
| `grocery_item_updated` | `{ item }` | Item modified (bought, edited) |
| `grocery_item_removed` | `{ item_id }` | Item deleted |
| `grocery_list_archived` | `{ list_id }` | List cleared/archived |
| `grocery_session_completed` | `{ bought_item_ids, expense_draft_id? }` | Shopping session completed |
| `expense_created` | `{ expense }` | New expense (draft or confirmed) |
| `expense_confirmed` | `{ expense_id }` | Draft confirmed |
| `expense_settled` | `{ split_id }` | Split marked settled |
| `meal_entry_created` | `{ entry }` | Meal entry created |
| `meal_entry_updated` | `{ entry }` | Meal entry updated |
| `meal_entry_removed` | `{ entry_id }` | Meal entry deleted |
| `chore_created` | `{ chore }` | New chore created |
| `chore_deleted` | `{ chore_id }` | Chore deleted |
| `assignment_completed` | `{ assignment_id, completed_by }` | Chore marked done |
| `assignment_updated` | `{ assignment }` | Assignment postponed or cancelled |
| `member_joined` | `{ user }` | New member joined household |
| `member_left` | `{ user_id }` | Member left |
| `household_settings_updated` | `{ ...settings }` | Household settings changed |

### Events (Client → Server)

Mutations go through REST. The SignalR channel is **read-only** for clients — it broadcasts changes initiated via the API. This keeps the mutation path auditable and prevents dual-write complexity.

---

## Rate Limits

| Tier | AI endpoints | Standard endpoints |
|------|-------------|-------------------|
| Free | Blocked (403) | 100 req/min per user |
| Paid | 30 receipt scans/mo, 4 meal plans/mo, 20 ingredient extractions/mo | 300 req/min per user |

---

## Error Codes

| Code | HTTP | Meaning |
|------|------|---------|
| `NOT_FOUND` | 404 | Resource doesn't exist or not in caller's household |
| `FORBIDDEN` | 403 | Role insufficient or tier restriction |
| `TIER_REQUIRED` | 403 | Feature requires paid tier |
| `VALIDATION_ERROR` | 422 | Request body fails schema validation |
| `CONFLICT` | 409 | Duplicate or invalid state transition |
| `EXPENSE_NOT_DRAFT` | 409 | Attempt to edit a confirmed expense |
