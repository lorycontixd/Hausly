import { useState, useEffect } from "react";
import {
  View,
  Text,
  ScrollView,
  Alert,
  StyleSheet,
} from "react-native";
import { useRouter } from "expo-router";
import { useHousehold } from "@/hooks/useHousehold";
import { useAuthContext } from "@/providers/AuthProvider";
import { useHouseholdStore } from "@/stores/householdStore";
import { api } from "@/services/api";
import { Button, Card } from "@/components/ui";
import { LoadingSpinner } from "@/components/ui";
import { colors, spacing, typography } from "@/constants/theme";

interface LeavePreview {
  unsettled_expenses: Array<{ id: string; title: string; amount: number }>;
  pending_chores: Array<{ id: string; name: string; due_date: string }>;
}

export default function LeaveHouseholdScreen() {
  const router = useRouter();
  const { householdId } = useHousehold();
  const { refreshProfile } = useAuthContext();
  const clearStore = useHouseholdStore((s) => s.clear);
  const [preview, setPreview] = useState<LeavePreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    if (!householdId) return;
    // Fetch the leave preview data (GET shows what would be affected)
    api
      .get<LeavePreview>(`/households/${householdId}/leave/preview`)
      .then(setPreview)
      .catch(() => setPreview({ unsettled_expenses: [], pending_chores: [] }))
      .finally(() => setLoading(false));
  }, [householdId]);

  const handleConfirmLeave = () => {
    Alert.alert(
      "Leave Household",
      "Are you sure you want to leave? This cannot be undone.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Leave",
          style: "destructive",
          onPress: async () => {
            if (!householdId) return;
            setLeaving(true);
            try {
              await api.post(`/households/${householdId}/leave`);
              clearStore();
              await refreshProfile();
              router.replace("/(auth)/onboarding");
            } catch (e) {
              setLeaving(false);
              Alert.alert(
                "Error",
                e instanceof Error ? e.message : "Failed to leave household"
              );
            }
          },
        },
      ]
    );
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <LoadingSpinner />
        <Text style={styles.loadingText}>Checking outstanding items...</Text>
      </View>
    );
  }

  const unsettledExpenses = preview?.unsettled_expenses ?? [];
  const pendingChores = preview?.pending_chores ?? [];
  const hasOutstandingItems = unsettledExpenses.length > 0 || pendingChores.length > 0;

  return (
    <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
      {hasOutstandingItems ? (
        <>
          <Card elevated style={styles.warningCard}>
            <Text style={styles.warningTitle}>⚠️ Outstanding Items</Text>
            <Text style={styles.warningText}>
              You have unresolved items. Please review them before leaving.
            </Text>
          </Card>

          {unsettledExpenses.length > 0 && (
            <Card style={styles.section}>
              <Text style={styles.sectionTitle}>
                Unsettled Expenses ({unsettledExpenses.length})
              </Text>
              {unsettledExpenses.map((expense) => (
                <View key={expense.id} style={styles.itemRow}>
                  <Text style={styles.itemName}>{expense.title}</Text>
                  <Text style={styles.itemMeta}>
                    ${expense.amount.toFixed(2)}
                  </Text>
                </View>
              ))}
            </Card>
          )}

          {pendingChores.length > 0 && (
            <Card style={styles.section}>
              <Text style={styles.sectionTitle}>
                Pending Chores ({pendingChores.length})
              </Text>
              {pendingChores.map((chore) => (
                <View key={chore.id} style={styles.itemRow}>
                  <Text style={styles.itemName}>{chore.name}</Text>
                  <Text style={styles.itemMeta}>
                    Due: {new Date(chore.due_date).toLocaleDateString()}
                  </Text>
                </View>
              ))}
            </Card>
          )}

          <Text style={styles.disclaimer}>
            Leaving will forgive any remaining debts owed to you and reassign
            your pending chores to other members.
          </Text>
        </>
      ) : (
        <Card elevated style={styles.section}>
          <Text style={styles.allClearTitle}>✓ All clear</Text>
          <Text style={styles.allClearText}>
            You have no unsettled expenses or pending chores.
          </Text>
        </Card>
      )}

      <Button
        title="Leave Household"
        onPress={handleConfirmLeave}
        variant="destructive"
        loading={leaving}
        style={styles.leaveButton}
      />

      <Button
        title="Cancel"
        onPress={() => router.back()}
        variant="secondary"
        style={styles.cancelButton}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scrollView: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.lg,
    paddingBottom: spacing.xxxl,
  },
  centered: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: colors.background,
  },
  loadingText: {
    ...typography.body,
    color: colors.textSecondary,
    marginTop: spacing.lg,
  },
  warningCard: {
    padding: spacing.lg,
    marginBottom: spacing.lg,
    backgroundColor: colors.destructiveLight,
    borderWidth: 1,
    borderColor: colors.destructive,
  },
  warningTitle: {
    ...typography.subheading,
    color: colors.destructive,
    marginBottom: spacing.sm,
  },
  warningText: {
    ...typography.bodySmall,
    color: colors.text,
  },
  section: {
    padding: spacing.lg,
    marginBottom: spacing.lg,
  },
  sectionTitle: {
    ...typography.label,
    color: colors.text,
    marginBottom: spacing.md,
  },
  itemRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  itemName: {
    ...typography.body,
    color: colors.text,
    flex: 1,
  },
  itemMeta: {
    ...typography.bodySmall,
    color: colors.textSecondary,
  },
  allClearTitle: {
    ...typography.subheading,
    color: colors.success,
    marginBottom: spacing.sm,
  },
  allClearText: {
    ...typography.body,
    color: colors.textSecondary,
  },
  disclaimer: {
    ...typography.bodySmall,
    color: colors.textTertiary,
    textAlign: "center",
    marginVertical: spacing.lg,
  },
  leaveButton: {
    marginTop: spacing.lg,
  },
  cancelButton: {
    marginTop: spacing.md,
  },
});
