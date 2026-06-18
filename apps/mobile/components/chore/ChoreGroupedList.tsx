import { View, Text } from "react-native";
import { ChoreAssignment } from "@hausly/types";
import { ChoreAssignmentCard } from "./ChoreAssignmentCard";
import { styles } from "./ChoreGroupedList.styles";

interface AssignmentGroup {
  title: string;
  isOverdue: boolean;
  assignments: ChoreAssignment[];
}

interface ChoreGroupedListProps {
  assignments: ChoreAssignment[];
  onComplete: (id: string) => void;
  onPostpone: (id: string) => void;
  onCancel: (id: string) => void;
  onPress?: (assignment: ChoreAssignment) => void;
}

function groupAssignments(assignments: ChoreAssignment[]): AssignmentGroup[] {
  const today = new Date();
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

export function ChoreGroupedList({
  assignments,
  onComplete,
  onPostpone,
  onCancel,
  onPress,
}: ChoreGroupedListProps) {
  const groups = groupAssignments(assignments);

  return (
    <View>
      {groups.map((group) => (
        <View key={group.title} style={styles.container}>
          <View style={styles.header}>
            <Text
              style={group.isOverdue ? styles.overdueTitle : styles.sectionTitle}
            >
              {group.isOverdue ? `⚠️ ${group.title}` : group.title}
            </Text>
            <Text style={styles.badge}>{group.assignments.length}</Text>
          </View>
          <View style={styles.list}>
            {group.assignments.map((assignment) => (
              <ChoreAssignmentCard
                key={assignment.id}
                assignment={assignment}
                isOverdue={group.isOverdue}
                onComplete={() => onComplete(assignment.id)}
                onPostpone={() => onPostpone(assignment.id)}
                onCancel={() => onCancel(assignment.id)}
                onPress={() => onPress?.(assignment)}
              />
            ))}
          </View>
        </View>
      ))}
    </View>
  );
}
