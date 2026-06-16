import { useHouseholdStore } from "./householdStore";
import { HouseholdMember, HouseholdSettings } from "@hausly/types";

// Reset store state between tests
beforeEach(() => {
  useHouseholdStore.getState().clear();
});

const mockSettings: HouseholdSettings = {
  default_currency: "EUR",
  enabled_modules: ["grocery", "expense", "meal", "chores"],
  notification_level: "medium",
};

const mockMembers: HouseholdMember[] = [
  { user_id: "u1", display_name: "Alice", role: "admin", joined_at: "2024-01-01T00:00:00Z" },
  { user_id: "u2", display_name: "Bob", role: "member", joined_at: "2024-01-02T00:00:00Z" },
];

describe("householdStore", () => {
  // Success criterion: Household data loaded and available to all screens
  test("setHousehold_with_valid_data_populates_all_fields", () => {
    useHouseholdStore.getState().setHousehold({
      id: "hh-123",
      name: "Our Home",
      inviteCode: "ABC123",
      members: mockMembers,
      settings: mockSettings,
    });

    const state = useHouseholdStore.getState();
    expect(state.id).toBe("hh-123");
    expect(state.name).toBe("Our Home");
    expect(state.inviteCode).toBe("ABC123");
    expect(state.members).toHaveLength(2);
    expect(state.members[0].display_name).toBe("Alice");
    expect(state.settings).toEqual(mockSettings);
  });

  // Success criterion: Household data available — verify settings include enabled_modules
  test("setHousehold_settings_contains_enabled_modules_for_tab_visibility", () => {
    useHouseholdStore.getState().setHousehold({
      id: "hh-1",
      name: "Test",
      inviteCode: "XYZ",
      members: mockMembers,
      settings: mockSettings,
    });

    const modules = useHouseholdStore.getState().settings?.enabled_modules;
    expect(modules).toContain("grocery");
    expect(modules).toContain("expense");
    expect(modules).toContain("meal");
    expect(modules).toContain("chores");
  });

  // Edge case: clear resets all fields
  test("clear_resets_all_household_state_to_null", () => {
    useHouseholdStore.getState().setHousehold({
      id: "hh-1",
      name: "Test",
      inviteCode: "XYZ",
      members: mockMembers,
      settings: mockSettings,
    });

    useHouseholdStore.getState().clear();

    const state = useHouseholdStore.getState();
    expect(state.id).toBeNull();
    expect(state.name).toBeNull();
    expect(state.inviteCode).toBeNull();
    expect(state.members).toEqual([]);
    expect(state.settings).toBeNull();
  });

  // Edge case: setHousehold overwrites previous state entirely
  test("setHousehold_overwrites_previous_household_data", () => {
    useHouseholdStore.getState().setHousehold({
      id: "hh-1",
      name: "First",
      inviteCode: "A",
      members: mockMembers,
      settings: mockSettings,
    });

    useHouseholdStore.getState().setHousehold({
      id: "hh-2",
      name: "Second",
      inviteCode: "B",
      members: [mockMembers[0]],
      settings: { ...mockSettings, enabled_modules: ["grocery"] },
    });

    const state = useHouseholdStore.getState();
    expect(state.id).toBe("hh-2");
    expect(state.name).toBe("Second");
    expect(state.members).toHaveLength(1);
    expect(state.settings?.enabled_modules).toEqual(["grocery"]);
  });

  // Edge case: initial state is all null/empty
  test("initial_state_has_null_household_data", () => {
    const state = useHouseholdStore.getState();
    expect(state.id).toBeNull();
    expect(state.name).toBeNull();
    expect(state.inviteCode).toBeNull();
    expect(state.members).toEqual([]);
    expect(state.settings).toBeNull();
  });
});
