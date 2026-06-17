import { View, Text, Pressable } from "react-native";
import { SettlementSuggestion, HouseholdMember } from "@hausly/types";
import { styles } from "./SettlementList.styles";

interface SettlementListProps {
  suggestions: SettlementSuggestion[];
  members: HouseholdMember[];
  currentUserId: string;
  onSettle: (suggestion: SettlementSuggestion) => void;
  isSettling: boolean;
}

export function SettlementList({
  suggestions,
  members,
  currentUserId,
  onSettle,
  isSettling,
}: SettlementListProps) {
  const getMemberName = (userId: string) => {
    if (userId === currentUserId) return "You";
    const member = members.find((m) => m.user_id === userId);
    return member?.display_name || member?.email || "Unknown";
  };

  if (suggestions.length === 0) {
    return (
      <View style={styles.container}>
        <Text style={styles.header}>Settlement Suggestions</Text>
        <Text style={styles.emptyText}>Nothing to settle 🎉</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.header}>Settlement Suggestions</Text>
      {suggestions.map((suggestion, index) => (
        <View key={`${suggestion.from_user_id}-${suggestion.to_user_id}`}>
          {index > 0 && <View style={styles.separator} />}
          <View style={styles.row}>
            <View style={styles.left}>
              <Text style={styles.names}>
                {getMemberName(suggestion.from_user_id)} → {getMemberName(suggestion.to_user_id)}
              </Text>
              <Text style={styles.arrow}>owes</Text>
            </View>
            <View style={styles.right}>
              <Text style={styles.amount}>
                €{suggestion.amount.toFixed(2)}
              </Text>
              <Pressable
                style={styles.settleButton}
                onPress={() => onSettle(suggestion)}
                disabled={isSettling}
              >
                <Text style={styles.settleButtonText}>Settle</Text>
              </Pressable>
            </View>
          </View>
        </View>
      ))}
    </View>
  );
}
