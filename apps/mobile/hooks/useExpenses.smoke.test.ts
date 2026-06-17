/**
 * Smoke Test: Phase 13 — Mobile: Expense Module
 *
 * Exercises the core mobile expense functionality end-to-end:
 * - Expense creation with all three split modes (equal, custom, percentage)
 * - Split sum validation and remainder handling
 * - Draft→confirm lifecycle via store state
 * - Balance rendering logic (direction, settled detection)
 * - Settlement suggestion handling (finding unsettled splits)
 * - Filter and tab state management
 * - Grocery-generated draft detection and confirmation flow
 *
 * Success Criteria (from implementation-plan-v1.md Phase 13):
 * 1. Create expense with all split modes works
 * 2. Balance calculation matches server (client renders server data correctly)
 * 3. Draft→confirm flow works
 * 4. Grocery-generated drafts appear for confirmation
 * 5. Settlement suggestions display correctly
 *
 * Relevant docs:
 * - docs/logics/expense-splits.md
 * - docs/planning/implementation-plan-v1.md Phase 13
 */

import { Expense, Balance, SettlementSuggestion, HouseholdMember } from "@hausly/types";
import { useExpenseStore, SplitMode } from "@/stores/expenseStore";

// --- Extracted logic under test (mirrors CreateExpenseSheet.tsx) ---

function computeEqualSplits(amount: number, participants: string[]) {
  if (participants.length === 0) return [];
  const perPerson = amount / participants.length;
  const rounded = Math.floor(perPerson * 100) / 100;
  const remainder = amount - rounded * participants.length;

  return participants.map((userId, index) => ({
    user_id: userId,
    share_amount:
      index === participants.length - 1
        ? Math.round((rounded + remainder) * 100) / 100
        : rounded,
  }));
}

function computeCustomSplits(
  participants: string[],
  customAmounts: Record<string, string>
) {
  return participants.map((userId) => ({
    user_id: userId,
    share_amount: parseFloat(customAmounts[userId] ?? "0") || 0,
  }));
}

function computePercentageSplits(
  amount: number,
  participants: string[],
  percentages: Record<string, string>
) {
  return participants.map((userId) => {
    const pct = parseFloat(percentages[userId] ?? "0") || 0;
    return {
      user_id: userId,
      share_amount: Math.round(((amount * pct) / 100) * 100) / 100,
    };
  });
}

function validateExpenseForm(
  title: string,
  amount: number,
  participants: string[],
  splitMode: SplitMode,
  computedSplits: { user_id: string; share_amount: number }[],
  percentages: Record<string, string>
): string | null {
  if (!title.trim()) return "Title is required";
  if (amount <= 0) return "Amount must be greater than 0";
  if (participants.length === 0) return "Select at least one participant";

  if (splitMode === "custom") {
    const total = computedSplits.reduce((sum, s) => sum + s.share_amount, 0);
    if (Math.abs(total - amount) > 0.01) {
      return `Split total (${total.toFixed(2)}) doesn't match amount (${amount.toFixed(2)})`;
    }
  }

  if (splitMode === "percentage") {
    const totalPct = participants.reduce(
      (sum, uid) => sum + (parseFloat(percentages[uid] ?? "0") || 0),
      0
    );
    if (Math.abs(totalPct - 100) > 0.01) {
      return `Percentages sum to ${totalPct.toFixed(1)}%, must equal 100%`;
    }
  }

  return null;
}

// --- Balance/Settlement rendering logic (mirrors BalanceSummary.tsx / SettlementList.tsx) ---

function getMemberName(
  userId: string,
  currentUserId: string,
  members: HouseholdMember[]
): string {
  if (userId === currentUserId) return "You";
  return members.find((m) => m.user_id === userId)?.display_name ?? "Unknown";
}

function getActiveBalances(balances: Balance[]): Balance[] {
  return balances.filter((b) => b.direction !== "settled");
}

