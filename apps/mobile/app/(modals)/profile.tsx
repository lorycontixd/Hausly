import { View, Text, ScrollView, StyleSheet } from "react-native";
import { useAuthContext } from "@/providers/AuthProvider";
import { useHouseholdStore } from "@/stores/householdStore";
import { Avatar, Card } from "@/components/ui";
import { colors, spacing, typography } from "@/constants/theme";

export default function ProfileScreen() {
  const { profile, user } = useAuthContext();
  const householdName = useHouseholdStore((s) => s.name);

  const displayName =
    profile?.display_name || user?.email?.split("@")[0] || "User";
  const email = profile?.email || user?.email || "—";

  return (
    <ScrollView
      style={styles.scrollView}
      contentContainerStyle={styles.content}
    >
      <View style={styles.avatarSection}>
        <Avatar name={displayName} size={80} />
        <Text style={styles.displayName}>{displayName}</Text>
      </View>

      <Card elevated style={styles.card}>
        <Text style={styles.label}>Email</Text>
        <Text style={styles.value}>{email}</Text>
      </Card>

      <Card elevated style={styles.card}>
        <Text style={styles.label}>Current Household</Text>
        <Text style={styles.value}>{householdName || "No household"}</Text>
      </Card>
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
  avatarSection: {
    alignItems: "center",
    paddingVertical: spacing.xxl,
    gap: spacing.md,
  },
  displayName: {
    ...typography.heading,
    color: colors.text,
  },
  card: {
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  label: {
    ...typography.caption,
    color: colors.textTertiary,
    textTransform: "uppercase",
    marginBottom: spacing.xs,
  },
  value: {
    ...typography.body,
    color: colors.text,
  },
});
