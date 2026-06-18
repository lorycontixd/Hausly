import { useChoreStore } from "./choreStore";

describe("choreStore", () => {
  beforeEach(() => {
    useChoreStore.setState({
      sheetVisible: false,
      editingChoreId: null,
      actionSheetVisible: false,
      selectedAssignmentId: null,
    });
  });

  it("opens create sheet without choreId", () => {
    useChoreStore.getState().openSheet();
    const state = useChoreStore.getState();
    expect(state.sheetVisible).toBe(true);
    expect(state.editingChoreId).toBeNull();
  });

  it("opens edit sheet with choreId", () => {
    useChoreStore.getState().openSheet("chore-123");
    const state = useChoreStore.getState();
    expect(state.sheetVisible).toBe(true);
    expect(state.editingChoreId).toBe("chore-123");
  });

  it("closes sheet and resets editingChoreId", () => {
    useChoreStore.getState().openSheet("chore-123");
    useChoreStore.getState().closeSheet();
    const state = useChoreStore.getState();
    expect(state.sheetVisible).toBe(false);
    expect(state.editingChoreId).toBeNull();
  });

  it("opens action sheet with assignmentId", () => {
    useChoreStore.getState().openActionSheet("assignment-456");
    const state = useChoreStore.getState();
    expect(state.actionSheetVisible).toBe(true);
    expect(state.selectedAssignmentId).toBe("assignment-456");
  });

  it("closes action sheet and resets selectedAssignmentId", () => {
    useChoreStore.getState().openActionSheet("assignment-456");
    useChoreStore.getState().closeActionSheet();
    const state = useChoreStore.getState();
    expect(state.actionSheetVisible).toBe(false);
    expect(state.selectedAssignmentId).toBeNull();
  });
});
