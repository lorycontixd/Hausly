import { StyleSheet } from "react-native";
import { colors, spacing, borderRadius, shadows, typography } from "@/constants/theme";

export const styles = StyleSheet.create({
  container: {
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    ...shadows.sm,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  headerTitle: {
    ...typography.label,
    color: colors.textSecondary,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.sm,
  },
  separator: {
    height: 1,
    backgroundColor: colors.borderLight,
  },
  names: {
    flex: 1,
  },
  nameText: {
    ...typography.body,
    color: colors.text,
  },
  directionText: {
    ...typography.caption,
    color: colors.textSecondary,
  },
  amountOwed: {
    ...typography.body,
    fontWeight: "600",
    color: colors.destructive,
  },
  amountOwedTo: {
    ...typography.body,
    fontWeight: "600",
    color: colors.success,
  },
  settledText: {
    ...typography.body,
    color: colors.textTertiary,
  },
  emptyText: {
    ...typography.bodySmall,
    color: colors.textSecondary,
    textAlign: "center",
    paddingVertical: spacing.lg,
  },
});
