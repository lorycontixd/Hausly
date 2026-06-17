import { View, Text, Pressable } from "react-native";
import { Expense } from "@hausly/types";
import { styles } from "./ExpenseListItem.styles";

interface ExpenseListItemProps {
  expense: Expense;
  paidByName: string;
  onPress: () => void;
}

const categoryIcons: Record<string, string> = {
  food: "🛒",
  transport: "🚗",
  utilities: "💡",
  entertainment: "🎬",
  rent: "🏠",
  health: "💊",
  other: "📋",
};

export function ExpenseListItem({
  expense,
  paidByName,
  onPress,
}: ExpenseListItemProps) {
  const icon = categoryIcons[expense.category ?? "other"] ?? "📋";
  const isDraft = expense.status === "draft";

  return (
    <Pressable style={styles.container} onPress={onPress}>
      <View style={styles.iconContainer}>
        <Text style={styles.iconText}>{icon}</Text>
      </View>

      <View style={styles.content}>
        <Text style={styles.title} numberOfLines={1}>
          {expense.title}
        </Text>
        <Text style={styles.subtitle}>
          Paid by {paidByName}
        </Text>
      </View>

      <View style={styles.rightSection}>
        <Text style={styles.amount}>
          {expense.currency} {expense.amount.toFixed(2)}
        </Text>
        {isDraft ? (
          <View style={styles.draftBadge}>
            <Text style={styles.draftText}>DRAFT</Text>
          </View>
        ) : (
          <View style={styles.confirmedBadge}>
            <Text style={styles.confirmedText}>CONFIRMED</Text>
          </View>
        )}
      </View>
    </Pressable>
  );
}
