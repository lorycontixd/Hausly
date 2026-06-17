import { StyleSheet } from "react-native";
import { colors, spacing, borderRadius, shadows, typography } from "@/constants/theme";

export const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    padding: spacing.lg,
    marginBottom: spacing.sm,
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    ...shadows.sm,
  },
  iconContainer: {
    width: 40,
    height: 40,
    borderRadius: borderRadius.sm,
    backgroundColor: colors.module.expenseSoft,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.md,
  },
  iconText: {
    fontSize: 18,
  },
  content: {
    flex: 1,
  },
  title: {
    ...typography.body,
    color: colors.text,
    fontWeight: "500",
  },
  subtitle: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  rightSection: {
    alignItems: "flex-end",
  },
  amount: {
    ...typography.body,
    fontWeight: "600",
    color: colors.text,
  },
  draftBadge: {
    marginTop: spacing.xs,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.full,
    backgroundColor: colors.warning + "20",
  },
  draftText: {
    ...typography.caption,
    color: colors.warning,
    fontSize: 10,
  },
  confirmedBadge: {
    marginTop: spacing.xs,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.full,
    backgroundColor: colors.success + "20",
  },
  confirmedText: {
    ...typography.caption,
    color: colors.success,
    fontSize: 10,
  },
});
