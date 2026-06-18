import { View, Text, Pressable } from "react-native";
import { ChoreAssignment } from "@hausly/types";
import { Button } from "@/components/ui";
import { styles } from "./ChoreAssignmentCard.styles";

interface ChoreAssignmentCardProps {
  assignment: ChoreAssignment;
  isOverdue: boolean;
  onComplete: () => void;
  onPostpone: () => void;
  onCancel: () => void;
  onPress?: () => void;
}

function formatDueLabel(assignment: ChoreAssignment, isOverdue: boolean): string {
  const effectiveDate = assignment.postponed_to ?? assignment.due_date;
  const due = new Date(effectiveDate + "T00:00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const diffMs = due.getTime() - today.getTime();
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));

  if (isOverdue) {
    return `${Math.abs(diffDays)}d overdue`;
  }
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Tomorrow";
  return due.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

export function ChoreAssignmentCard({
  assignment,
  isOverdue,
  onComplete,
  onPostpone,
  onCancel,
  onPress,
}: ChoreAssignmentCardProps) {
  const dueLabel = formatDueLabel(assignment, isOverdue);
  const isCompleted = assignment.status === "completed";

  return (
    <Pressable
      style={[styles.container, isOverdue && styles.overdue]}
      onPress={onPress}
    >
      <View style={styles.header}>
        <Text style={styles.choreName}>{assignment.chore_name}</Text>
        <Text style={isOverdue ? styles.overdueText : styles.dueText}>
          {dueLabel}
        </Text>
      </View>

      <Text style={styles.assignee}>
        {assignment.assigned_to_display_name}
      </Text>

      {isCompleted && assignment.completed_by_display_name && (
        <Text style={styles.completedTag}>
          ✓ Completed by {assignment.completed_by_display_name}
        </Text>
      )}

      {assignment.status === "pending" && (
        <View style={styles.actions}>
          <Button
            title="Done"
            onPress={onComplete}
            variant="primary"
            size="small"
          />
          {isOverdue && (
            <>
              <Button
                title="Postpone"
                onPress={onPostpone}
                variant="secondary"
                size="small"
              />
              <Button
                title="Cancel"
                onPress={onCancel}
                variant="destructive"
                size="small"
              />
            </>
          )}
        </View>
      )}
    </Pressable>
  );
}