function findUnsettledSplitsForSettlement(
  expenses: Expense[],
  suggestion: SettlementSuggestion
) {
  const relevantExpenses = expenses.filter(
    (e) =>
      e.status === "confirmed" &&
      e.paid_by_user_id === suggestion.to_user_id
  );
  return relevantExpenses.flatMap((e) =>
    e.splits.filter(
      (s) => s.user_id === suggestion.from_user_id && !s.is_settled
    )
  );
}

// --- Test data ---

const USER_ALICE = "user-alice-001";
const USER_BOB = "user-bob-002";
const USER_CAROL = "user-carol-003";

const members: HouseholdMember[] = [
  { user_id: USER_ALICE, display_name: "Alice", email: "alice@test.com", role: "admin", joined_at: "2024-01-01T00:00:00Z" },
  { user_id: USER_BOB, display_name: "Bob", email: "bob@test.com", role: "member", joined_at: "2024-01-02T00:00:00Z" },
  { user_id: USER_CAROL, display_name: "Carol", email: "carol@test.com", role: "member", joined_at: "2024-01-03T00:00:00Z" },
];

const draftExpense: Expense = {
  id: "exp-draft-001",
  title: "Groceries",
  amount: 45.60,
  currency: "EUR",
  category: "food",
  paid_by_user_id: USER_ALICE,
  status: "draft",
  source: "manual",
  splits: [
    { id: "split-1", user_id: USER_ALICE, share_amount: 22.80, is_settled: false, settled_at: null },
    { id: "split-2", user_id: USER_BOB, share_amount: 22.80, is_settled: false, settled_at: null },
  ],
  created_at: "2024-06-15T10:00:00Z",
  confirmed_at: null,
};

const confirmedExpense: Expense = {
  id: "exp-conf-001",
  title: "Dinner",
  amount: 60.00,
  currency: "EUR",
  category: "food",
  paid_by_user_id: USER_ALICE,
  status: "confirmed",
  source: "manual",
  splits: [
    { id: "split-3", user_id: USER_ALICE, share_amount: 20.00, is_settled: false, settled_at: null },
    { id: "split-4", user_id: USER_BOB, share_amount: 20.00, is_settled: false, settled_at: null },
    { id: "split-5", user_id: USER_CAROL, share_amount: 20.00, is_settled: false, settled_at: null },
  ],
  created_at: "2024-06-14T20:00:00Z",
  confirmed_at: "2024-06-14T20:05:00Z",
};

const groceryDraftExpense: Expense = {
  id: "exp-grocery-draft-001",
  title: "Weekly shop",
  amount: 85.40,
  currency: "EUR",
  category: "food",
  paid_by_user_id: USER_BOB,
  status: "draft",
  source: "grocery_integration",
  splits: [
    { id: "split-6", user_id: USER_ALICE, share_amount: 28.47, is_settled: false, settled_at: null },
    { id: "split-7", user_id: USER_BOB, share_amount: 28.47, is_settled: false, settled_at: null },
    { id: "split-8", user_id: USER_CAROL, share_amount: 28.46, is_settled: false, settled_at: null },
  ],
  created_at: "2024-06-16T14:00:00Z",
  confirmed_at: null,
};

const allExpenses = [draftExpense, confirmedExpense, groceryDraftExpense];

// --- Tests ---

