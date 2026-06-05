# Chores — Logic & Behaviour

> Describes the per-chore recurrence model: creation, rotation, assignment generation, overdue blocking, and member departure.
- Read: false
- Approved: false
- Notes: NA
---

## Overview

Each chore is an **independent entity** with its own recurrence and assignee list. There is no global "schedule" or calendar block — chores are created individually by any household member, optionally made recurring, and optionally rotated between assignees.

---

## Data Model

```
Chore (definition — one per task)
  └── ChoreAssignee (ordered list of members responsible)
  └── ChoreAssignment (generated instances with concrete due dates)
```

---

## Chore Creation

Any member can create a chore. The creator **must include themselves** as an assignee (self-assign or shared including self). You cannot create a chore exclusively for others.

### Creation Fields

| Field | Required | Description |
|-------|----------|-------------|
| name | Yes | What the chore is (e.g. "Clean bathroom") |
| assignees | Yes | Ordered list of user_ids. Creator must be included. |
| start_date | Yes | First occurrence date (also anchors day-of-week for weekly recurrence) |
| is_recurring | Yes | Toggle: one-off or repeating |
| recurrence_interval | If recurring | How often: integer (e.g. 1, 2, 3) |
| recurrence_unit | If recurring | Unit: days / weeks / months |
| rotation_enabled | If >1 assignee | Whether to rotate or assign to all |

### Recurrence Examples

| Config | Meaning |
|--------|---------|
| interval=1, unit=weeks, start=Sunday | Every Sunday |
| interval=3, unit=weeks, start=Sunday, rotation=true, 3 assignees | Each person's turn every 3 weeks on Sunday |
| interval=1, unit=months, start=Jun 15 | 15th of every month |
| interval=2, unit=days, start=Jun 4 | Every 2 days starting Jun 4 |
| is_recurring=false, start=tomorrow, 2 assignees | One-off task for tomorrow, both people do it |

---

## Rotation vs Shared Assignment

**When `rotation_enabled = true`** (multiple assignees):
- Each occurrence assigns to the **next person** in the ordered list
- Personal frequency = `chore_interval × assignee_count`
- Example: "Clean house" every week, rotating [A, B, C] → A does it week 1, B week 2, C week 3, A week 4...

**When `rotation_enabled = false`** (multiple assignees):
- Each occurrence creates **one assignment per assignee** — everyone does it on the same day
- Example: "Laundry" one-off tomorrow, assignees=[A, B] → both A and B have an assignment for tomorrow

**Single assignee:** rotation toggle is hidden/irrelevant. One assignment per occurrence.

---

## Assignment Generation

### Recurring Chores

A **daily background job** generates assignments up to 2 weeks ahead (rolling window):

```
for each active recurring chore:
    if has_unresolved_overdue(chore):
        skip  # blocked until resolved

    while next_due_date <= today + 14 days:
        if rotation_enabled:
            assignee = assignees[occurrence_index % len(assignees)]
            create assignment(assignee, next_due_date)
        else:
            for each assignee:
                create assignment(assignee, next_due_date)
        
        advance next_due_date per interval/unit
```

The job is **idempotent** — it skips already-existing assignments (matched by `chore_id` + `due_date` + `assigned_to_user_id`).

### One-Off Chores (is_recurring = false)

- Assignments created **immediately at chore creation time** (one per assignee)
- No cron involvement
- Chore auto-deactivates (`is_active = false`) when all assignments are resolved (completed or cancelled)

### On Chore Creation

