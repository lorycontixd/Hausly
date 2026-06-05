# Grocery Shopping Session — Logic & Behaviour

> Describes how the shopping session works end-to-end: client-side state, completion flow, expense integration, personal items, and offline handling.
- Read: false
- Approved: false
- Notes: NA
---

## Overview

A "shopping session" is a **client-side UI mode** where a user checks off items from the grocery list as they shop. There is no server-side session entity — the session exists only as local state on the user's device.

The session ends when the user clicks "Done", which triggers a single API call that:
1. Removes checked items from the grocery list
2. Optionally creates a draft expense with the receipt total

---

## Session Lifecycle

### Starting a Session

- User opens the grocery list and taps "Start Shopping" (or equivalent)
- Client enters session mode: items become checkable (tap to check/uncheck)
- No server call on session start — purely client-side state
- Other users continue to see the normal list; they are unaware a session is in progress

### During a Session

- User checks items as they pick them up in the store
- Checked items are stored in local state (array of `item_id`)
- The list remains live: if another user adds/removes items via SignalR, the local list updates accordingly
- Personal items (both visible and hidden owned by the user) appear in the session and can be checked

### Ending a Session — "Done" Button

1. User taps "Done"
2. Client shows a summary screen:
   - List of checked non-personal items (these will be shared expense items)
   - List of checked personal items (these will NOT be in the expense)
   - Total item count
   - Input field: "Receipt total" (numeric, required if `create_expense = true`)
   - Toggle: "Create shared expense" (default: on)
3. User enters the receipt total and confirms
4. Client calls `POST /grocery/session/complete` with:
   - `bought_item_ids`: all checked item IDs
   - `receipt_total`: the entered amount
   - `create_expense`: boolean

### Cancelling a Session

- User can cancel the session at any time (no server call)
- All checked state is discarded
- List returns to normal view

---

## Server Behaviour on Session Complete

When `POST /grocery/session/complete` is received:

1. **Mark items as bought:** set `is_bought = true`, `bought_by_user_id`, `bought_at` for all `bought_item_ids`
2. **Remove from active list:** set `is_archived = true` on bought items (they leave the active list but remain in DB for history)
3. **Personal item handling:** personal items in `bought_item_ids` are archived like other items but excluded from step 4
4. **Create draft expense (if `create_expense = true`):**
   - `title`: "Groceries — {n} items" (where n = non-personal checked count)
   - `amount`: `receipt_total`
   - `currency`: from `HouseholdSettings.default_currency`
   - `paid_by_user_id`: the authenticated user
   - `splits`: equal split across ALL active household members
   - `status`: `draft`
   - `source`: `grocery_integration`
   - Description/notes field: comma-separated list of non-personal item names
5. **Broadcast via SignalR:** `grocery:items_bought` event with list of removed item IDs

---

## Personal Items in Sessions

| Item State | Visible in Session | Included in Expense | Removed on Done |
|------------|-------------------|--------------------|-----------------| 
| Non-personal | Yes | Yes | Yes (if checked) |
| Personal (visible) | Yes (with marker) | No | Yes (if checked) |
| Personal (hidden, owned by user) | Yes (only to owner) | No | Yes (if checked) |
| Personal (hidden, owned by OTHER user) | No | No | N/A |

**Key rule:** Personal items are always excluded from expense generation regardless of visibility setting. They are removed from the list when checked, but their cost is the owner's responsibility.

---

## Simultaneous Shopping

If two members shop at the same time (both have active sessions):

- Each session is independent (client-side only)
- First "Done" to reach the server wins for overlapping items
- If both check the same item: first `session/complete` call archives it; second call silently skips items that are already archived (no error)
- Each generates their own draft expense (if enabled)
- Users resolve any overlap in the expense draft review step (merge, adjust amounts, discard one)

This is acceptable for households of 2–6 people where simultaneous shopping is rare and socially resolvable.

---

## Offline Behaviour

When the user has no internet connection during a shopping session:

1. **Session proceeds normally:** checking items is local state, no server calls needed
2. **On "Done" click (offline):**
   - Client stores the complete payload locally in the `pending_operations` queue
   - A message informs the user: "You're offline. The shopping will be saved when you reconnect."
   - Items appear checked/greyed in the local list
3. **On connectivity restoration:**
   - Client sends `POST /grocery/session/complete` with the stored payload
   - Normal server behaviour applies
   - If items were modified by another user while offline (e.g., someone else already bought "Milk"), the server skips already-archived items silently

---

## Frontend Design

### Session Mode (Active)

```
┌─────────────────────────────┐
│  🛒 Shopping Mode            │
│                             │
│  ☑ Milk (2L)               │
│  ☑ Eggs (12)               │
│  ☐ Bread                   │
│  ☑ Pasta (500g)            │
│  ☑ 🧑 Toothbrush [personal] │
│  ☐ Olive oil               │
│                             │
│  4 items checked            │
│                             │
│  [Cancel]         [Done →]  │
└─────────────────────────────┘
```

### Session Summary (on Done)

```
┌─────────────────────────────┐
│  Shopping Summary            │
│                             │
│  Shared items: 3            │
│    Milk, Eggs, Pasta        │
│                             │
│  Personal items: 1          │
│    Toothbrush (not shared)  │
│                             │
│  Receipt total: [___€___]   │
│                             │
│  ☑ Create shared expense    │
│                             │
│  [Back]          [Confirm]  │
└─────────────────────────────┘
```

---

## Key Rules

- Shopping session is **client-side only** — no server entity, no locking, no coordination between users.
- The expense amount is the **receipt total** entered by the user, not a sum of item prices (items have no price field).
- Personal items are always excluded from expense generation.
- Default expense split: all active household members (user can adjust in draft review).
- "Clear list" (archive) and "shopping session Done" are **two separate actions** with different behaviours: clear archives everything without expense; session removes checked items and optionally creates an expense.