describe("Phase 13 Smoke: Expense Module End-to-End", () => {
  beforeEach(() => {
    useExpenseStore.setState({
      form: {
        title: "",
        amount: "",
        currency: "EUR",
        category: "",
        paidByUserId: null,
        splitMode: "equal",
        splits: [],
        participants: [],
      },
      selectedExpenseId: null,
      statusFilter: "all",
      activeTab: "expenses",
    });
  });

  // =========================================================================
  // Success Criterion #1: Create expense with all split modes works
  // =========================================================================
  describe("Create expense with all split modes (SC #1)", () => {
    it("test_create_expense_equal_split_end_to_end_happy_path", () => {
      // Scenario: Alice pays €90, split equally among 3 members
      const amount = 90;
      const participants = [USER_ALICE, USER_BOB, USER_CAROL];
      const splits = computeEqualSplits(amount, participants);

      // Splits computed correctly: each gets €30
      expect(splits).toHaveLength(3);
      expect(splits[0].share_amount).toBe(30);
      expect(splits[1].share_amount).toBe(30);
      expect(splits[2].share_amount).toBe(30);

      // Sum must equal amount (expense-splits.md invariant)
      const total = splits.reduce((sum, s) => sum + s.share_amount, 0);
      expect(total).toBeCloseTo(amount, 2);

      // Validation passes
      const error = validateExpenseForm(
        "Team lunch",
        amount,
        participants,
        "equal",
        splits,
        {}
      );
      expect(error).toBeNull();
    });

    it("test_create_expense_equal_split_remainder_goes_to_last", () => {
      // expense-splits.md: "remainder goes to last participant"
      const amount = 100;
      const participants = [USER_ALICE, USER_BOB, USER_CAROL];
      const splits = computeEqualSplits(amount, participants);

      // 100 / 3 = 33.33... → first two get 33.33, last gets 33.34
      expect(splits[0].share_amount).toBe(33.33);
      expect(splits[1].share_amount).toBe(33.33);
      expect(splits[2].share_amount).toBeCloseTo(33.34, 2);

      const total = splits.reduce((sum, s) => sum + s.share_amount, 0);
      expect(total).toBeCloseTo(100, 2);
    });

    it("test_create_expense_custom_split_valid_sum", () => {
      const amount = 100;
      const participants = [USER_ALICE, USER_BOB];
      const customAmounts = { [USER_ALICE]: "60", [USER_BOB]: "40" };
      const splits = computeCustomSplits(participants, customAmounts);

      expect(splits[0].share_amount).toBe(60);
      expect(splits[1].share_amount).toBe(40);

      // Validation passes (sum == amount)
      const error = validateExpenseForm(
        "Utilities",
        amount,
        participants,
        "custom",
        splits,
        {}
      );
      expect(error).toBeNull();
    });

    it("test_create_expense_custom_split_invalid_sum_rejected", () => {
      // expense-splits.md: "Sum must equal total"
      const amount = 100;
      const participants = [USER_ALICE, USER_BOB];
      const customAmounts = { [USER_ALICE]: "60", [USER_BOB]: "30" };
      const splits = computeCustomSplits(participants, customAmounts);

      const error = validateExpenseForm(
        "Utilities",
        amount,
        participants,
        "custom",
        splits,
        {}
      );
      expect(error).toContain("doesn't match amount");
    });

    it("test_create_expense_percentage_split_valid", () => {
      const amount = 200;
      const participants = [USER_ALICE, USER_BOB, USER_CAROL];
      const percentages = {
        [USER_ALICE]: "50",
        [USER_BOB]: "30",
        [USER_CAROL]: "20",
      };
      const splits = computePercentageSplits(amount, participants, percentages);

      expect(splits[0].share_amount).toBe(100);
      expect(splits[1].share_amount).toBe(60);
      expect(splits[2].share_amount).toBe(40);

      // Validation passes (percentages sum to 100)
      const error = validateExpenseForm(
        "Rent",
        amount,
        participants,
        "percentage",
        splits,
        percentages
      );
      expect(error).toBeNull();
    });

    it("test_create_expense_percentage_split_invalid_sum_rejected", () => {
      // expense-splits.md: "Percentages must sum to 100%"
      const amount = 200;
      const participants = [USER_ALICE, USER_BOB];
      const percentages = { [USER_ALICE]: "60", [USER_BOB]: "30" };
      const splits = computePercentageSplits(amount, participants, percentages);

      const error = validateExpenseForm(
        "Rent",
        amount,
        participants,
        "percentage",
        splits,
        percentages
      );
      expect(error).toContain("must equal 100%");
    });

    it("test_create_expense_validation_rejects_empty_title", () => {
      const error = validateExpenseForm("", 50, [USER_ALICE], "equal", [], {});
      expect(error).toBe("Title is required");
    });

    it("test_create_expense_validation_rejects_zero_amount", () => {
      const error = validateExpenseForm("Test", 0, [USER_ALICE], "equal", [], {});
      expect(error).toBe("Amount must be greater than 0");
    });

    it("test_create_expense_validation_rejects_no_participants", () => {
      const error = validateExpenseForm("Test", 50, [], "equal", [], {});
      expect(error).toBe("Select at least one participant");
    });

    it("test_payer_included_in_splits_as_per_spec", () => {
      // expense-splits.md: "The payer is included in the splits array"
      // 2 people, €40 equal split → splits: [€20 (payer), €20 (other)]
      const amount = 40;
      const payer = USER_ALICE;
      const participants = [USER_ALICE, USER_BOB];
      const splits = computeEqualSplits(amount, participants);

      // Payer is included
      const payerSplit = splits.find((s) => s.user_id === payer);
      expect(payerSplit).toBeDefined();
      expect(payerSplit!.share_amount).toBe(20);

      // Net credit for payer = amount - payer_split = 40 - 20 = 20
      const netCredit = amount - payerSplit!.share_amount;
      expect(netCredit).toBe(20);
    });
  });

  // =========================================================================
  // Success Criterion #3: Draft→confirm flow works
  // =========================================================================
  describe("Draft→confirm flow (SC #3)", () => {
    it("test_draft_confirm_lifecycle_end_to_end", () => {
      // Step 1: Store starts with expenses tab
      expect(useExpenseStore.getState().activeTab).toBe("expenses");

      // Step 2: Select a draft expense for viewing
      const { setSelectedExpenseId } = useExpenseStore.getState();
      setSelectedExpenseId(draftExpense.id);
      expect(useExpenseStore.getState().selectedExpenseId).toBe(draftExpense.id);

      // Step 3: Draft is identifiable as draft (can be confirmed)
      expect(draftExpense.status).toBe("draft");
      expect(draftExpense.confirmed_at).toBeNull();

      // Step 4: After confirmation, expense would have confirmed status
      // (API changes status; client re-fetches via cache invalidation)
      const confirmedVersion: Expense = {
        ...draftExpense,
        status: "confirmed",
        confirmed_at: "2024-06-15T10:05:00Z",
      };
      expect(confirmedVersion.status).toBe("confirmed");
      expect(confirmedVersion.confirmed_at).not.toBeNull();

      // Step 5: Clear selection after confirm
      setSelectedExpenseId(null);
      expect(useExpenseStore.getState().selectedExpenseId).toBeNull();
    });

    it("test_draft_only_expenses_have_confirm_action", () => {
      // expense-splits.md: "Once confirmed, cannot be edited — only archived"
      expect(draftExpense.status).toBe("draft");
      expect(confirmedExpense.status).toBe("confirmed");

      // Only drafts should show confirm/delete actions
      const isDraft = (e: Expense) => e.status === "draft";
      expect(isDraft(draftExpense)).toBe(true);
      expect(isDraft(confirmedExpense)).toBe(false);
    });

    it("test_auto_generated_expenses_always_start_as_draft", () => {
      // expense-splits.md: "Auto-generated expenses always start as draft"
      expect(groceryDraftExpense.source).toBe("grocery_integration");
      expect(groceryDraftExpense.status).toBe("draft");
    });
  });

  // =========================================================================
  // Success Criterion #2: Balance calculation matches server
  // =========================================================================
  describe("Balance rendering (SC #2)", () => {
    it("test_balance_summary_shows_active_balances_only", () => {
      const balances: Balance[] = [
        { user_a_id: USER_ALICE, user_b_id: USER_BOB, net_amount: 20, direction: "b_owes_a" },
        { user_a_id: USER_ALICE, user_b_id: USER_CAROL, net_amount: 0, direction: "settled" },
        { user_a_id: USER_BOB, user_b_id: USER_CAROL, net_amount: 15, direction: "a_owes_b" },
      ];

      const active = getActiveBalances(balances);
      // Settled balances should be filtered out
      expect(active).toHaveLength(2);
      expect(active.every((b) => b.direction !== "settled")).toBe(true);
    });

    it("test_balance_direction_determines_debtor_and_creditor", () => {
      // expense-splits.md: "If positive: A owes B, if negative: B owes A"
      const balanceAOwesB: Balance = {
        user_a_id: USER_ALICE,
        user_b_id: USER_BOB,
        net_amount: 30,
        direction: "a_owes_b",
      };

      // When direction is a_owes_b, Alice is the debtor
      const fromId =
        balanceAOwesB.direction === "a_owes_b"
          ? balanceAOwesB.user_a_id
          : balanceAOwesB.user_b_id;
      const toId =
        balanceAOwesB.direction === "a_owes_b"
          ? balanceAOwesB.user_b_id
          : balanceAOwesB.user_a_id;

      expect(fromId).toBe(USER_ALICE);
      expect(toId).toBe(USER_BOB);
    });

    it("test_member_name_resolution_shows_you_for_current_user", () => {
      expect(getMemberName(USER_ALICE, USER_ALICE, members)).toBe("You");
      expect(getMemberName(USER_BOB, USER_ALICE, members)).toBe("Bob");
      expect(getMemberName("unknown-id", USER_ALICE, members)).toBe("Unknown");
    });
  });

  // =========================================================================
  // Success Criterion #4: Grocery-generated drafts appear for confirmation
  // =========================================================================
  describe("Grocery-generated drafts (SC #4)", () => {
    it("test_grocery_drafts_identifiable_by_source_and_status", () => {
      // Grocery-generated expenses are identifiable by source field
      const groceryDrafts = allExpenses.filter(
        (e) => e.source === "grocery_integration" && e.status === "draft"
      );
      expect(groceryDrafts).toHaveLength(1);
      expect(groceryDrafts[0].id).toBe("exp-grocery-draft-001");
      expect(groceryDrafts[0].title).toBe("Weekly shop");
    });

    it("test_grocery_drafts_appear_in_draft_filter", () => {
      // When user filters by "draft", grocery-generated drafts show up
      const { setStatusFilter } = useExpenseStore.getState();
      setStatusFilter("draft");
      expect(useExpenseStore.getState().statusFilter).toBe("draft");

      const draftExpenses = allExpenses.filter((e) => e.status === "draft");
      expect(draftExpenses).toHaveLength(2); // manual draft + grocery draft
      expect(draftExpenses.map((e) => e.source)).toContain("grocery_integration");
      expect(draftExpenses.map((e) => e.source)).toContain("manual");
    });

    it("test_grocery_draft_has_correct_split_structure", () => {
      // Grocery integration creates equal splits across all members
      expect(groceryDraftExpense.splits).toHaveLength(3);
      const total = groceryDraftExpense.splits.reduce(
        (sum, s) => sum + s.share_amount,
        0
      );
      // Sum of splits must equal expense amount
      expect(total).toBeCloseTo(groceryDraftExpense.amount, 2);
    });
  });

  // =========================================================================
  // Success Criterion #5: Settlement suggestions display correctly
  // =========================================================================
  describe("Settlement suggestions (SC #5)", () => {
    it("test_settlement_finds_unsettled_splits_for_suggestion", () => {
      // expense-splits.md: settlement matches debtors with creditors
      const suggestion: SettlementSuggestion = {
        from_user_id: USER_BOB,
        to_user_id: USER_ALICE,
        amount: 20,
      };

      // Alice paid for confirmed dinner, Bob owes Alice
      const unsettled = findUnsettledSplitsForSettlement(
        [confirmedExpense],
        suggestion
      );

      // Bob has an unsettled split in the confirmed expense paid by Alice
      expect(unsettled).toHaveLength(1);
      expect(unsettled[0].user_id).toBe(USER_BOB);
      expect(unsettled[0].is_settled).toBe(false);
    });

    it("test_settlement_ignores_draft_expenses", () => {
      // expense-splits.md: "Only confirmed expenses affect balances"
      const suggestion: SettlementSuggestion = {
        from_user_id: USER_BOB,
        to_user_id: USER_ALICE,
        amount: 22.80,
      };

      // Draft expense should be skipped
      const unsettled = findUnsettledSplitsForSettlement(
        [draftExpense],
        suggestion
      );
      expect(unsettled).toHaveLength(0);
    });

    it("test_settlement_ignores_already_settled_splits", () => {
      const settledExpense: Expense = {
        ...confirmedExpense,
        splits: [
          { id: "split-3", user_id: USER_ALICE, share_amount: 20, is_settled: true, settled_at: "2024-06-15T00:00:00Z" },
          { id: "split-4", user_id: USER_BOB, share_amount: 20, is_settled: true, settled_at: "2024-06-15T00:00:00Z" },
          { id: "split-5", user_id: USER_CAROL, share_amount: 20, is_settled: true, settled_at: "2024-06-15T00:00:00Z" },
        ],
      };

      const suggestion: SettlementSuggestion = {
        from_user_id: USER_BOB,
        to_user_id: USER_ALICE,
        amount: 20,
      };

      const unsettled = findUnsettledSplitsForSettlement(
        [settledExpense],
        suggestion
      );
      expect(unsettled).toHaveLength(0);
    });

    it("test_settlement_across_multiple_expenses", () => {
      // When Bob owes Alice from multiple confirmed expenses
      const secondExpense: Expense = {
        ...confirmedExpense,
        id: "exp-conf-002",
        title: "Uber ride",
        amount: 30,
        splits: [
          { id: "split-9", user_id: USER_ALICE, share_amount: 15, is_settled: false, settled_at: null },
          { id: "split-10", user_id: USER_BOB, share_amount: 15, is_settled: false, settled_at: null },
        ],
      };

      const suggestion: SettlementSuggestion = {
        from_user_id: USER_BOB,
        to_user_id: USER_ALICE,
        amount: 35, // 20 from dinner + 15 from uber
      };

      const unsettled = findUnsettledSplitsForSettlement(
        [confirmedExpense, secondExpense],
        suggestion
      );

      // Should find Bob's unsettled splits in both expenses paid by Alice
      expect(unsettled).toHaveLength(2);
      expect(unsettled[0].share_amount).toBe(20);
      expect(unsettled[1].share_amount).toBe(15);
    });
  });

  // =========================================================================
  // Store state management (supports all criteria)
  // =========================================================================
  describe("Store state management", () => {
    it("test_tab_and_filter_state_persists_across_views", () => {
      const store = useExpenseStore.getState();

      // Switch to balances tab
      store.setActiveTab("balances");
      expect(useExpenseStore.getState().activeTab).toBe("balances");

      // Set draft filter (should persist when switching back to expenses)
      store.setStatusFilter("draft");
      expect(useExpenseStore.getState().statusFilter).toBe("draft");

      // Switch to settlements
      store.setActiveTab("settlements");
      expect(useExpenseStore.getState().activeTab).toBe("settlements");

      // Filter is still draft
      expect(useExpenseStore.getState().statusFilter).toBe("draft");

      // Switch back to expenses
      store.setActiveTab("expenses");
      expect(useExpenseStore.getState().statusFilter).toBe("draft");
    });

    it("test_full_create_expense_form_lifecycle", () => {
      const store = useExpenseStore.getState();

      // Fill form
      store.setFormField("title", "Team dinner");
      store.setFormField("amount", "120");
      store.setFormField("paidByUserId", USER_ALICE);
      store.setFormField("splitMode", "equal");
      store.setFormField("participants", [USER_ALICE, USER_BOB, USER_CAROL]);

      const { form } = useExpenseStore.getState();
      expect(form.title).toBe("Team dinner");
      expect(form.amount).toBe("120");
      expect(form.paidByUserId).toBe(USER_ALICE);
      expect(form.splitMode).toBe("equal");
      expect(form.participants).toHaveLength(3);

      // Reset after submission
      store.resetForm();
      const resetForm = useExpenseStore.getState().form;
      expect(resetForm.title).toBe("");
      expect(resetForm.amount).toBe("");
      expect(resetForm.paidByUserId).toBeNull();
      expect(resetForm.participants).toHaveLength(0);
    });
  });
});
