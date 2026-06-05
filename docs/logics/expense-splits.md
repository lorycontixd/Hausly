# Expense Splits — Logic & Behaviour

> Describes how expense splitting works end-to-end: data flow, balance calculation, settlement, and frontend expectations.
- Read: true
- Approved: true
- Notes: NA
---

## Data Model Recap

```
Expense (one row per purchase/payment)
  └── ExpenseSplit (one row per participant who owes a share)
```

- `Expense` records who paid (`paid_by_user_id`) and the total `amount`.
- `ExpenseSplit` records each participant's owed portion (`share_amount`).
- Sum of all `share_amount` values on an expense must equal `expense.amount`!

---

## Split Modes

The frontend offers three UX modes, all of which resolve to absolute `share_amount` values before submission:

| Mode | Description | Validation |
|------|-------------|------------|
| Equal | `amount / n_participants` per person | Automatic; handles rounding (remainder goes to last participant) |
| Custom amounts | User manually enters each share | Sum must equal total |
| Percentage | User sets % per person, converted to amounts | Percentages must sum to 100% |

The backend only stores and validates absolute amounts — it has no concept of "split mode."

---

## Payer Inclusion in Splits

The payer **is included** in the splits array. Their split represents what they consumed/owe themselves (self-cancelling in balance math). This keeps the model uniform:

- 2 people, €40 equal split → splits: [€20 (payer), €20 (other)]
- The payer's net credit for this expense = `amount - payer_split = €40 - €20 = €20` (the other person owes them €20)

If the payer is NOT a participant (they paid for others only), their split is simply omitted or zero.

---

## Draft → Confirmed Flow

1. Auto-generated expenses (grocery integration, recurring) always start as `status: draft`.
2. Manually created expenses can start as `draft` or `confirmed` (user's choice).
3. **Only confirmed expenses affect balances.** Drafts are invisible to settlement logic.
4. The client presents a confirmation card for drafts: the user reviews amount, splits, and taps confirm.
5. Once confirmed, an expense cannot be edited — only archived.

---

## Balance Calculation

For each ordered pair (A, B) of household members:

```
A owes B = sum of A's splits in expenses paid by B (confirmed only)
B owes A = sum of B's splits in expenses paid by A (confirmed only)

Net(A, B) = (A owes B) - (B owes A)
  If positive: A owes B that amount
  If negative: B owes A that amount
  If zero: settled
```

The `/expenses/balances` endpoint returns one net value per unique member pair.

---

## Settlement

The `/expenses/settlements` endpoint runs a **minimum-transactions** algorithm:

1. Compute net balance per member (total owed - total credited across all pairs).
2. Greedily match the largest creditor with the largest debtor until all nets are zero.
3. Return a list of suggested transactions: `[{ from_user_id, to_user_id, amount }]`.

Settlement is **external** (bank transfer, cash, Revolut). The user marks splits as settled in-app:
- `POST /expenses/splits/{split_id}/settle` sets `is_settled = true` and `settled_at`.
- Once all splits on an expense are settled, the expense is fully resolved.

---

## Recurring Expenses

- Recurring expenses (rent, utilities) are defined once with an RRULE and `next_occurrence_date`.
- A **daily cron job** checks all recurring expenses where `next_occurrence_date <= today`.
- For each due expense: if no unconfirmed draft already exists for that date, a new draft row is generated.
- Each generated instance follows the same draft → confirm flow.
- The user must confirm each occurrence (no silent financial writes — per §2.3 of the master plan).
- **Staleness cap:** if 3 or more unconfirmed drafts exist for a recurring expense, generation pauses. A notification is sent: "You have unconfirmed recurring expenses. Still active?"
- Once confirmed or discarded, `next_occurrence_date` advances per the RRULE.

---

## Grocery → Expense Integration

Integration is triggered by the **shopping session** flow (see `docs/logics/grocery-session.md` for full detail):

1. User enters a shopping session (client-side state) and checks items as they shop.
2. User clicks "Done" and enters the **receipt total** (the amount paid at checkout).
3. A draft expense is created with:
   - `source: grocery_integration`
   - `amount`: the receipt total entered by the user
   - `title`: auto-generated from item names (e.g. "Groceries — 8 items")
   - `splits`: equal split across all active household members (default)
4. Personal items (those with `is_personal = true`) are excluded from the expense context — they are removed from the list but do not appear in the expense description.
5. The frontend surfaces this draft for user review and confirmation.
6. The user can adjust splits, title, amount, or category before confirming.

**Key distinction:** The expense amount comes from the user-entered receipt total, NOT from summing individual item prices. Items have no price field — they serve as context/description only.

---

## Frontend Design

### Screens & Data Requirements

| Screen | Data Source | User Actions |
|--------|------------|--------------|
| **Create expense** | Local form | Enter amount, select payer, pick participants, choose split mode, submit |
| **Expense detail** | `GET /expenses/{id}` | View title, amount, payer, per-person splits |
| **Balance summary** | `GET /expenses/balances` | View net balance per member pair on home screen |
| **Settle up** | `GET /expenses/settlements` | View suggested transactions, tap "Mark as settled" |
| **Confirm draft** | Push notification or draft list | Review auto-generated expense, edit if needed, confirm or discard |

### Create Expense Flow (UI)

```
┌─────────────────────────────┐
│  Amount: [___€___]          │
│  Title:  [____________]     │
│  Paid by: [Lorenzo ▾]      │
│                             │
│  Split between:             │
│  ☑ Lorenzo    €22.80       │
│  ☑ Maria      €22.80       │
│  ☐ Paolo      —            │
│                             │
│  Mode: [Equal ▾] [Custom] [%] │
│                             │
│  [Save as Draft] [Confirm]  │
└─────────────────────────────┘
```

### Balance Summary (Home Screen Widget)

```
┌─────────────────────────────┐
│  Household Balance          │
│                             │
│  You owe Maria     €12.30   │
│  Paolo owes you     €8.50   │
│                             │
│  [Settle Up →]              │
└─────────────────────────────┘
```

### Settle Up Screen

```
┌─────────────────────────────┐
│  Suggested settlements:     │
│                             │
│  Lorenzo → Maria   €12.30   │
│  Paolo → Lorenzo    €8.50   │
│                             │
│  [Mark as Done]             │
│  (payment happens outside)  │
└─────────────────────────────┘
```

### Confirm Draft Card

```
┌─────────────────────────────┐
│  📋 New expense from grocery │
│                             │
│  Groceries — €45.60        │
│  Paid by: Lorenzo           │
│  Split: Equal (€22.80 each) │
│                             │
│  [Edit] [Discard] [Confirm] │
└─────────────────────────────┘
```

---

## Key Rules

- The frontend **never** computes balances locally — always fetches from server.
- All auto-generated expenses require explicit user confirmation before affecting balances.
- Settlement is informational only — the app suggests who pays whom but doesn't process payments.
- The backend validates that `sum(splits) == expense.amount` on every create/update.
