import { StyleSheet } from "react-native";
import { colors, spacing, borderRadius, shadows, typography } from "@/constants/theme";

export const styles = StyleSheet.create({
  container: {
    padding: spacing.lg,
    marginBottom: spacing.sm,
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    ...shadows.sm,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.md,
  },
  separator: {
    height: 1,
    backgroundColor: colors.borderLight,
  },
  left: {
    flex: 1,
  },
  names: {
    ...typography.body,
    color: colors.text,
  },
  arrow: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  right: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  amount: {
    ...typography.body,
    fontWeight: "600",
    color: colors.text,
  },
  settleButton: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.sm,
    backgroundColor: colors.success,
  },
  settleButtonText: {
    ...typography.caption,
    color: colors.textInverse,
    fontWeight: "600",
  },
  emptyText: {
    ...typography.bodySmall,
    color: colors.textSecondary,
    textAlign: "center",
    paddingVertical: spacing.lg,
  },
  header: {
    ...typography.label,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
});