When a recurring chore is created, the server generates initial assignments inline (doesn't wait for the next cron run). This ensures the user sees results immediately.

---

## Overdue Blocking

When `due_date < today` and status is `pending`:

1. **Notification:** remind assigned member(s) that the chore is overdue
2. **Block:** no new occurrences are generated for this chore until the overdue assignment is resolved
3. **Resolution options** (shown on the overdue chore card):
   - **Mark as done** → `status: completed`, unblocks, next occurrence generates normally
   - **Postpone** → `postponed_to` set to a new date, assignment stays `pending` with `due_date` unchanged. Effective due date becomes `COALESCE(postponed_to, due_date)`. Unblocks generation temporarily. If postponed date passes without completion, it becomes overdue again.
   - **Cancel** → `status: cancelled`, unblocks, next occurrence generates on schedule

4. **Rotation stays fair:** the blocked assignment stays with the same person. Rotation doesn't advance until they resolve it.

### Postpone Behaviour

- Only the **current overdue occurrence** shifts. Future occurrences remain on their normal schedule.
- Original `due_date` is preserved for audit trail. `postponed_to` holds the new effective date.
- If `postponed_to` also passes without resolution → overdue again, same blocking rules apply.
- Effective due date for all queries: `COALESCE(postponed_to, due_date)`.

---

## Completing a Chore

1. Any household member can mark any assignment as done
2. Server sets `completed_at = now()` and `completed_by_user_id = caller`
3. `completed_by_user_id` may differ from `assigned_to_user_id` — this is by design
4. SignalR broadcasts `chore:completed` to the household

---

## Member Leaving

When a member leaves the household:

1. **Removed from assignee lists** of all chores where they appear
2. **Future pending assignments** for them are deleted
3. **Rotation recomputes:** remaining members rotate normally (list shrinks by one)
4. **If they were the sole assignee:** chore is deactivated, household members notified
5. **Past completed assignments** retain their name permanently (historical accuracy)

No manual admin intervention required — handled automatically.

---

## Chore Deletion

- **Any member** can delete any chore (not just creator or admin)
- Deletion deactivates the chore and deletes future pending assignments
- Past completed assignments remain in history
- Implicit consent model: if someone disagrees, they recreate the chore

---

## Consent Model

Chores use **implicit consent**: when a member creates a chore with multiple assignees, those assignees see it immediately without needing to accept. If someone objects, they resolve it socially or delete the chore. The "anyone can delete" power makes consent a non-issue.

---

## Frontend Design

### Chore List (default view — grouped by date)

```
┌─────────────────────────────┐
│  Chores                      │
│                             │
│  TODAY                      │
│  ☐ Bathroom — Lorenzo       │
│                             │
│  TOMORROW                   │
│  ☐ Laundry — Lorenzo, Maria │
│                             │
│  THIS WEEK                  │
│  ☐ Clean windows — Lorenzo  │  Wed
│  ☐ Clean house — Maria      │  Sun
│                             │
│  OVERDUE ⚠️                  │
│  ☐ Kitchen — Paolo (2d ago) │
│    [Done] [Postpone] [Cancel]│
│                             │
│  [+ Add Chore]              │
└─────────────────────────────┘
```

### Create Chore

```
┌─────────────────────────────┐
│  New Chore                   │
│                             │
│  Name: [Clean house_____]   │
│                             │
│  Starting: [Sunday, Jun 8]  │
│                             │
│  ☑ Make recurring            │
│  Every: [1] [weeks ▾]       │
│                             │
│  Assign to:                 │
│  ☑ Lorenzo (you)            │
│  ☑ Maria                    │
│  ☑ Paolo                    │
│                             │
│  ☑ Rotate between members   │
│  → Your turn every 3 weeks  │
│                             │
│  [Create]                   │
└─────────────────────────────┘
```

### Overdue Card

```
┌─────────────────────────────┐
│  ⚠️ Kitchen — overdue (2d)   │
│  Assigned: Paolo             │
│                             │
│  [Mark Done] [Postpone] [Cancel] │
└─────────────────────────────┘
```

---

## Key Rules

- Any member can create chores (must include self as assignee).
- Any member can delete any chore.
- Any member can complete any assignment (credit to completer).
- Overdue assignments **block** future generation for that chore.
- Postpone shifts only the current occurrence, not the entire schedule.
- One-off chores auto-deactivate on completion.
- No calendar view — due-date-sorted list with grouping is sufficient.
- Consent is implicit; deletion is the safety valve.
