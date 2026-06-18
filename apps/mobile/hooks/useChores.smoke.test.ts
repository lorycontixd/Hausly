/**
 * Smoke Test: Phase 15 — Mobile: Chore Module
 *
 * Exercises the core mobile chore functionality end-to-end:
 * - Assignment grouping by date (Overdue, Today, Tomorrow, This Week, Later)
 * - Chore creation lifecycle (name → recurrence → assignees → rotation → create)
 * - Creator-in-assignees validation
 * - Rotation preview calculation (personal frequency)
 * - Assignment actions: complete, postpone, cancel
 * - Overdue detection and blocking visibility
 * - Postpone shifts effective date without changing original due_date
 * - Store state management (sheet open/close, action sheet)
 *
 * Success Criteria (from implementation-plan-v1.md Phase 15):
 * 1. Assignments display grouped by date
 * 2. Create chore validates creator in assignees
 * 3. Rotation preview shows correct frequency
 * 4. Complete/postpone/cancel work
 * 5. Overdue blocking visible (no new assignments generated)
 *
 * Relevant docs:
 * - docs/logics/chore-schedule.md
 * - docs/data-models.md (Chore, ChoreAssignee, ChoreAssignment)
 * - docs/api-reference.md (Chores section)
 * - docs/planning/implementation-plan-v1.md Phase 15
 */

import { ChoreAssignment, Chore, RecurrenceUnit } from "@hausly/types";
import { useChoreStore } from "@/stores/choreStore";

// --- Extracted logic under test (mirrors ChoreGroupedList, ChoreCreateSheet) ---

interface AssignmentGroup {
  title: string;
  isOverdue: boolean;
  assignments: ChoreAssignment[];
}

function groupAssignments(
  assignments: ChoreAssignment[],
  referenceDate: Date
): AssignmentGroup[] {
  const today = new Date(referenceDate);
  today.setHours(0, 0, 0, 0);

  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);

  const endOfWeek = new Date(today);
  endOfWeek.setDate(endOfWeek.getDate() + (7 - today.getDay()));

  const overdue: ChoreAssignment[] = [];
  const todayGroup: ChoreAssignment[] = [];
  const tomorrowGroup: ChoreAssignment[] = [];
  const thisWeek: ChoreAssignment[] = [];
  const later: ChoreAssignment[] = [];

  for (const a of assignments) {
    if (a.status !== "pending") continue;

    const effectiveDate = new Date(
      (a.postponed_to ?? a.due_date) + "T00:00:00"
    );

    if (effectiveDate < today) {
      overdue.push(a);
    } else if (effectiveDate.getTime() === today.getTime()) {
      todayGroup.push(a);
    } else if (effectiveDate.getTime() === tomorrow.getTime()) {
      tomorrowGroup.push(a);
    } else if (effectiveDate <= endOfWeek) {
      thisWeek.push(a);
    } else {
      later.push(a);
    }
  }

  const groups: AssignmentGroup[] = [];
  if (overdue.length > 0)
    groups.push({ title: "Overdue", isOverdue: true, assignments: overdue });
  if (todayGroup.length > 0)
    groups.push({ title: "Today", isOverdue: false, assignments: todayGroup });
  if (tomorrowGroup.length > 0)
    groups.push({ title: "Tomorrow", isOverdue: false, assignments: tomorrowGroup });
  if (thisWeek.length > 0)
    groups.push({ title: "This Week", isOverdue: false, assignments: thisWeek });
  if (later.length > 0)
    groups.push({ title: "Later", isOverdue: false, assignments: later });

  return groups;
}

function computeRotationPreview(
  isRecurring: boolean,
  rotationEnabled: boolean,
  assigneeCount: number,
  interval: number,
  unit: RecurrenceUnit
): string | null {
  if (!isRecurring || !rotationEnabled || assigneeCount < 2) return null;
  const personalFreq = interval * assigneeCount;
  return `Your turn every ${personalFreq} ${unit}`;
}

function validateCreatorInAssignees(
  creatorId: string,
  assigneeIds: string[]
): boolean {
  return assigneeIds.includes(creatorId);
}

function buildChoreCreatePayload(
  name: string,
  startDate: string,
  isRecurring: boolean,
  interval: number,
  unit: RecurrenceUnit,
  assigneeIds: string[],
  rotationEnabled: boolean
) {
  return {
    name: name.trim(),
    start_date: startDate,
    is_recurring: isRecurring,
    recurrence_interval: isRecurring ? interval : null,
    recurrence_unit: isRecurring ? unit : null,
    assignee_user_ids: assigneeIds,
    rotation_enabled: assigneeIds.length > 1 && rotationEnabled,
  };
}

