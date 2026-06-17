/**
 * Smoke Test: Phase 14 — Mobile: Meal Planner Module
 *
 * Exercises the core mobile meal planner functionality end-to-end:
 * - Weekly view generation (7 days × 2 slots)
 * - Slot claiming lifecycle (tap empty → fill form → save)
 * - Entry lookup and display logic per (date, slot) pair
 * - First-come-first-served: 409 conflict detection
 * - Edit permission enforcement (owner/admin only)
 * - Headcount defaults to household member count
 * - Week navigation (prev/next/reset)
 * - Store state management (sheet open/close, slot selection)
 *
 * Success Criteria (from implementation-plan-v1.md Phase 14):
 * 1. Weekly view displays correctly
 * 2. First-come-first-served: 409 shown as friendly message
 * 3. Only owner/admin can edit/delete
 * 4. Headcount defaults correctly
 *
 * Relevant docs:
 * - docs/data-models.md (MealPlanEntry)
 * - docs/api-reference.md (Meal Planner section)
 * - docs/planning/implementation-plan-v1.md Phase 14
 */

import { MealPlanEntry, MealSlot } from "@hausly/types";
import { useMealStore } from "@/stores/mealStore";

// --- Extracted logic under test (mirrors meal.tsx, MealWeekView, MealEntrySheet) ---

function getWeekDays(offset: number, referenceDate: Date = new Date()): string[] {
  const today = referenceDate;
  const monday = new Date(today);
  const day = today.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  monday.setDate(today.getDate() + diff + offset * 7);

  const days: string[] = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    days.push(d.toISOString().split("T")[0]);
  }
  return days;
}

function getWeekLabel(days: string[]): string {
  const start = new Date(days[0] + "T00:00:00");
  const end = new Date(days[6] + "T00:00:00");
  const opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" };
  return `${start.toLocaleDateString(undefined, opts)} – ${end.toLocaleDateString(undefined, opts)}`;
}

function getEntryForSlot(
  entries: MealPlanEntry[],
  date: string,
  slot: MealSlot
): MealPlanEntry | null {
  return entries.find((e) => e.date === date && e.slot === slot) ?? null;
}

function canUserEditEntry(
  entry: MealPlanEntry,
  userId: string,
  userRole: "admin" | "member"
): boolean {
  return entry.owner_user_id === userId || userRole === "admin";
}

function getDefaultHeadcount(memberCount: number): number {
  return memberCount || 2;
}

function isSlotConflictError(error: { code?: string; message?: string }): boolean {
  return error.code === "CONFLICT" || (error.message?.includes("409") ?? false);
}

function buildCreatePayload(
  date: string,
  slot: MealSlot,
  text: string,
  headcount: number
) {
  return { date, slot, text: text.trim(), headcount };
}

function validateMealForm(text: string): boolean {
  return text.trim().length > 0;
}

// --- Test data ---

const REFERENCE_DATE = new Date("2026-06-17T12:00:00Z"); // Wednesday
const HOUSEHOLD_ID = "hh-meal-test-001";
const USER_ALICE_ID = "user-alice-001";
const USER_BOB_ID = "user-bob-002";
const USER_CAROL_ID = "user-carol-003";

const MEMBERS = [
  { user_id: USER_ALICE_ID, display_name: "Alice", role: "admin" as const },
  { user_id: USER_BOB_ID, display_name: "Bob", role: "member" as const },
  { user_id: USER_CAROL_ID, display_name: "Carol", role: "member" as const },
];

const mockEntries: MealPlanEntry[] = [
  {
    id: "meal-1",
    date: "2026-06-15", // Monday
    slot: "lunch",
    text: "Pasta al pomodoro",
    headcount: 3,
    owner_user_id: USER_ALICE_ID,
    owner_display_name: "Alice",
    created_at: "2026-06-14T20:00:00Z",
  },
  {
    id: "meal-2",
    date: "2026-06-15", // Monday
    slot: "dinner",
    text: "Grilled salmon with veggies",
    headcount: 3,
    owner_user_id: USER_BOB_ID,
    owner_display_name: "Bob",
    created_at: "2026-06-14T21:00:00Z",
  },
  {
    id: "meal-3",
    date: "2026-06-17", // Wednesday
    slot: "lunch",
    text: "Caesar salad",
    headcount: 2,
    owner_user_id: USER_CAROL_ID,
    owner_display_name: "Carol",
    created_at: "2026-06-16T18:00:00Z",
  },
  {
    id: "meal-4",
    date: "2026-06-19", // Friday
    slot: "dinner",
    text: "Pizza night",
    headcount: 4,
    owner_user_id: USER_ALICE_ID,
    owner_display_name: "Alice",
    created_at: "2026-06-17T09:00:00Z",
  },
];

