import { create } from "zustand";
import { MealSlot } from "@hausly/types";

interface SelectedSlot {
  date: string;
  slot: MealSlot;
}

interface MealStoreState {
  weekOffset: number;
  selectedSlot: SelectedSlot | null;
  sheetVisible: boolean;
  editingEntryId: string | null;

  nextWeek: () => void;
  prevWeek: () => void;
  resetWeek: () => void;
  openSheet: (slot: SelectedSlot, entryId?: string) => void;
  closeSheet: () => void;
}

export const useMealStore = create<MealStoreState>((set) => ({
  weekOffset: 0,
  selectedSlot: null,
  sheetVisible: false,
  editingEntryId: null,

  nextWeek: () => set((s) => ({ weekOffset: s.weekOffset + 1 })),
  prevWeek: () => set((s) => ({ weekOffset: s.weekOffset - 1 })),
  resetWeek: () => set({ weekOffset: 0 }),
  openSheet: (slot, entryId) =>
    set({ selectedSlot: slot, sheetVisible: true, editingEntryId: entryId ?? null }),
  closeSheet: () =>
    set({ sheetVisible: false, selectedSlot: null, editingEntryId: null }),
}));
