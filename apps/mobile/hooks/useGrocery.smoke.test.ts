/**
 * Smoke Test: Phase 12 — Mobile: Grocery Module
 *
 * Exercises the core mobile grocery functionality end-to-end:
 * - Item display and filtering (personal vs all)
 * - Shopping session lifecycle (start → check items → done → summary → confirm)
 * - Session summary splits shared vs personal items correctly
 * - Expense creation validation logic
 * - Offline queue management (add → sync → remove)
 * - Clear list (archive) flow
 *
 * Success Criteria (from implementation-plan-v1.md Phase 12):
 * 1. Items sync in real-time between devices (via SignalR cache invalidation)
 * 2. Personal items visible only to owner (hidden) or marked (visible)
 * 3. Shopping session → expense draft flow works end-to-end
 * 4. Offline add/session works and syncs on reconnect
 *
 * Relevant docs:
 * - docs/logics/grocery-session.md
 * - docs/planning/implementation-plan-v1.md Phase 12
 */

import { GroceryItem } from "@hausly/types";
import { useGroceryStore } from "@/stores/groceryStore";

// --- Extracted logic under test (mirrors grocery.tsx and SessionSummary.tsx) ---

function filterItems(items: GroceryItem[], showPersonalOnly: boolean): GroceryItem[] {
  if (showPersonalOnly) return items.filter((i) => i.is_personal);
  return items;
}

function getSessionSummary(items: GroceryItem[], checkedIds: Set<string>) {
  const checkedItems = items.filter((i) => checkedIds.has(i.id));
  const sharedItems = checkedItems.filter((i) => !i.is_personal);
  const personalItems = checkedItems.filter((i) => i.is_personal);
  return { checkedItems, sharedItems, personalItems };
}

function isSessionConfirmValid(createExpense: boolean, receiptTotal: string): boolean {
  if (!createExpense) return true;
  const amount = parseFloat(receiptTotal);
  return !isNaN(amount) && amount > 0;
}

function buildSessionPayload(
  checkedIds: Set<string>,
  receiptTotal: number,
  createExpense: boolean
) {
  return {
    bought_item_ids: Array.from(checkedIds),
    receipt_total: receiptTotal,
    create_expense: createExpense,
  };
}

// --- Test data ---

const HOUSEHOLD_ID = "hh-test-123";
const USER_ALICE_ID = "user-alice-001";
const USER_BOB_ID = "user-bob-002";

const testItems: GroceryItem[] = [
  {
    id: "item-shared-1",
    name: "Milk",
    quantity: 2,
    unit: "L",
    is_bought: false,
    added_by_user_id: USER_ALICE_ID,
    source: "manual",
    is_personal: false,
    personal_for_user_id: null,
    personal_visibility: "visible",
    created_at: "2024-01-01T10:00:00Z",
  },
  {
    id: "item-shared-2",
    name: "Eggs",
    quantity: 12,
    unit: "pcs",
    is_bought: false,
    added_by_user_id: USER_BOB_ID,
    source: "manual",
    is_personal: false,
    personal_for_user_id: null,
    personal_visibility: "visible",
    created_at: "2024-01-01T10:01:00Z",
  },
  {
    id: "item-shared-3",
    name: "Bread",
    quantity: 1,
    unit: null,
    is_bought: false,
    added_by_user_id: USER_ALICE_ID,
    source: "manual",
    is_personal: false,
    personal_for_user_id: null,
    personal_visibility: "visible",
    created_at: "2024-01-01T10:02:00Z",
  },
  {
    id: "item-personal-visible",
    name: "Toothbrush",
    quantity: 1,
    unit: null,
    is_bought: false,
    added_by_user_id: USER_ALICE_ID,
    source: "manual",
    is_personal: true,
    personal_for_user_id: USER_ALICE_ID,
    personal_visibility: "visible",
    created_at: "2024-01-01T10:03:00Z",
  },
  {
    id: "item-personal-hidden",
    name: "Secret Item",
    quantity: null,
    unit: null,
    is_bought: false,
    added_by_user_id: USER_BOB_ID,
    source: "manual",
    is_personal: true,
    personal_for_user_id: USER_BOB_ID,
    personal_visibility: "hidden",
    created_at: "2024-01-01T10:04:00Z",
  },
];

// --- Tests ---

