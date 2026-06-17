import { create } from "zustand";

export type SplitMode = "equal" | "custom" | "percentage";

interface SplitEntry {
  user_id: string;
  value: number; // amount for equal/custom, percentage for percentage mode
}

interface CreateExpenseFormState {
  title: string;
  amount: string;
  currency: string;
  category: string;
  paidByUserId: string | null;
  splitMode: SplitMode;
  splits: SplitEntry[];
  participants: string[]; // user_ids included in split
}

interface ExpenseStoreState {
  // Create expense form
  form: CreateExpenseFormState;
  setFormField: <K extends keyof CreateExpenseFormState>(
    key: K,
    value: CreateExpenseFormState[K]
  ) => void;
  resetForm: () => void;

  // Detail view
  selectedExpenseId: string | null;
  setSelectedExpenseId: (id: string | null) => void;

  // Filter state
  statusFilter: "all" | "draft" | "confirmed";
  setStatusFilter: (status: "all" | "draft" | "confirmed") => void;

  // View mode
  activeTab: "expenses" | "balances" | "settlements";
  setActiveTab: (tab: "expenses" | "balances" | "settlements") => void;
}

const initialForm: CreateExpenseFormState = {
  title: "",
  amount: "",
  currency: "EUR",
  category: "",
  paidByUserId: null,
  splitMode: "equal",
  splits: [],
  participants: [],
};

export const useExpenseStore = create<ExpenseStoreState>((set) => ({
  form: { ...initialForm },
  setFormField: (key, value) =>
    set((state) => ({ form: { ...state.form, [key]: value } })),
  resetForm: () => set({ form: { ...initialForm } }),

  selectedExpenseId: null,
  setSelectedExpenseId: (id) => set({ selectedExpenseId: id }),

  statusFilter: "all",
  setStatusFilter: (status) => set({ statusFilter: status }),

  activeTab: "expenses",
  setActiveTab: (tab) => set({ activeTab: tab }),
}));