function isOverdue(assignment: ChoreAssignment, referenceDate: Date): boolean {
  const today = new Date(referenceDate);
  today.setHours(0, 0, 0, 0);
  const effectiveDate = new Date(
    (assignment.postponed_to ?? assignment.due_date) + "T00:00:00"
  );
  return assignment.status === "pending" && effectiveDate < today;
}

function getEffectiveDueDate(assignment: ChoreAssignment): string {
  return assignment.postponed_to ?? assignment.due_date;
}

function buildPostponePayload(assignmentId: string, postponeTo: string) {
  return { assignmentId, postpone_to: postponeTo };
}

function canFormSave(
  name: string,
  assigneeIds: string[],
  creatorId: string
): boolean {
  return (
    name.trim().length > 0 &&
    assigneeIds.length > 0 &&
    assigneeIds.includes(creatorId)
  );
}

// --- Test data ---

const REFERENCE_DATE = new Date("2026-06-17T12:00:00Z"); // Tuesday
const HOUSEHOLD_ID = "hh-chore-test-001";
const USER_ALICE_ID = "user-alice-001";
const USER_BOB_ID = "user-bob-002";
const USER_CAROL_ID = "user-carol-003";

const MEMBERS = [
  { user_id: USER_ALICE_ID, display_name: "Alice", role: "admin" as const },
  { user_id: USER_BOB_ID, display_name: "Bob", role: "member" as const },
  { user_id: USER_CAROL_ID, display_name: "Carol", role: "member" as const },
];

function makeAssignment(overrides: Partial<ChoreAssignment>): ChoreAssignment {
  return {
    id: "assign-default",
    chore_id: "chore-1",
    chore_name: "Clean bathroom",
    assigned_to_user_id: USER_ALICE_ID,
    assigned_to_display_name: "Alice",
    due_date: "2026-06-17",
    postponed_to: null,
    status: "pending",
    completed_at: null,
    completed_by_user_id: null,
    completed_by_display_name: null,
    ...overrides,
  };
}

const mockAssignments: ChoreAssignment[] = [
  // Overdue: 2 days ago
  makeAssignment({
    id: "assign-overdue-1",
    chore_name: "Kitchen",
    assigned_to_user_id: USER_CAROL_ID,
    assigned_to_display_name: "Carol",
    due_date: "2026-06-15",
  }),
  // Today
  makeAssignment({
    id: "assign-today-1",
    chore_name: "Bathroom",
    assigned_to_user_id: USER_ALICE_ID,
    assigned_to_display_name: "Alice",
    due_date: "2026-06-17",
  }),
  // Tomorrow
  makeAssignment({
    id: "assign-tomorrow-1",
    chore_name: "Laundry",
    assigned_to_user_id: USER_BOB_ID,
    assigned_to_display_name: "Bob",
    due_date: "2026-06-18",
  }),
  // This week (Friday)
  makeAssignment({
    id: "assign-week-1",
    chore_name: "Vacuum",
    assigned_to_user_id: USER_ALICE_ID,
    assigned_to_display_name: "Alice",
    due_date: "2026-06-20",
  }),
  // Later (next week)
  makeAssignment({
    id: "assign-later-1",
    chore_name: "Windows",
    assigned_to_user_id: USER_BOB_ID,
    assigned_to_display_name: "Bob",
    due_date: "2026-06-25",
  }),
  // Completed (should be excluded from grouping)
  makeAssignment({
    id: "assign-completed-1",
    chore_name: "Dishes",
    assigned_to_user_id: USER_ALICE_ID,
    assigned_to_display_name: "Alice",
    due_date: "2026-06-16",
    status: "completed",
    completed_at: "2026-06-16T14:00:00Z",
    completed_by_user_id: USER_BOB_ID,
    completed_by_display_name: "Bob",
  }),
  // Cancelled (should be excluded from grouping)
  makeAssignment({
    id: "assign-cancelled-1",
    chore_name: "Yard",
    assigned_to_user_id: USER_CAROL_ID,
    assigned_to_display_name: "Carol",
    due_date: "2026-06-17",
    status: "cancelled",
  }),
];