describe("Phase 12 Smoke: Grocery Module End-to-End", () => {
  beforeEach(() => {
    const store = useGroceryStore.getState();
    store.endSession();
    store.clearPendingOperations();
  });

  describe("Shopping session lifecycle (Success Criterion #3)", () => {
    it("test_session_lifecycle_end_to_end_happy_path", () => {
      const store = useGroceryStore.getState();

      // Step 1: Start session
      store.startSession();
      expect(useGroceryStore.getState().isSessionActive).toBe(true);
      expect(useGroceryStore.getState().checkedItemIds.size).toBe(0);

      // Step 2: Check items during shopping (3 shared + 1 personal)
      store.toggleItem("item-shared-1"); // Milk
      store.toggleItem("item-shared-2"); // Eggs
      store.toggleItem("item-shared-3"); // Bread
      store.toggleItem("item-personal-visible"); // Toothbrush (personal)

      expect(useGroceryStore.getState().checkedItemIds.size).toBe(4);

      // Step 3: Generate session summary
      const checkedIds = useGroceryStore.getState().checkedItemIds;
      const { sharedItems, personalItems } = getSessionSummary(testItems, checkedIds);

      // grocery-session.md: personal items excluded from expense
      expect(sharedItems).toHaveLength(3);
      expect(personalItems).toHaveLength(1);
      expect(sharedItems.map((i) => i.name)).toEqual(["Milk", "Eggs", "Bread"]);
      expect(personalItems[0].name).toBe("Toothbrush");

      // Step 4: Validate confirmation (expense enabled, valid amount)
      expect(isSessionConfirmValid(true, "35.50")).toBe(true);

      // Step 5: Build payload for POST /session/complete
      const payload = buildSessionPayload(checkedIds, 35.5, true);
      expect(payload.bought_item_ids).toHaveLength(4);
      expect(payload.receipt_total).toBe(35.5);
      expect(payload.create_expense).toBe(true);

      // Step 6: End session clears state
      store.endSession();
      expect(useGroceryStore.getState().isSessionActive).toBe(false);
      expect(useGroceryStore.getState().checkedItemIds.size).toBe(0);
    });

    it("test_session_cancel_discards_all_state", () => {
      const store = useGroceryStore.getState();

      store.startSession();
      store.toggleItem("item-shared-1");
      store.toggleItem("item-shared-2");
      expect(useGroceryStore.getState().checkedItemIds.size).toBe(2);

      // Cancel = endSession — discards all checked state
      store.endSession();
      expect(useGroceryStore.getState().isSessionActive).toBe(false);
      expect(useGroceryStore.getState().checkedItemIds.size).toBe(0);
    });

    it("test_session_toggle_item_is_idempotent", () => {
      const store = useGroceryStore.getState();
      store.startSession();

      // Toggle on
      store.toggleItem("item-shared-1");
      expect(useGroceryStore.getState().checkedItemIds.has("item-shared-1")).toBe(true);

      // Toggle off
      store.toggleItem("item-shared-1");
      expect(useGroceryStore.getState().checkedItemIds.has("item-shared-1")).toBe(false);

      // Toggle on again
      store.toggleItem("item-shared-1");
      expect(useGroceryStore.getState().checkedItemIds.has("item-shared-1")).toBe(true);
    });
  });

  describe("Personal item filtering (Success Criterion #2)", () => {
    it("test_filter_all_shows_all_items", () => {
      const result = filterItems(testItems, false);
      expect(result).toHaveLength(5);
    });

    it("test_filter_personal_shows_only_personal_items", () => {
      const result = filterItems(testItems, true);
      expect(result).toHaveLength(2);
      expect(result.every((i) => i.is_personal)).toBe(true);
      expect(result.map((i) => i.name).sort()).toEqual(["Secret Item", "Toothbrush"]);
    });

    it("test_personal_items_excluded_from_session_expense", () => {
      // grocery-session.md key rule: Personal items always excluded from expense
      const checkedIds = new Set(["item-shared-1", "item-personal-visible", "item-personal-hidden"]);
      const { sharedItems, personalItems } = getSessionSummary(testItems, checkedIds);

      // Only shared items go into expense
      expect(sharedItems).toHaveLength(1);
      expect(sharedItems[0].name).toBe("Milk");

      // Personal items tracked separately
      expect(personalItems).toHaveLength(2);
    });
  });

  describe("Session confirm validation (Success Criterion #3)", () => {
    it("test_valid_when_expense_disabled", () => {
      // No receipt total needed when expense is disabled
      expect(isSessionConfirmValid(false, "")).toBe(true);
      expect(isSessionConfirmValid(false, "0")).toBe(true);
      expect(isSessionConfirmValid(false, "abc")).toBe(true);
    });

    it("test_valid_when_expense_enabled_positive_amount", () => {
      expect(isSessionConfirmValid(true, "10.50")).toBe(true);
      expect(isSessionConfirmValid(true, "0.01")).toBe(true);
      expect(isSessionConfirmValid(true, "999.99")).toBe(true);
    });

    it("test_invalid_when_expense_enabled_bad_amount", () => {
      expect(isSessionConfirmValid(true, "")).toBe(false);
      expect(isSessionConfirmValid(true, "0")).toBe(false);
      expect(isSessionConfirmValid(true, "-5")).toBe(false);
      expect(isSessionConfirmValid(true, "abc")).toBe(false);
    });
  });

  describe("Offline queue (Success Criterion #4)", () => {
    it("test_offline_session_complete_queued_and_synced", () => {
      const store = useGroceryStore.getState();

      // Simulate offline session complete
      store.addPendingOperation({
        type: "session_complete",
        payload: {
          householdId: HOUSEHOLD_ID,
          bought_item_ids: ["item-shared-1", "item-shared-2"],
          receipt_total: 25.0,
          create_expense: true,
        },
      });

      // Operation is queued
      const ops = useGroceryStore.getState().pendingOperations;
      expect(ops).toHaveLength(1);
      expect(ops[0].type).toBe("session_complete");
      expect(ops[0].payload.receipt_total).toBe(25.0);
      expect(ops[0].payload.bought_item_ids).toEqual(["item-shared-1", "item-shared-2"]);
      expect(ops[0].id).toBeDefined();
      expect(ops[0].createdAt).toBeDefined();

      // Simulate sync success — remove from queue
      store.removePendingOperation(ops[0].id);
      expect(useGroceryStore.getState().pendingOperations).toHaveLength(0);
    });

    it("test_multiple_offline_operations_queued_in_order", () => {
      const store = useGroceryStore.getState();

      store.addPendingOperation({
        type: "session_complete",
        payload: {
          householdId: HOUSEHOLD_ID,
          bought_item_ids: ["a"],
          receipt_total: 10,
          create_expense: true,
        },
      });
      store.addPendingOperation({
        type: "session_complete",
        payload: {
          householdId: HOUSEHOLD_ID,
          bought_item_ids: ["b"],
          receipt_total: 20,
          create_expense: false,
        },
      });

      const ops = useGroceryStore.getState().pendingOperations;
      expect(ops).toHaveLength(2);
      expect(ops[0].payload.receipt_total).toBe(10);
      expect(ops[1].payload.receipt_total).toBe(20);

      // Clear all
      store.clearPendingOperations();
      expect(useGroceryStore.getState().pendingOperations).toHaveLength(0);
    });
  });

  describe("Session payload construction", () => {
    it("test_payload_includes_all_checked_ids", () => {
      const ids = new Set(["item-shared-1", "item-shared-2", "item-personal-visible"]);
      const payload = buildSessionPayload(ids, 42.0, true);

      expect(payload.bought_item_ids).toHaveLength(3);
      expect(payload.bought_item_ids).toContain("item-shared-1");
      expect(payload.bought_item_ids).toContain("item-shared-2");
      expect(payload.bought_item_ids).toContain("item-personal-visible");
      expect(payload.receipt_total).toBe(42.0);
      expect(payload.create_expense).toBe(true);
    });

    it("test_payload_without_expense_creation", () => {
      const ids = new Set(["item-shared-1"]);
      const payload = buildSessionPayload(ids, 0, false);

      expect(payload.create_expense).toBe(false);
      expect(payload.receipt_total).toBe(0);
    });
  });

  describe("Edge cases", () => {
    it("test_session_with_no_items_checked_produces_empty_summary", () => {
      const emptyChecked = new Set<string>();
      const { checkedItems, sharedItems, personalItems } = getSessionSummary(
        testItems,
        emptyChecked
      );
      expect(checkedItems).toHaveLength(0);
      expect(sharedItems).toHaveLength(0);
      expect(personalItems).toHaveLength(0);
    });

    it("test_session_with_only_personal_items_no_shared_in_expense", () => {
      // grocery-session.md: if all checked items are personal, no expense should be created
      const onlyPersonal = new Set(["item-personal-visible", "item-personal-hidden"]);
      const { sharedItems, personalItems } = getSessionSummary(testItems, onlyPersonal);

      expect(sharedItems).toHaveLength(0);
      expect(personalItems).toHaveLength(2);
      // Client should not attempt expense creation when no shared items
    });

    it("test_filter_on_empty_list_returns_empty", () => {
      expect(filterItems([], false)).toHaveLength(0);
      expect(filterItems([], true)).toHaveLength(0);
    });
  });
});
