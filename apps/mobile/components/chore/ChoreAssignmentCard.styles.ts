import { StyleSheet } from "react-native";
import { colors, spacing, borderRadius, typography, shadows } from "@/constants/theme";

export const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    ...shadows.sm,
  },
  overdue: {
    borderColor: colors.error,
    borderWidth: 1.5,
    backgroundColor: colors.destructiveLight,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  choreName: {
    ...typography.label,
    color: colors.text,
    flex: 1,
  },
  dueText: {
    ...typography.caption,
    color: colors.textSecondary,
  },
  overdueText: {
    ...typography.caption,
    color: colors.error,
    fontWeight: "600",
  },
  assignee: {
    ...typography.bodySmall,
    color: colors.module.chore,
    marginTop: spacing.xs,
  },
  completedTag: {
    ...typography.caption,
    color: colors.success,
    marginTop: spacing.xs,
  },
  actions: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.md,
  },
});
