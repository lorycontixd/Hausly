import { StyleSheet } from "react-native";
import { colors, spacing, borderRadius, typography } from "@/constants/theme";

export const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: borderRadius.sm,
    padding: spacing.md,
    minHeight: 80,
    borderWidth: 1,
    borderColor: colors.border,
  },
  slotLabel: {
    ...typography.caption,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  content: {
    flex: 1,
    justifyContent: "space-between",
  },
  text: {
    ...typography.bodySmall,
    color: colors.text,
  },
  meta: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: spacing.xs,
  },
  owner: {
    ...typography.caption,
    color: colors.module.meal,
  },
  headcount: {
    ...typography.caption,
    color: colors.textTertiary,
  },
  empty: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  emptyText: {
    ...typography.caption,
    color: colors.textTertiary,
    fontStyle: "italic",
  },
});
