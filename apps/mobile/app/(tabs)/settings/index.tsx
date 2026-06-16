import {
  View,
  Text,
  ScrollView,
  Pressable,
  Alert,
  Share,
  StyleSheet,
} from "react-native";
import { useRouter } from "expo-router";
import { useHousehold } from "@/hooks/useHousehold";
import { useHouseholdStore } from "@/stores/householdStore";
import { useAuthContext } from "@/providers/AuthProvider";
import {
  useUpdateSettings,
  useRegenerateInviteCode,
} from "@/hooks/useHouseholdMutations";
import { Button, Card, Avatar } from "@/components/ui";
import { colors, spacing, borderRadius, typography } from "@/constants/theme";
import { ModuleName, HouseholdMember } from "@hausly/types";

const ALL_MODULES: { name: ModuleName; label: string; emoji: string }[] = [
  { name: "grocery", label: "Grocery List", emoji: "🛒" },
  { name: "expense", label: "Expenses", emoji: "💰" },
  { name: "meal", label: "Meal Planner", emoji: "🍽️" },
  { name: "chores", label: "Chores", emoji: "✅" },
];

export default function HouseholdSettingsScreen() {
  const router = useRouter();
  const { profile } = useAuthContext();
  const { household, householdId, refetch } = useHousehold();
  const members = useHouseholdStore((s) => s.members);
  const settings = useHouseholdStore((s) => s.settings);
  const inviteCode = useHouseholdStore((s) => s.inviteCode);

  const currentUserId = profile?.user_id;
  const currentMember = members.find((m) => m.user_id === currentUserId);
  const isAdmin = currentMember?.role === "admin";

  const updateSettingsMutation = useUpdateSettings(householdId ?? "");
  const regenerateCodeMutation = useRegenerateInviteCode(householdId ?? "");

  const handleCopyCode = async () => {
    if (!inviteCode) return;
    await Share.share({ message: inviteCode });
  };

  const handleToggleModule = async (moduleName: ModuleName) => {
    if (!isAdmin || !settings) return;
    const current = settings.enabled_modules;
    const updated = current.includes(moduleName)
      ? current.filter((m) => m !== moduleName)
      : [...current, moduleName];

    await updateSettingsMutation.mutateAsync({ enabled_modules: updated });
    refetch();
  };

  const handleRegenerateCode = () => {
    Alert.alert(
      "Regenerate Invite Code",
      "The current code will stop working. Are you sure?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Regenerate",
          style: "destructive",
          onPress: async () => {
            await regenerateCodeMutation.mutateAsync();
            refetch();
          },
        },
      ]
    );
  };

  const handleMemberPress = (member: HouseholdMember) => {
    if (!isAdmin || member.user_id === currentUserId) return;
    router.push({
      pathname: "/(tabs)/settings/member",
      params: { userId: member.user_id, displayName: member.display_name, role: member.role },
    });
  };

  const handleLeave = () => {
    router.push("/(tabs)/settings/leave");
  };

  if (!household) return null;

  return (
    <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
      <Card elevated style={styles.section}>
        <Text style={styles.sectionTitle}>Household</Text>
        <Text style={styles.householdName}>{household.name}</Text>
        <Text style={styles.householdType}>{household.type}</Text>
      </Card>

      <Card elevated style={styles.section}>
        <Text style={styles.sectionTitle}>Invite Code</Text>
        <View style={styles.codeRow}>
          <Text style={styles.codeText}>{inviteCode}</Text>
          <Pressable onPress={handleCopyCode} style={styles.copyButton}>
            <Text style={styles.copyButtonText}>Share</Text>
          </Pressable>
        </View>
        {isAdmin && (
          <Button
            title="Regenerate Code"
            onPress={handleRegenerateCode}
            variant="secondary"
            size="small"
            loading={regenerateCodeMutation.isPending}
            style={styles.regenerateButton}
          />
        )}
      </Card>

      {isAdmin && (
        <Card elevated style={styles.section}>
          <Text style={styles.sectionTitle}>Modules</Text>
          {ALL_MODULES.map((mod) => {
            const enabled = settings?.enabled_modules.includes(mod.name) ?? false;
            return (
              <Pressable
                key={mod.name}
                style={styles.moduleRow}
                onPress={() => handleToggleModule(mod.name)}
              >
                <Text style={styles.moduleEmoji}>{mod.emoji}</Text>
                <Text style={styles.moduleLabel}>{mod.label}</Text>
                <View
                  style={[
                    styles.toggle,
                    enabled && styles.toggleEnabled,
                  ]}
                >
                  <View
                    style={[
                      styles.toggleDot,
                      enabled && styles.toggleDotEnabled,
                    ]}
                  />
                </View>
              </Pressable>
            );
          })}
        </Card>
      )}

      <Card elevated style={styles.section}>
        <Text style={styles.sectionTitle}>
          Members ({members.length})
        </Text>
        {members.map((member) => {
          const name = member.display_name || member.email || "Member";
          return (
            <Pressable
              key={member.user_id}
              style={styles.memberRow}
              onPress={() => handleMemberPress(member)}
              disabled={!isAdmin || member.user_id === currentUserId}
            >
              <Avatar name={name} size={36} />
              <View style={styles.memberInfo}>
                <Text style={styles.memberName}>
                  {name}
                  {member.user_id === currentUserId && " (you)"}
                </Text>
                <Text style={styles.memberRole}>{member.role}</Text>
              </View>
              {isAdmin && member.user_id !== currentUserId && (
                <Text style={styles.chevron}>›</Text>
              )}
            </Pressable>
          );
        })}
      </Card>

      <Button
        title="Leave Household"
        onPress={handleLeave}
        variant="destructive"
        style={styles.leaveButton}
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
  section: {
    padding: spacing.lg,
    marginBottom: spacing.lg,
  },
  sectionTitle: {
    ...typography.caption,
    color: colors.textTertiary,
    textTransform: "uppercase",
    marginBottom: spacing.md,
  },
  householdName: {
    ...typography.subheading,
    color: colors.text,
  },
  householdType: {
    ...typography.bodySmall,
    color: colors.textSecondary,
    textTransform: "capitalize",
    marginTop: spacing.xs,
  },
  codeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  codeText: {
    ...typography.subheading,
    color: colors.text,
    letterSpacing: 2,
    flex: 1,
  },
  copyButton: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.sm,
    backgroundColor: colors.primarySoft,
  },
  copyButtonText: {
    ...typography.caption,
    color: colors.primary,
  },
  regenerateButton: {
    marginTop: spacing.md,
  },
  moduleRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  moduleEmoji: {
    fontSize: 20,
    marginRight: spacing.md,
  },
  moduleLabel: {
    ...typography.body,
    color: colors.text,
    flex: 1,
  },
  toggle: {
    width: 44,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.border,
    justifyContent: "center",
    paddingHorizontal: 2,
  },
  toggleEnabled: {
    backgroundColor: colors.primary,
  },
  toggleDot: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: colors.surface,
  },
  toggleDotEnabled: {
    alignSelf: "flex-end",
  },
  memberRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  memberInfo: {
    flex: 1,
    marginLeft: spacing.md,
  },
  memberName: {
    ...typography.body,
    color: colors.text,
  },
  memberRole: {
    ...typography.caption,
    color: colors.textTertiary,
    textTransform: "capitalize",
  },
  chevron: {
    fontSize: 22,
    color: colors.textTertiary,
  },
  leaveButton: {
    marginTop: spacing.lg,
  },
});
