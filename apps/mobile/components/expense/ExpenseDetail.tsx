import { View, Text } from "react-native";
import { Expense, HouseholdMember } from "@hausly/types";
import { Sheet, Button } from "@/components/ui";
import { styles } from "./ExpenseDetail.styles";

interface ExpenseDetailProps {
  visible: boolean;
  onClose: () => void;
  expense: Expense | null;
  members: HouseholdMember[];
  currentUserId: string;
  onConfirm?: () => void;
  onDelete?: () => void;
  isConfirming?: boolean;
  isDeleting?: boolean;
}

const sourceLabels: Record<string, string> = {
  manual: "Manual",
  grocery_integration: "From grocery session",
  recurring_auto: "Recurring (auto-generated)",
};

export function ExpenseDetail({
  visible,
  onClose,
  expense,
  members,
  currentUserId,
  onConfirm,
  onDelete,
  isConfirming = false,
  isDeleting = false,
}: ExpenseDetailProps) {
  if (!expense) return null;

  const getMemberName = (userId: string) => {
    if (userId === currentUserId) return "You";
    const member = members.find((m) => m.user_id === userId);
    return member?.display_name || member?.email || "Unknown";
  };

  const isDraft = expense.status === "draft";
  const paidByName = getMemberName(expense.paid_by_user_id);

  return (
    <Sheet visible={visible} onClose={onClose}>
      <View style={styles.container}>
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.amount}>
            {expense.currency} {expense.amount.toFixed(2)}
          </Text>
          <Text style={styles.title}>{expense.title}</Text>
          <View style={[styles.badge, isDraft ? styles.badgeDraft : styles.badgeConfirmed]}>
            <Text
              style={[
                styles.badgeText,
                isDraft ? styles.badgeTextDraft : styles.badgeTextConfirmed,
              ]}
            >
              {isDraft ? "DRAFT" : "CONFIRMED"}
            </Text>
          </View>
          {expense.source !== "manual" && (
            <Text style={styles.sourceTag}>
              {sourceLabels[expense.source] ?? expense.source}
            </Text>
          )}
        </View>

        {/* Info */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Details</Text>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Paid by</Text>
            <Text style={styles.infoValue}>{paidByName}</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Category</Text>
            <Text style={styles.infoValue}>{expense.category ?? "Other"}</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Date</Text>
            <Text style={styles.infoValue}>
              {new Date(expense.created_at).toLocaleDateString()}
            </Text>
          </View>
        </View>

        {/* Splits */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Splits</Text>
          {expense.splits.map((split) => (
            <View key={split.id} style={styles.splitRow}>
              <View>
                <Text style={styles.splitName}>
                  {getMemberName(split.user_id)}
                </Text>
                <Text style={split.is_settled ? styles.splitSettled : styles.splitUnsettled}>
                  {split.is_settled ? "Settled" : "Unsettled"}
                </Text>
              </View>
              <Text style={styles.splitAmount}>
                {expense.currency} {split.share_amount.toFixed(2)}
              </Text>
            </View>
          ))}
        </View>

        {/* Actions */}
        {isDraft && (
          <View style={styles.actionRow}>
            <Button
              title="Delete"
              variant="destructive"
              onPress={onDelete ?? (() => {})}
              loading={isDeleting}
              style={{ flex: 1 }}
            />
            <Button
              title="Confirm"
              variant="primary"
              onPress={onConfirm ?? (() => {})}
              loading={isConfirming}
              style={{ flex: 1 }}
            />
          </View>
        )}
      </View>
    </Sheet>
  );
}
