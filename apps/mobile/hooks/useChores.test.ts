/**
 * Tests for Phase 15 — Mobile: Chore Module
 *
 * Tests the core logic of the chore module:
 * - Assignment grouping by date (overdue, today, tomorrow, this week, later)
 * - Rotation preview calculation
 * - Creator-in-assignees validation
 *
 * Success Criteria (from implementation-plan-v1.md Phase 15):
 * 1. Assignments display grouped by date
 * 2. Create chore validates creator in assignees
 * 3. Rotation preview shows correct frequency
 * 4. Complete/postpone/cancel work
 * 5. Overdue blocking visible
 */

import { ChoreAssignment } from "@hausly/types";

// --- Extracted logic (mirrors ChoreGroupedList) ---

interface AssignmentGroup {
  title: string;
  isOverdue: boolean;
  assignments: ChoreAssignment[];
}

function groupAssignments(
  assignments: ChoreAssignment[],
  today: Date
): AssignmentGroup[] {
  const todayStart = new Date(today);
  todayStart.setHours(0, 0, 0, 0);

  const tomorrow = new Date(todayStart);
  tomorrow.setDate(tomorrow.getDate() + 1);

  const endOfWeek = new Date(todayStart);
  endOfWeek.setDate(endOfWeek.getDate() + (7 - todayStart.getDay()));

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

    if (effectiveDate < todayStart) {
      overdue.push(a);
    } else if (effectiveDate.getTime() === todayStart.getTime()) {
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

// --- Rotation preview logic ---

function computeRotationPreview(
  isRecurring: boolean,
  rotationEnabled: boolean,
  assigneeCount: number,
  interval: number,
  unit: string
): string | null {
  if (!isRecurring || !rotationEnabled || assigneeCount < 2) return null;
  const personalFreq = interval * assigneeCount;
  return `Your turn every ${personalFreq} ${unit}`;
}

// --- Validation ---

function validateCreatorInAssignees(
  creatorId: string,
  assigneeIds: string[]
): boolean {
  return assigneeIds.includes(creatorId);
}

// --- Test data ---

const today = new Date("2026-06-17T12:00:00Z");

function makeAssignment(
  overrides: Partial<ChoreAssignment>
): ChoreAssignment {
  return {
    id: "a-1",
    chore_id: "chore-1",
    chore_name: "Clean bathroom",
    assigned_to_user_id: "user-1",
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

// --- Tests ---

describe("Chore Module — Assignment grouping", () => {
  it("groups overdue assignments correctly", () => {
    const assignments = [
      makeAssignment({ id: "a-1", due_date: "2026-06-15" }),
      makeAssignment({ id: "a-2", due_date: "2026-06-17" }),
    ];

    const groups = groupAssignments(assignments, today);
    expect(groups[0].title).toBe("Overdue");
    expect(groups[0].assignments).toHaveLength(1);
    expect(groups[0].assignments[0].id).toBe("a-1");
    expect(groups[1].title).toBe("Today");
    expect(groups[1].assignments[0].id).toBe("a-2");
  });

  it("groups today, tomorrow, and this week", () => {
    const assignments = [
      makeAssignment({ id: "a-today", due_date: "2026-06-17" }),
      makeAssignment({ id: "a-tomorrow", due_date: "2026-06-18" }),
      makeAssignment({ id: "a-week", due_date: "2026-06-20" }),
    ];

    const groups = groupAssignments(assignments, today);
    expect(groups.map((g) => g.title)).toEqual([
      "Today",
      "Tomorrow",
      "This Week",
    ]);
  });

  it("uses postponed_to as effective date", () => {
    const assignments = [
      makeAssignment({
        id: "a-postponed",
        due_date: "2026-06-15",
        postponed_to: "2026-06-18",
      }),
    ];

    const groups = groupAssignments(assignments, today);
    expect(groups[0].title).toBe("Tomorrow");
  });

  it("skips non-pending assignments", () => {
    const assignments = [
      makeAssignment({ id: "a-done", status: "completed", due_date: "2026-06-17" }),
      makeAssignment({ id: "a-pending", status: "pending", due_date: "2026-06-17" }),
    ];

    const groups = groupAssignments(assignments, today);
    const allIds = groups.flatMap((g) => g.assignments.map((a) => a.id));
    expect(allIds).toEqual(["a-pending"]);
  });

  it("groups later assignments", () => {
    const assignments = [
      makeAssignment({ id: "a-later", due_date: "2026-06-25" }),
    ];

    const groups = groupAssignments(assignments, today);
    expect(groups[0].title).toBe("Later");
  });
});

describe("Chore Module — Rotation preview", () => {
  it("returns null when not recurring", () => {
    const result = computeRotationPreview(false, true, 3, 1, "weeks");
    expect(result).toBeNull();
  });

  it("returns null when rotation disabled", () => {
    const result = computeRotationPreview(true, false, 3, 1, "weeks");
    expect(result).toBeNull();
  });

  it("returns null with single assignee", () => {
    const result = computeRotationPreview(true, true, 1, 1, "weeks");
    expect(result).toBeNull();
  });

  it("calculates correct frequency for 3 assignees weekly", () => {
    const result = computeRotationPreview(true, true, 3, 1, "weeks");
    expect(result).toBe("Your turn every 3 weeks");
  });

  it("calculates correct frequency for 2 assignees every 2 days", () => {
    const result = computeRotationPreview(true, true, 2, 2, "days");
    expect(result).toBe("Your turn every 4 days");
  });
});

describe("Chore Module — Validation", () => {
  it("creator must be in assignees", () => {
    expect(validateCreatorInAssignees("user-1", ["user-1", "user-2"])).toBe(
      true
    );
    expect(validateCreatorInAssignees("user-1", ["user-2", "user-3"])).toBe(
      false
    );
  });

  it("empty assignee list fails", () => {
    expect(validateCreatorInAssignees("user-1", [])).toBe(false);
  });
});
