import { View, Text } from "react-native";
import { Balance, HouseholdMember } from "@hausly/types";
import { styles } from "./BalanceSummary.styles";

interface BalanceSummaryProps {
  balances: Balance[];
  members: HouseholdMember[];
  currentUserId: string;
}

export function BalanceSummary({
  balances,
  members,
  currentUserId,
}: BalanceSummaryProps) {
  const getMemberName = (userId: string) => {
    if (userId === currentUserId) return "You";
    const member = members.find((m) => m.user_id === userId);
    return member?.display_name || member?.email || "Unknown";
  };

  const activeBalances = balances.filter((b) => b.direction !== "settled");

  if (activeBalances.length === 0) {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Balances</Text>
        </View>
        <Text style={styles.emptyText}>All settled up! 🎉</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Balances</Text>
      </View>
      {activeBalances.map((balance, index) => {
        const fromId =
          balance.direction === "a_owes_b" ? balance.user_a_id : balance.user_b_id;
        const toId =
          balance.direction === "a_owes_b" ? balance.user_b_id : balance.user_a_id;
        const isCurrentUserDebtor = fromId === currentUserId;

        return (
          <View key={`${balance.user_a_id}-${balance.user_b_id}`}>
            {index > 0 && <View style={styles.separator} />}
            <View style={styles.row}>
              <View style={styles.names}>
                <Text style={styles.nameText}>
                  {getMemberName(fromId)} → {getMemberName(toId)}
                </Text>
              </View>
              <Text
                style={
                  isCurrentUserDebtor ? styles.amountOwed : styles.amountOwedTo
                }
              >
                €{balance.net_amount.toFixed(2)}
              </Text>
            </View>
          </View>
        );
      })}
    </View>
  );
}
