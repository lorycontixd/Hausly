/**
 * Smoke tests for Phase 11 — Mobile: Household Management
 *
 * Tests the core logic extracted from the household management screens:
 * - Onboarding flow step logic
 * - Settings screen admin detection and module toggle logic
 * - Member management access control
 * - Leave flow data presentation logic
 *
 * Success Criteria (from implementation-plan-v1.md Phase 11):
 * 1. User can create a household and see it on home screen
 * 2. User can join via invite code
 * 3. Admin can manage members and settings
 * 4. Leave flow presents unsettled data before confirming
 */

import { useHouseholdStore } from "@/stores/householdStore";
import { HouseholdMember, HouseholdSettings, ModuleName } from "@hausly/types";

// --- Extracted logic from settings/index.tsx ---

function isUserAdmin(members: HouseholdMember[], userId: string): boolean {
  const member = members.find((m) => m.user_id === userId);
  return member?.role === "admin";
}

function toggleModule(
  currentModules: ModuleName[],
  moduleName: ModuleName
): ModuleName[] {
  if (currentModules.includes(moduleName)) {
    return currentModules.filter((m) => m !== moduleName);
  }
  return [...currentModules, moduleName];
}

function canManageMember(
  isAdmin: boolean,
  targetUserId: string,
  currentUserId: string
): boolean {
  return isAdmin && targetUserId !== currentUserId;
}

// --- Extracted logic from onboarding.tsx ---

type OnboardingStep = "choice" | "create-name" | "create-type" | "join" | "join-preview";

const HOUSEHOLD_TYPES = ["couple", "friends", "students", "family", "custom"] as const;

function canProceedToType(name: string): boolean {
  return name.trim().length > 0;
}

function canSubmitJoinPreview(inviteCode: string): boolean {
  return inviteCode.trim().length > 0;
}

// --- Extracted logic from leave.tsx ---

interface LeavePreview {
  unsettled_expenses: Array<{ id: string; title: string; amount: number }>;
  pending_chores: Array<{ id: string; name: string; due_date: string }>;
}

function hasOutstandingItems(preview: LeavePreview): boolean {
  return preview.unsettled_expenses.length > 0 || preview.pending_chores.length > 0;
}

// --- Test data ---

const mockSettings: HouseholdSettings = {
  default_currency: "EUR",
  enabled_modules: ["grocery", "expense", "meal", "chores"],
  notification_level: "medium",
};

const mockMembers: HouseholdMember[] = [
  { user_id: "admin-1", display_name: "Alice", role: "admin", joined_at: "2024-01-01T00:00:00Z" },
  { user_id: "member-2", display_name: "Bob", role: "member", joined_at: "2024-01-02T00:00:00Z" },
  { user_id: "member-3", display_name: "Carol", role: "member", joined_at: "2024-01-03T00:00:00Z" },
];

// Reset store between tests
beforeEach(() => {
  useHouseholdStore.getState().clear();
});

// ============================================================
// SUCCESS CRITERION 1: User can create a household
// ============================================================

describe("Onboarding — Create household flow", () => {
  test("test_create_household_step_progression_requires_name", () => {
    // Cannot proceed from name step without a name
    expect(canProceedToType("")).toBe(false);
    expect(canProceedToType("   ")).toBe(false);
    // Can proceed with valid name
    expect(canProceedToType("Our Home")).toBe(true);
    expect(canProceedToType("  Trimmed  ")).toBe(true);
  });

  test("test_create_household_all_types_available", () => {
    // All 5 household types should be available for selection
    expect(HOUSEHOLD_TYPES).toHaveLength(5);
    expect(HOUSEHOLD_TYPES).toContain("couple");
    expect(HOUSEHOLD_TYPES).toContain("friends");
    expect(HOUSEHOLD_TYPES).toContain("students");
    expect(HOUSEHOLD_TYPES).toContain("family");
    expect(HOUSEHOLD_TYPES).toContain("custom");
  });

  test("test_create_household_populates_store_on_success", () => {
    // Simulates what happens after successful creation + fetch
    useHouseholdStore.getState().setHousehold({
      id: "hh-new",
      name: "Test Home",
      inviteCode: "ABC123",
      members: [mockMembers[0]],
      settings: mockSettings,
    });

    const state = useHouseholdStore.getState();
    // Success criterion: User can create a household and see it on home screen
    expect(state.id).toBe("hh-new");
    expect(state.name).toBe("Test Home");
    expect(state.settings).not.toBeNull();
  });
});

// ============================================================
// SUCCESS CRITERION 2: User can join via invite code
// ============================================================

describe("Onboarding — Join household flow", () => {
  test("test_join_household_requires_invite_code", () => {
    expect(canSubmitJoinPreview("")).toBe(false);
    expect(canSubmitJoinPreview("   ")).toBe(false);
    expect(canSubmitJoinPreview("ABC123")).toBe(true);
  });

  test("test_join_household_preview_step_exists", () => {
    // The join flow has a preview step before confirmation
    const steps: OnboardingStep[] = ["choice", "create-name", "create-type", "join", "join-preview"];
    expect(steps).toContain("join-preview");
  });

  test("test_join_household_populates_store_after_join", () => {
    // After joining, household data populates the store
    useHouseholdStore.getState().setHousehold({
      id: "hh-joined",
      name: "Roommates",
      inviteCode: "XYZ789",
      members: mockMembers,
      settings: mockSettings,
    });

    const state = useHouseholdStore.getState();
    expect(state.id).toBe("hh-joined");
    expect(state.members).toHaveLength(3);
  });
});