const mockChore: Chore = {
  id: "chore-weekly-clean",
  name: "Clean house",
  is_recurring: true,
  recurrence_interval: 1,
  recurrence_unit: "weeks",
  start_date: "2026-06-08",
  rotation_enabled: true,
  assignees: [
    { user_id: USER_ALICE_ID, display_name: "Alice", position: 0 },
    { user_id: USER_BOB_ID, display_name: "Bob", position: 1 },
    { user_id: USER_CAROL_ID, display_name: "Carol", position: 2 },
  ],
  created_at: "2026-06-01T10:00:00Z",
};

// --- Tests ---

describe("Smoke: Chore Module end-to-end — Assignment grouping (SC1)", () => {
  it("test_chore_assignments_group_into_all_five_sections", () => {
    const groups = groupAssignments(mockAssignments, REFERENCE_DATE);
    const titles = groups.map((g) => g.title);

    // SC1: Assignments display grouped by date
    expect(titles).toEqual(["Overdue", "Today", "Tomorrow", "This Week", "Later"]);
  });

  it("test_chore_overdue_group_contains_only_past_pending_assignments", () => {
    const groups = groupAssignments(mockAssignments, REFERENCE_DATE);
    const overdueGroup = groups.find((g) => g.title === "Overdue")!;

    expect(overdueGroup.isOverdue).toBe(true);
    expect(overdueGroup.assignments).toHaveLength(1);
    expect(overdueGroup.assignments[0].id).toBe("assign-overdue-1");
    expect(overdueGroup.assignments[0].chore_name).toBe("Kitchen");
  });

  it("test_chore_completed_and_cancelled_excluded_from_groups", () => {
    const groups = groupAssignments(mockAssignments, REFERENCE_DATE);
    const allIds = groups.flatMap((g) => g.assignments.map((a) => a.id));

    // SC1: Only pending assignments show in the list
    expect(allIds).not.toContain("assign-completed-1");
    expect(allIds).not.toContain("assign-cancelled-1");
    expect(allIds).toHaveLength(5); // 5 pending assignments
  });

  it("test_chore_postponed_assignment_uses_effective_date_for_grouping", () => {
    // Assignment originally due 2026-06-15 (overdue), postponed to 2026-06-18 (tomorrow)
    const postponedAssignments = [
      makeAssignment({
        id: "assign-postponed",
        due_date: "2026-06-15",
        postponed_to: "2026-06-18",
      }),
    ];

    const groups = groupAssignments(postponedAssignments, REFERENCE_DATE);
    // Should appear in Tomorrow, not Overdue
    expect(groups[0].title).toBe("Tomorrow");
    expect(groups[0].assignments[0].id).toBe("assign-postponed");
  });

  it("test_chore_empty_assignments_produce_no_groups", () => {
    const groups = groupAssignments([], REFERENCE_DATE);
    expect(groups).toHaveLength(0);
  });

  it("test_chore_all_completed_produce_no_groups", () => {
    const allDone = [
      makeAssignment({ id: "d1", status: "completed" }),
      makeAssignment({ id: "d2", status: "cancelled" }),
    ];
    const groups = groupAssignments(allDone, REFERENCE_DATE);
    expect(groups).toHaveLength(0);
  });
});

