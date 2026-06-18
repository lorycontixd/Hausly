import { useCallback, useState } from "react";
import { View, Text, ScrollView, Alert } from "react-native";
import { useHouseholdStore } from "@/stores/householdStore";
import { useChoreStore } from "@/stores/choreStore";
import {
  useChores,
  useAssignments,
  useCompleteAssignment,
  usePostponeAssignment,
  useCancelAssignment,
} from "@/hooks/useChores";
import { ChoreGroupedList } from "@/components/chore/ChoreGroupedList";
import { ChoreCreateSheet } from "@/components/chore/ChoreCreateSheet";
import { PostponeSheet } from "@/components/chore/PostponeSheet";
import { LoadingSpinner, EmptyState, Button } from "@/components/ui";
import { ChoreAssignment } from "@hausly/types";
import { styles } from "@/components/chore/ChoreScreen.styles";

export default function ChoresScreen() {
  const householdId = useHouseholdStore((s) => s.id);

  const sheetVisible = useChoreStore((s) => s.sheetVisible);
  const editingChoreId = useChoreStore((s) => s.editingChoreId);
  const openSheet = useChoreStore((s) => s.openSheet);
  const closeSheet = useChoreStore((s) => s.closeSheet);

  const { data: chores } = useChores(householdId);
  const { data: assignments, isLoading } = useAssignments(householdId, {
    status: "pending",
  });

  const completeAssignment = useCompleteAssignment(householdId);
  const postponeAssignment = usePostponeAssignment(householdId);
  const cancelAssignment = useCancelAssignment(householdId);

  const [postponeSheetVisible, setPostponeSheetVisible] = useState(false);
  const [postponeTargetId, setPostponeTargetId] = useState<string | null>(null);

  const editingChore = editingChoreId
    ? chores?.find((c) => c.id === editingChoreId) ?? null
    : null;

  const handleComplete = useCallback(
    (assignmentId: string) => {
      completeAssignment.mutate(assignmentId);
    },
    [completeAssignment]
  );

  const handlePostpone = useCallback((assignmentId: string) => {
    setPostponeTargetId(assignmentId);
    setPostponeSheetVisible(true);
  }, []);

  const handlePostponeConfirm = useCallback(
    (date: string) => {
      if (!postponeTargetId) return;
      postponeAssignment.mutate({
        assignmentId: postponeTargetId,
        postponeTo: date,
      });
      setPostponeTargetId(null);
    },
    [postponeTargetId, postponeAssignment]
  );

  const handleCancel = useCallback(
    (assignmentId: string) => {
      Alert.alert(
        "Cancel assignment?",
        "This will skip this occurrence. The next one will generate normally.",
        [
          { text: "Keep", style: "cancel" },
          {
            text: "Cancel It",
            style: "destructive",
            onPress: () => cancelAssignment.mutate(assignmentId),
          },
        ]
      );
    },
    [cancelAssignment]
  );

  const handleAssignmentPress = useCallback(
    (assignment: ChoreAssignment) => {
      openSheet(assignment.chore_id);
    },
    [openSheet]
  );

  if (!householdId) {
    return (
      <EmptyState
        icon="🏠"
        title="No household"
        message="Join or create a household to manage chores."
      />
    );
  }

  if (isLoading) {
    return <LoadingSpinner />;
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Chores</Text>
        <Button
          title="+ Add"
          onPress={() => openSheet()}
          variant="primary"
          size="small"
        />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {assignments && assignments.length > 0 ? (
          <ChoreGroupedList
            assignments={assignments}
            onComplete={handleComplete}
            onPostpone={handlePostpone}
            onCancel={handleCancel}
            onPress={handleAssignmentPress}
          />
        ) : (
          <EmptyState
            icon="✨"
            title="All clear!"
            message="No pending chores. Tap + to create one."
          />
        )}
      </ScrollView>

      <ChoreCreateSheet
        visible={sheetVisible}
        onClose={closeSheet}
        existingChore={editingChore}
      />

      <PostponeSheet
        visible={postponeSheetVisible}
        onClose={() => setPostponeSheetVisible(false)}
        onConfirm={handlePostponeConfirm}
      />
    </View>
  );
}
