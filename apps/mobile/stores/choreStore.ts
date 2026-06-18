import { create } from "zustand";

interface ChoreStoreState {
  // Create/edit sheet
  sheetVisible: boolean;
  editingChoreId: string | null;
  openSheet: (choreId?: string) => void;
  closeSheet: () => void;

  // Assignment action sheet
  actionSheetVisible: boolean;
  selectedAssignmentId: string | null;
  openActionSheet: (assignmentId: string) => void;
  closeActionSheet: () => void;
}

export const useChoreStore = create<ChoreStoreState>((set) => ({
  sheetVisible: false,
  editingChoreId: null,
  openSheet: (choreId) =>
    set({ sheetVisible: true, editingChoreId: choreId ?? null }),
  closeSheet: () => set({ sheetVisible: false, editingChoreId: null }),

  actionSheetVisible: false,
  selectedAssignmentId: null,
  openActionSheet: (assignmentId) =>
    set({ actionSheetVisible: true, selectedAssignmentId: assignmentId }),
  closeActionSheet: () =>
    set({ actionSheetVisible: false, selectedAssignmentId: null }),
}));
