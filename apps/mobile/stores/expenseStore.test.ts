import { useExpenseStore } from "./expenseStore";

describe("expenseStore", () => {
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

  it("sets form fields", () => {
    const { setFormField } = useExpenseStore.getState();
    setFormField("title", "Groceries");
    setFormField("amount", "45.60");

    const { form } = useExpenseStore.getState();
    expect(form.title).toBe("Groceries");
    expect(form.amount).toBe("45.60");
  });

  it("resets form to initial state", () => {
    const { setFormField, resetForm } = useExpenseStore.getState();
    setFormField("title", "Test");
    setFormField("amount", "100");
    setFormField("splitMode", "custom");

    resetForm();

    const { form } = useExpenseStore.getState();
    expect(form.title).toBe("");
    expect(form.amount).toBe("");
    expect(form.splitMode).toBe("equal");
  });

  it("manages selected expense id", () => {
    const { setSelectedExpenseId } = useExpenseStore.getState();
    setSelectedExpenseId("expense-123");
    expect(useExpenseStore.getState().selectedExpenseId).toBe("expense-123");

    setSelectedExpenseId(null);
    expect(useExpenseStore.getState().selectedExpenseId).toBeNull();
  });

  it("manages status filter", () => {
    const { setStatusFilter } = useExpenseStore.getState();
    setStatusFilter("draft");
    expect(useExpenseStore.getState().statusFilter).toBe("draft");

    setStatusFilter("confirmed");
    expect(useExpenseStore.getState().statusFilter).toBe("confirmed");

    setStatusFilter("all");
    expect(useExpenseStore.getState().statusFilter).toBe("all");
  });

  it("manages active tab", () => {
    const { setActiveTab } = useExpenseStore.getState();
    setActiveTab("balances");
    expect(useExpenseStore.getState().activeTab).toBe("balances");

    setActiveTab("settlements");
    expect(useExpenseStore.getState().activeTab).toBe("settlements");

    setActiveTab("expenses");
    expect(useExpenseStore.getState().activeTab).toBe("expenses");
  });

  it("sets participants list", () => {
    const { setFormField } = useExpenseStore.getState();
    const participants = ["user-1", "user-2", "user-3"];
    setFormField("participants", participants);

    expect(useExpenseStore.getState().form.participants).toEqual(participants);
  });

  it("sets split mode", () => {
    const { setFormField } = useExpenseStore.getState();
    setFormField("splitMode", "percentage");
    expect(useExpenseStore.getState().form.splitMode).toBe("percentage");

    setFormField("splitMode", "custom");
    expect(useExpenseStore.getState().form.splitMode).toBe("custom");
  });
});