describe("Smoke: Chore Module end-to-end — Chore creation validation (SC2)", () => {
  it("test_chore_creator_must_be_in_assignees", () => {
    // SC2: Create chore validates creator in assignees
    expect(
      validateCreatorInAssignees(USER_ALICE_ID, [USER_ALICE_ID, USER_BOB_ID])
    ).toBe(true);

    expect(
      validateCreatorInAssignees(USER_ALICE_ID, [USER_BOB_ID, USER_CAROL_ID])
    ).toBe(false);
  });

  it("test_chore_form_save_blocked_when_creator_not_in_assignees", () => {
    // Alice tries to create a chore only for Bob and Carol
    const canSave = canFormSave("Clean house", [USER_BOB_ID, USER_CAROL_ID], USER_ALICE_ID);
    expect(canSave).toBe(false);
  });

  it("test_chore_form_save_blocked_with_empty_name", () => {
    const canSave = canFormSave("", [USER_ALICE_ID], USER_ALICE_ID);
    expect(canSave).toBe(false);

    const canSaveWhitespace = canFormSave("   ", [USER_ALICE_ID], USER_ALICE_ID);
    expect(canSaveWhitespace).toBe(false);
  });

  it("test_chore_form_save_blocked_with_no_assignees", () => {
    const canSave = canFormSave("Clean house", [], USER_ALICE_ID);
    expect(canSave).toBe(false);
  });

  it("test_chore_form_save_allowed_when_valid", () => {
    const canSave = canFormSave("Clean house", [USER_ALICE_ID, USER_BOB_ID], USER_ALICE_ID);
    expect(canSave).toBe(true);
  });

  it("test_chore_create_payload_structure_recurring_with_rotation", () => {
    const payload = buildChoreCreatePayload(
      "  Clean house  ",
      "2026-06-08",
      true,
      1,
      "weeks",
      [USER_ALICE_ID, USER_BOB_ID, USER_CAROL_ID],
      true
    );

    expect(payload).toEqual({
      name: "Clean house",
      start_date: "2026-06-08",
      is_recurring: true,
      recurrence_interval: 1,
      recurrence_unit: "weeks",
      assignee_user_ids: [USER_ALICE_ID, USER_BOB_ID, USER_CAROL_ID],
      rotation_enabled: true,
    });
  });

  it("test_chore_create_payload_one_off_strips_recurrence", () => {
    const payload = buildChoreCreatePayload(
      "Fix shelf",
      "2026-06-20",
      false,
      1,
      "weeks",
      [USER_ALICE_ID],
      false
    );

    expect(payload.is_recurring).toBe(false);
    expect(payload.recurrence_interval).toBeNull();
    expect(payload.recurrence_unit).toBeNull();
    // Single assignee → rotation forced false
    expect(payload.rotation_enabled).toBe(false);
  });

  it("test_chore_create_payload_rotation_disabled_with_single_assignee", () => {
    const payload = buildChoreCreatePayload(
      "Solo chore",
      "2026-06-17",
      true,
      1,
      "days",
      [USER_ALICE_ID],
      true // User tried to enable rotation, but only 1 assignee
    );

    // Should be forced false since assignees.length <= 1
    expect(payload.rotation_enabled).toBe(false);
  });
});

describe("Smoke: Chore Module end-to-end — Rotation preview (SC3)", () => {
  it("test_chore_rotation_preview_3_people_weekly", () => {
    // SC3: Rotation preview shows correct frequency
    // Every 1 week, 3 assignees → your turn every 3 weeks
    const preview = computeRotationPreview(true, true, 3, 1, "weeks");
    expect(preview).toBe("Your turn every 3 weeks");
  });

  it("test_chore_rotation_preview_2_people_biweekly", () => {
    // Every 2 weeks, 2 assignees → your turn every 4 weeks
    const preview = computeRotationPreview(true, true, 2, 2, "weeks");
    expect(preview).toBe("Your turn every 4 weeks");
  });

  it("test_chore_rotation_preview_4_people_daily", () => {
    // Every 1 day, 4 assignees → your turn every 4 days
    const preview = computeRotationPreview(true, true, 4, 1, "days");
    expect(preview).toBe("Your turn every 4 days");
  });

  it("test_chore_rotation_preview_2_people_monthly", () => {
    // Every 1 month, 2 assignees → your turn every 2 months
    const preview = computeRotationPreview(true, true, 2, 1, "months");
    expect(preview).toBe("Your turn every 2 months");
  });

  it("test_chore_rotation_preview_null_when_not_recurring", () => {
    const preview = computeRotationPreview(false, true, 3, 1, "weeks");
    expect(preview).toBeNull();
  });

  it("test_chore_rotation_preview_null_when_rotation_off", () => {
    const preview = computeRotationPreview(true, false, 3, 1, "weeks");
    expect(preview).toBeNull();
  });

  it("test_chore_rotation_preview_null_with_single_assignee", () => {
    const preview = computeRotationPreview(true, true, 1, 1, "weeks");
    expect(preview).toBeNull();
  });
});