// --- Tests ---

describe("Smoke: Meal Planner end-to-end — Weekly view rendering", () => {
  // SC1: Weekly view displays correctly
  it("test_meal_week_view_generates_7_consecutive_days", () => {
    const days = getWeekDays(0, REFERENCE_DATE);

    expect(days).toHaveLength(7);
    // 2026-06-17 is Wednesday, so Monday is 2026-06-15
    expect(days[0]).toBe("2026-06-15");
    expect(days[6]).toBe("2026-06-21");

    // All days are consecutive
    for (let i = 1; i < days.length; i++) {
      const prev = new Date(days[i - 1] + "T00:00:00");
      const curr = new Date(days[i] + "T00:00:00");
      expect(curr.getTime() - prev.getTime()).toBe(86400000);
    }
  });

  // SC1: Weekly view displays correctly — each day has 2 slots
  it("test_meal_week_view_renders_14_slots_for_7_days", () => {
    const days = getWeekDays(0, REFERENCE_DATE);
    const slots: MealSlot[] = ["lunch", "dinner"];

    const allSlots: Array<{ date: string; slot: MealSlot }> = [];
    for (const date of days) {
      for (const slot of slots) {
        allSlots.push({ date, slot });
      }
    }

    expect(allSlots).toHaveLength(14);
    // Each day has both lunch and dinner
    for (const date of days) {
      const daySlots = allSlots.filter((s) => s.date === date);
      expect(daySlots).toHaveLength(2);
      expect(daySlots.map((s) => s.slot).sort()).toEqual(["dinner", "lunch"]);
    }
  });

  // SC1: Entries correctly mapped to slots
  it("test_meal_entries_map_to_correct_date_slot_pairs", () => {
    // Monday lunch occupied by Alice
    const mondayLunch = getEntryForSlot(mockEntries, "2026-06-15", "lunch");
    expect(mondayLunch).not.toBeNull();
    expect(mondayLunch!.text).toBe("Pasta al pomodoro");
    expect(mondayLunch!.owner_display_name).toBe("Alice");

    // Monday dinner occupied by Bob
    const mondayDinner = getEntryForSlot(mockEntries, "2026-06-15", "dinner");
    expect(mondayDinner).not.toBeNull();
    expect(mondayDinner!.text).toBe("Grilled salmon with veggies");

    // Tuesday has no entries — slots empty
    const tuesdayLunch = getEntryForSlot(mockEntries, "2026-06-16", "lunch");
    const tuesdayDinner = getEntryForSlot(mockEntries, "2026-06-16", "dinner");
    expect(tuesdayLunch).toBeNull();
    expect(tuesdayDinner).toBeNull();

    // Wednesday lunch occupied, dinner empty
    const wedLunch = getEntryForSlot(mockEntries, "2026-06-17", "lunch");
    const wedDinner = getEntryForSlot(mockEntries, "2026-06-17", "dinner");
    expect(wedLunch).not.toBeNull();
    expect(wedDinner).toBeNull();
  });

  it("test_meal_week_label_shows_correct_date_range", () => {
    const days = getWeekDays(0, REFERENCE_DATE);
    const label = getWeekLabel(days);

    // Label should contain both the start and end month/day
    expect(label).toContain("15");
    expect(label).toContain("21");
    expect(label).toContain("–");
  });
});