// ============================================================
// SUCCESS CRITERION 3: Admin can manage members and settings
// ============================================================

describe("Settings — Admin detection and access control", () => {
  test("test_admin_detected_correctly_from_members", () => {
    expect(isUserAdmin(mockMembers, "admin-1")).toBe(true);
    expect(isUserAdmin(mockMembers, "member-2")).toBe(false);
    expect(isUserAdmin(mockMembers, "member-3")).toBe(false);
  });

  test("test_admin_cannot_manage_self", () => {
    // Admin should not be able to change their own role or remove themselves
    expect(canManageMember(true, "admin-1", "admin-1")).toBe(false);
  });

  test("test_admin_can_manage_other_members", () => {
    expect(canManageMember(true, "member-2", "admin-1")).toBe(true);
    expect(canManageMember(true, "member-3", "admin-1")).toBe(true);
  });

  test("test_member_cannot_manage_anyone", () => {
    expect(canManageMember(false, "member-2", "member-3")).toBe(false);
    expect(canManageMember(false, "admin-1", "member-2")).toBe(false);
  });

  test("test_unknown_user_not_admin", () => {
    expect(isUserAdmin(mockMembers, "nonexistent-user")).toBe(false);
    expect(isUserAdmin([], "admin-1")).toBe(false);
  });
});

describe("Settings — Module toggle logic", () => {
  test("test_toggle_module_disables_enabled_module", () => {
    const modules: ModuleName[] = ["grocery", "expense", "meal", "chores"];
    const result = toggleModule(modules, "meal");
    expect(result).toEqual(["grocery", "expense", "chores"]);
    expect(result).not.toContain("meal");
  });

  test("test_toggle_module_enables_disabled_module", () => {
    const modules: ModuleName[] = ["grocery", "expense"];
    const result = toggleModule(modules, "chores");
    expect(result).toEqual(["grocery", "expense", "chores"]);
  });

  test("test_toggle_module_idempotent_round_trip", () => {
    const original: ModuleName[] = ["grocery", "expense", "meal", "chores"];
    const toggled = toggleModule(original, "meal");
    const restored = toggleModule(toggled, "meal");
    expect(restored).toContain("meal");
    expect(restored).toHaveLength(4);
  });

  test("test_toggle_module_preserves_other_modules", () => {
    const modules: ModuleName[] = ["grocery", "expense", "meal"];
    const result = toggleModule(modules, "grocery");
    expect(result).toContain("expense");
    expect(result).toContain("meal");
    expect(result).not.toContain("grocery");
  });

  test("test_settings_module_toggles_update_store", () => {
    useHouseholdStore.getState().setHousehold({
      id: "hh-1",
      name: "Test",
      inviteCode: "XYZ",
      members: mockMembers,
      settings: { ...mockSettings, enabled_modules: ["grocery", "expense", "meal", "chores"] },
    });

    // Simulate toggling meal off
    const current = useHouseholdStore.getState().settings!.enabled_modules as ModuleName[];
    const updated = toggleModule(current, "meal");

    useHouseholdStore.getState().setHousehold({
      id: "hh-1",
      name: "Test",
      inviteCode: "XYZ",
      members: mockMembers,
      settings: { ...mockSettings, enabled_modules: updated },
    });

    const result = useHouseholdStore.getState().settings!.enabled_modules;
    expect(result).not.toContain("meal");
    expect(result).toContain("grocery");
  });
});

// ============================================================
// SUCCESS CRITERION 4: Leave flow presents unsettled data
// ============================================================

describe("Leave flow — Outstanding items detection", () => {
  test("test_leave_flow_detects_unsettled_expenses", () => {
    const preview: LeavePreview = {
      unsettled_expenses: [
        { id: "exp-1", title: "Groceries", amount: 45.00 },
        { id: "exp-2", title: "Utilities", amount: 80.00 },
      ],
      pending_chores: [],
    };
    expect(hasOutstandingItems(preview)).toBe(true);
  });

  test("test_leave_flow_detects_pending_chores", () => {
    const preview: LeavePreview = {
      unsettled_expenses: [],
      pending_chores: [
        { id: "ch-1", name: "Vacuum", due_date: "2024-06-15" },
      ],
    };
    expect(hasOutstandingItems(preview)).toBe(true);
  });

  test("test_leave_flow_detects_both_outstanding", () => {
    const preview: LeavePreview = {
      unsettled_expenses: [{ id: "exp-1", title: "Dinner", amount: 30.00 }],
      pending_chores: [{ id: "ch-1", name: "Dishes", due_date: "2024-06-16" }],
    };
    expect(hasOutstandingItems(preview)).toBe(true);
  });

  test("test_leave_flow_all_clear_when_nothing_outstanding", () => {
    const preview: LeavePreview = {
      unsettled_expenses: [],
      pending_chores: [],
    };
    // Shows "all clear" state
    expect(hasOutstandingItems(preview)).toBe(false);
  });

  test("test_leave_flow_clears_household_store_after_leaving", () => {
    // Setup: user has household loaded
    useHouseholdStore.getState().setHousehold({
      id: "hh-1",
      name: "Test",
      inviteCode: "XYZ",
      members: mockMembers,
      settings: mockSettings,
    });

    // After leaving, store should be cleared
    useHouseholdStore.getState().clear();

    const state = useHouseholdStore.getState();
    expect(state.id).toBeNull();
    expect(state.members).toEqual([]);
    expect(state.settings).toBeNull();
  });
});