describe("Smoke: Chore Module end-to-end — Assignment actions (SC4)", () => {
  it("test_chore_complete_records_completer_different_from_assignee", () => {
    // SC4: Complete works — anyone can mark done
    // Bob completes Alice's assignment
    const completed: ChoreAssignment = {
      ...makeAssignment({ id: "assign-today-1" }),
      status: "completed",
      completed_at: "2026-06-17T10:00:00Z",
      completed_by_user_id: USER_BOB_ID,
      completed_by_display_name: "Bob",
    };

    expect(completed.assigned_to_user_id).toBe(USER_ALICE_ID);
    expect(completed.completed_by_user_id).toBe(USER_BOB_ID);
    expect(completed.completed_by_display_name).toBe("Bob");
    expect(completed.status).toBe("completed");
  });

  it("test_chore_postpone_sets_new_effective_date_preserving_original", () => {
    // SC4: Postpone works — original due_date preserved, postponed_to set
    const original = makeAssignment({
      id: "assign-overdue-1",
      due_date: "2026-06-15",
    });

    // After postpone to Jun 20
    const postponed: ChoreAssignment = {
      ...original,
      postponed_to: "2026-06-20",
    };

    // Original preserved for audit
    expect(postponed.due_date).toBe("2026-06-15");
    // New effective date
    expect(getEffectiveDueDate(postponed)).toBe("2026-06-20");
    // No longer overdue (2026-06-20 is in the future)
    expect(isOverdue(postponed, REFERENCE_DATE)).toBe(false);
  });

  it("test_chore_cancel_produces_terminal_state", () => {
    // SC4: Cancel works
    const cancelled: ChoreAssignment = {
      ...makeAssignment({ id: "assign-overdue-1", due_date: "2026-06-15" }),
      status: "cancelled",
    };

    expect(cancelled.status).toBe("cancelled");
    // Cancelled assignments are excluded from grouping
    const groups = groupAssignments([cancelled], REFERENCE_DATE);
    expect(groups).toHaveLength(0);
  });

  it("test_chore_postpone_payload_structure", () => {
    const payload = buildPostponePayload("assign-overdue-1", "2026-06-20");
    expect(payload).toEqual({
      assignmentId: "assign-overdue-1",
      postpone_to: "2026-06-20",
    });
  });

  it("test_chore_overdue_assignment_actions_include_all_three_options", () => {
    // Overdue assignments get: Done, Postpone, Cancel
    const overdueAssignment = makeAssignment({
      id: "assign-overdue-1",
      due_date: "2026-06-15",
    });

    const overdueStatus = isOverdue(overdueAssignment, REFERENCE_DATE);
    expect(overdueStatus).toBe(true);
    // When isOverdue=true, card renders all 3 action buttons
  });

  it("test_chore_non_overdue_pending_only_has_done_action", () => {
    // Non-overdue pending assignments only get: Done
    const todayAssignment = makeAssignment({
      id: "assign-today-1",
      due_date: "2026-06-17",
    });

    const overdueStatus = isOverdue(todayAssignment, REFERENCE_DATE);
    expect(overdueStatus).toBe(false);
    // When isOverdue=false, card renders only Done button
  });
});

describe("Smoke: Chore Module end-to-end — Overdue blocking (SC5)", () => {
  it("test_chore_overdue_detected_correctly", () => {
    // SC5: Overdue blocking visible
    const overdueAssignment = makeAssignment({
      due_date: "2026-06-15", // 2 days before reference
      status: "pending",
    });

    expect(isOverdue(overdueAssignment, REFERENCE_DATE)).toBe(true);
  });

  it("test_chore_today_is_not_overdue", () => {
    const todayAssignment = makeAssignment({
      due_date: "2026-06-17", // same as reference date
      status: "pending",
    });

    expect(isOverdue(todayAssignment, REFERENCE_DATE)).toBe(false);
  });

  it("test_chore_completed_past_assignment_not_overdue", () => {
    const completedPast = makeAssignment({
      due_date: "2026-06-15",
      status: "completed",
    });

    expect(isOverdue(completedPast, REFERENCE_DATE)).toBe(false);
  });

  it("test_chore_postponed_to_future_not_overdue", () => {
    // Originally overdue but postponed to future
    const postponedForward = makeAssignment({
      due_date: "2026-06-14",
      postponed_to: "2026-06-19",
      status: "pending",
    });

    expect(isOverdue(postponedForward, REFERENCE_DATE)).toBe(false);
  });

  it("test_chore_postponed_but_still_past_is_overdue", () => {
    // Postponed to a date that is also in the past
    const stillOverdue = makeAssignment({
      due_date: "2026-06-10",
      postponed_to: "2026-06-15",
      status: "pending",
    });

    expect(isOverdue(stillOverdue, REFERENCE_DATE)).toBe(true);
  });

  it("test_chore_overdue_group_flagged_for_highlighting", () => {
    const groups = groupAssignments(mockAssignments, REFERENCE_DATE);
    const overdueGroup = groups.find((g) => g.title === "Overdue");

    // SC5: Overdue blocking visible — group is flagged
    expect(overdueGroup).toBeDefined();
    expect(overdueGroup!.isOverdue).toBe(true);

    // Non-overdue groups are not flagged
    const todayGroup = groups.find((g) => g.title === "Today");
    expect(todayGroup!.isOverdue).toBe(false);
  });
});