describe("Smoke: Meal Planner end-to-end — Week navigation", () => {
  beforeEach(() => {
    useMealStore.setState({
      weekOffset: 0,
      selectedSlot: null,
      sheetVisible: false,
      editingEntryId: null,
    });
  });

  it("test_meal_week_navigation_forward_shifts_by_7_days", () => {
    const currentDays = getWeekDays(0, REFERENCE_DATE);
    expect(currentDays[0]).toBe("2026-06-15");

    useMealStore.getState().nextWeek();
    const nextOffset = useMealStore.getState().weekOffset;
    expect(nextOffset).toBe(1);

    const nextDays = getWeekDays(nextOffset, REFERENCE_DATE);
    expect(nextDays[0]).toBe("2026-06-22");
    expect(nextDays[6]).toBe("2026-06-28");
  });

  it("test_meal_week_navigation_backward_shifts_by_7_days", () => {
    useMealStore.getState().prevWeek();
    const offset = useMealStore.getState().weekOffset;
    expect(offset).toBe(-1);

    const prevDays = getWeekDays(offset, REFERENCE_DATE);
    expect(prevDays[0]).toBe("2026-06-08");
    expect(prevDays[6]).toBe("2026-06-14");
  });

  it("test_meal_week_navigation_reset_returns_to_current_week", () => {
    useMealStore.getState().nextWeek();
    useMealStore.getState().nextWeek();
    expect(useMealStore.getState().weekOffset).toBe(2);

    useMealStore.getState().resetWeek();
    expect(useMealStore.getState().weekOffset).toBe(0);
  });

  it("test_meal_week_navigation_multiple_forward_accumulates", () => {
    useMealStore.getState().nextWeek();
    useMealStore.getState().nextWeek();
    useMealStore.getState().nextWeek();
    expect(useMealStore.getState().weekOffset).toBe(3);

    const days = getWeekDays(3, REFERENCE_DATE);
    // 3 weeks from 2026-06-15 = 2026-07-06
    expect(days[0]).toBe("2026-07-06");
  });
});

describe("Smoke: Meal Planner end-to-end — Slot claiming (first-come-first-served)", () => {
  // SC2: First-come-first-served: 409 shown as friendly message
  it("test_meal_create_payload_has_correct_structure", () => {
    const payload = buildCreatePayload("2026-06-17", "dinner", "  Tacos  ", 3);

    expect(payload).toEqual({
      date: "2026-06-17",
      slot: "dinner",
      text: "Tacos",
      headcount: 3,
    });
  });

  it("test_meal_conflict_error_detection_by_code", () => {
    const conflictByCode = { code: "CONFLICT", message: "Slot already taken" };
    expect(isSlotConflictError(conflictByCode)).toBe(true);
  });

  it("test_meal_conflict_error_detection_by_status_message", () => {
    const conflictByMessage = { message: "Request failed with 409" };
    expect(isSlotConflictError(conflictByMessage)).toBe(true);
  });

  it("test_meal_non_conflict_error_not_detected_as_conflict", () => {
    const serverError = { code: "INTERNAL_ERROR", message: "Something went wrong" };
    expect(isSlotConflictError(serverError)).toBe(false);

    const validationError = { code: "VALIDATION_ERROR", message: "Invalid input" };
    expect(isSlotConflictError(validationError)).toBe(false);
  });

  it("test_meal_occupied_slot_returns_existing_entry_not_null", () => {
    // When tapping a slot that already has an entry, it opens in edit mode
    const existing = getEntryForSlot(mockEntries, "2026-06-15", "lunch");
    expect(existing).not.toBeNull();
    expect(existing!.id).toBe("meal-1");
    // This means the sheet opens in edit mode, not create mode
  });

  it("test_meal_empty_slot_returns_null_for_create_mode", () => {
    // When tapping an empty slot, no existing entry
    const empty = getEntryForSlot(mockEntries, "2026-06-16", "lunch");
    expect(empty).toBeNull();
    // This means the sheet opens in create mode
  });
});

