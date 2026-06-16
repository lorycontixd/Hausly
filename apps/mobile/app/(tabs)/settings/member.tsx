import { View, Text, Alert, StyleSheet } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useHousehold } from "@/hooks/useHousehold";
import { useChangeRole, useRemoveMember } from "@/hooks/useHouseholdMutations";
import { Button, Avatar, Card } from "@/components/ui";
import { colors, spacing, typography } from "@/constants/theme";
import { MemberRole } from "@hausly/types";

export default function MemberManageScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{
    userId: string;
    displayName: string;
    role: string;
  }>();
  const { householdId, refetch } = useHousehold();

  const changeRoleMutation = useChangeRole();
  const removeMemberMutation = useRemoveMember();

  const { userId, displayName, role } = params;
  const newRole: MemberRole = role === "admin" ? "member" : "admin";

  const handleChangeRole = () => {
    Alert.alert(
      "Change Role",
      `Make ${displayName} ${newRole === "admin" ? "an admin" : "a member"}?`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Confirm",
          onPress: async () => {
            if (!householdId || !userId) return;
            await changeRoleMutation.mutateAsync({
              householdId,
              userId,
              role: newRole,
            });
            refetch();
            router.back();
          },
        },
      ]
    );
  };

  const handleRemove = () => {
    Alert.alert(
      "Remove Member",
      `Remove ${displayName} from the household? This cannot be undone.`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Remove",
          style: "destructive",
          onPress: async () => {
            if (!householdId || !userId) return;
            await removeMemberMutation.mutateAsync({ householdId, userId });
            refetch();
            router.back();
          },
        },
      ]
    );
  };

  return (
    <View style={styles.container}>
      <Card elevated style={styles.profileCard}>
        <Avatar name={displayName ?? ""} size={56} />
        <Text style={styles.name}>{displayName}</Text>
        <Text style={styles.role}>{role}</Text>
      </Card>

      <View style={styles.actions}>
        <Button
          title={`Make ${newRole === "admin" ? "Admin" : "Member"}`}
          onPress={handleChangeRole}
          variant="secondary"
          loading={changeRoleMutation.isPending}
        />

        <Button
          title="Remove from Household"
          onPress={handleRemove}
          variant="destructive"
          loading={removeMemberMutation.isPending}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    padding: spacing.lg,
  },
  profileCard: {
    padding: spacing.xxl,
    alignItems: "center",
    marginBottom: spacing.xxl,
  },
  name: {
    ...typography.subheading,
    color: colors.text,
    marginTop: spacing.md,
  },
  role: {
    ...typography.caption,
    color: colors.textTertiary,
    textTransform: "capitalize",
    marginTop: spacing.xs,
  },
  actions: {
    gap: spacing.md,
  },
});