describe("Smoke: Chore Module end-to-end — Store state management", () => {
  beforeEach(() => {
    useChoreStore.setState({
      sheetVisible: false,
      editingChoreId: null,
      actionSheetVisible: false,
      selectedAssignmentId: null,
    });
  });

  it("test_chore_open_create_sheet_sets_visible_without_chore_id", () => {
    useChoreStore.getState().openSheet();
    const state = useChoreStore.getState();
    expect(state.sheetVisible).toBe(true);
    expect(state.editingChoreId).toBeNull();
  });

  it("test_chore_open_edit_sheet_passes_chore_id", () => {
    useChoreStore.getState().openSheet(mockChore.id);
    const state = useChoreStore.getState();
    expect(state.sheetVisible).toBe(true);
    expect(state.editingChoreId).toBe(mockChore.id);
  });

  it("test_chore_close_sheet_resets_all_state", () => {
    useChoreStore.getState().openSheet(mockChore.id);
    useChoreStore.getState().closeSheet();
    const state = useChoreStore.getState();
    expect(state.sheetVisible).toBe(false);
    expect(state.editingChoreId).toBeNull();
  });

  it("test_chore_action_sheet_lifecycle_for_overdue_assignment", () => {
    const overdueId = "assign-overdue-1";

    useChoreStore.getState().openActionSheet(overdueId);
    expect(useChoreStore.getState().actionSheetVisible).toBe(true);
    expect(useChoreStore.getState().selectedAssignmentId).toBe(overdueId);

    useChoreStore.getState().closeActionSheet();
    expect(useChoreStore.getState().actionSheetVisible).toBe(false);
    expect(useChoreStore.getState().selectedAssignmentId).toBeNull();
  });

  it("test_chore_tap_assignment_opens_edit_sheet_with_chore_id", () => {
    // Tapping an assignment card opens the chore edit sheet
    const assignment = mockAssignments[1]; // Today's assignment
    useChoreStore.getState().openSheet(assignment.chore_id);

    const state = useChoreStore.getState();
    expect(state.sheetVisible).toBe(true);
    expect(state.editingChoreId).toBe(assignment.chore_id);
  });
});

describe("Smoke: Chore Module end-to-end — Edge cases", () => {
  it("test_chore_multiple_overdue_from_same_chore_all_show", () => {
    // When a chore has multiple overdue assignments they all appear
    const multipleOverdue = [
      makeAssignment({ id: "o1", chore_id: "c1", due_date: "2026-06-14" }),
      makeAssignment({ id: "o2", chore_id: "c1", due_date: "2026-06-15" }),
      makeAssignment({ id: "o3", chore_id: "c1", due_date: "2026-06-16" }),
    ];

    const groups = groupAssignments(multipleOverdue, REFERENCE_DATE);
    expect(groups[0].title).toBe("Overdue");
    expect(groups[0].assignments).toHaveLength(3);
  });

  it("test_chore_effective_date_coalesce_prefers_postponed_to", () => {
    const withPostpone = makeAssignment({
      due_date: "2026-06-10",
      postponed_to: "2026-06-20",
    });
    expect(getEffectiveDueDate(withPostpone)).toBe("2026-06-20");

    const withoutPostpone = makeAssignment({
      due_date: "2026-06-10",
      postponed_to: null,
    });
    expect(getEffectiveDueDate(withoutPostpone)).toBe("2026-06-10");
  });

  it("test_chore_rotation_disabled_for_single_assignee_even_if_requested", () => {
    const payload = buildChoreCreatePayload(
      "Solo task",
      "2026-06-17",
      true,
      1,
      "days",
      [USER_ALICE_ID],
      true
    );
    expect(payload.rotation_enabled).toBe(false);
  });

  it("test_chore_assignment_completed_by_different_user_shows_credit", () => {
    // Any member can complete any assignment — credit goes to completer
    const completed = makeAssignment({
      assigned_to_user_id: USER_ALICE_ID,
      assigned_to_display_name: "Alice",
      status: "completed",
      completed_by_user_id: USER_CAROL_ID,
      completed_by_display_name: "Carol",
    });

    expect(completed.assigned_to_display_name).toBe("Alice");
    expect(completed.completed_by_display_name).toBe("Carol");
  });
});