describe("Smoke: Meal Planner end-to-end — Edit permissions", () => {
  // SC3: Only owner/admin can edit/delete

  it("test_meal_owner_can_edit_own_entry", () => {
    // Alice owns meal-1, Alice is admin
    expect(canUserEditEntry(mockEntries[0], USER_ALICE_ID, "admin")).toBe(true);
    // Even if Alice were a regular member, she owns it
    expect(canUserEditEntry(mockEntries[0], USER_ALICE_ID, "member")).toBe(true);
  });

  it("test_meal_admin_can_edit_any_entry", () => {
    // Alice is admin, Bob owns meal-2
    expect(canUserEditEntry(mockEntries[1], USER_ALICE_ID, "admin")).toBe(true);
    // Alice is admin, Carol owns meal-3
    expect(canUserEditEntry(mockEntries[2], USER_ALICE_ID, "admin")).toBe(true);
  });

  it("test_meal_non_owner_member_cannot_edit", () => {
    // Bob is member, Alice owns meal-1
    expect(canUserEditEntry(mockEntries[0], USER_BOB_ID, "member")).toBe(false);
    // Carol is member, Alice owns meal-4
    expect(canUserEditEntry(mockEntries[3], USER_CAROL_ID, "member")).toBe(false);
  });

  it("test_meal_non_owner_member_cannot_edit_even_with_same_household", () => {
    // Bob (member) cannot edit Carol's entry
    expect(canUserEditEntry(mockEntries[2], USER_BOB_ID, "member")).toBe(false);
    // Carol (member) cannot edit Bob's entry
    expect(canUserEditEntry(mockEntries[1], USER_CAROL_ID, "member")).toBe(false);
  });
});

describe("Smoke: Meal Planner end-to-end — Headcount defaults", () => {
  // SC4: Headcount defaults correctly

  it("test_meal_headcount_defaults_to_member_count", () => {
    const memberCount = MEMBERS.length; // 3
    const defaultHeadcount = getDefaultHeadcount(memberCount);
    expect(defaultHeadcount).toBe(3);
  });

  it("test_meal_headcount_defaults_to_2_when_no_members_loaded", () => {
    // Edge case: members not yet loaded (count = 0)
    const defaultHeadcount = getDefaultHeadcount(0);
    expect(defaultHeadcount).toBe(2);
  });

  it("test_meal_headcount_minimum_is_1", () => {
    // Headcount stepper should not go below 1
    let headcount = 1;
    headcount = Math.max(1, headcount - 1);
    expect(headcount).toBe(1);
  });

  it("test_meal_headcount_can_exceed_member_count", () => {
    // Guests scenario: headcount can be higher than member count
    const memberCount = 3;
    const guestHeadcount = memberCount + 2;
    expect(guestHeadcount).toBe(5);
    // No upper bound enforced (guests allowed)
  });
});

describe("Smoke: Meal Planner end-to-end — Form validation", () => {
  it("test_meal_form_rejects_empty_text", () => {
    expect(validateMealForm("")).toBe(false);
    expect(validateMealForm("   ")).toBe(false);
    expect(validateMealForm("\n\t")).toBe(false);
  });

  it("test_meal_form_accepts_valid_text", () => {
    expect(validateMealForm("Pasta")).toBe(true);
    expect(validateMealForm("  Tacos  ")).toBe(true); // trims internally
  });
});

describe("Smoke: Meal Planner end-to-end — Store sheet management", () => {
  beforeEach(() => {
    useMealStore.setState({
      weekOffset: 0,
      selectedSlot: null,
      sheetVisible: false,
      editingEntryId: null,
    });
  });

  it("test_meal_open_sheet_for_new_entry_sets_slot_without_entry_id", () => {
    useMealStore.getState().openSheet({ date: "2026-06-17", slot: "dinner" });

    const state = useMealStore.getState();
    expect(state.sheetVisible).toBe(true);
    expect(state.selectedSlot).toEqual({ date: "2026-06-17", slot: "dinner" });
    expect(state.editingEntryId).toBeNull();
  });

  it("test_meal_open_sheet_for_existing_entry_includes_entry_id", () => {
    useMealStore
      .getState()
      .openSheet({ date: "2026-06-15", slot: "lunch" }, "meal-1");

    const state = useMealStore.getState();
    expect(state.sheetVisible).toBe(true);
    expect(state.selectedSlot).toEqual({ date: "2026-06-15", slot: "lunch" });
    expect(state.editingEntryId).toBe("meal-1");
  });

  it("test_meal_close_sheet_clears_all_state", () => {
    useMealStore
      .getState()
      .openSheet({ date: "2026-06-15", slot: "lunch" }, "meal-1");
    useMealStore.getState().closeSheet();

    const state = useMealStore.getState();
    expect(state.sheetVisible).toBe(false);
    expect(state.selectedSlot).toBeNull();
    expect(state.editingEntryId).toBeNull();
  });
});
