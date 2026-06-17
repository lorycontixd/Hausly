import { useGroceryStore } from "./groceryStore";

describe("groceryStore", () => {
  beforeEach(() => {
    const { endSession, clearPendingOperations } = useGroceryStore.getState();
    endSession();
    clearPendingOperations();
  });

  describe("shopping session", () => {
    it("starts a session with empty checked items", () => {
      useGroceryStore.getState().startSession();

      const state = useGroceryStore.getState();
      expect(state.isSessionActive).toBe(true);
      expect(state.checkedItemIds.size).toBe(0);
    });

    it("toggles items in checked set", () => {
      useGroceryStore.getState().startSession();

      useGroceryStore.getState().toggleItem("item-1");
      expect(useGroceryStore.getState().checkedItemIds.has("item-1")).toBe(true);

      useGroceryStore.getState().toggleItem("item-1");
      expect(useGroceryStore.getState().checkedItemIds.has("item-1")).toBe(false);
    });

    it("ends session and clears checked items", () => {
      useGroceryStore.getState().startSession();
      useGroceryStore.getState().toggleItem("item-1");
      useGroceryStore.getState().endSession();

      const state = useGroceryStore.getState();
      expect(state.isSessionActive).toBe(false);
      expect(state.checkedItemIds.size).toBe(0);
    });
  });

  describe("offline queue", () => {
    it("adds a pending operation", () => {
      useGroceryStore.getState().addPendingOperation({
        type: "session_complete",
        payload: {
          householdId: "h-1",
          bought_item_ids: ["item-1"],
          receipt_total: 10,
          create_expense: true,
        },
      });

      const ops = useGroceryStore.getState().pendingOperations;
      expect(ops).toHaveLength(1);
      expect(ops[0].type).toBe("session_complete");
      expect(ops[0].payload.receipt_total).toBe(10);
    });

    it("removes a pending operation by id", () => {
      useGroceryStore.getState().addPendingOperation({
        type: "session_complete",
        payload: {
          householdId: "h-1",
          bought_item_ids: ["item-1"],
          receipt_total: 5,
          create_expense: false,
        },
      });

      const opId = useGroceryStore.getState().pendingOperations[0].id;
      useGroceryStore.getState().removePendingOperation(opId);

      expect(useGroceryStore.getState().pendingOperations).toHaveLength(0);
    });
  });
});
