import { create } from "zustand";

interface PendingOperation {
  id: string;
  type: "session_complete";
  payload: {
    householdId: string;
    bought_item_ids: string[];
    receipt_total: number;
    create_expense: boolean;
  };
  createdAt: string;
}

interface GrocerySessionState {
  // Shopping session
  isSessionActive: boolean;
  checkedItemIds: Set<string>;
  startSession: () => void;
  endSession: () => void;
  toggleItem: (itemId: string) => void;
  clearChecked: () => void;

  // Offline queue
  pendingOperations: PendingOperation[];
  addPendingOperation: (op: Omit<PendingOperation, "id" | "createdAt">) => void;
  removePendingOperation: (id: string) => void;
  clearPendingOperations: () => void;
}

export const useGroceryStore = create<GrocerySessionState>((set) => ({
  // Shopping session
  isSessionActive: false,
  checkedItemIds: new Set(),
  startSession: () => set({ isSessionActive: true, checkedItemIds: new Set() }),
  endSession: () => set({ isSessionActive: false, checkedItemIds: new Set() }),
  toggleItem: (itemId) =>
    set((state) => {
      const next = new Set(state.checkedItemIds);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else {
        next.add(itemId);
      }
      return { checkedItemIds: next };
    }),
  clearChecked: () => set({ checkedItemIds: new Set() }),

  // Offline queue
  pendingOperations: [],
  addPendingOperation: (op) =>
    set((state) => ({
      pendingOperations: [
        ...state.pendingOperations,
        { ...op, id: `op-${Date.now()}`, createdAt: new Date().toISOString() },
      ],
    })),
  removePendingOperation: (id) =>
    set((state) => ({
      pendingOperations: state.pendingOperations.filter((op) => op.id !== id),
    })),
  clearPendingOperations: () => set({ pendingOperations: [] }),
}));
