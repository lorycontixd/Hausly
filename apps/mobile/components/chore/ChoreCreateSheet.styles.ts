import { StyleSheet } from "react-native";
import { colors, spacing, typography } from "@/constants/theme";

export const styles = StyleSheet.create({
  content: {
    padding: spacing.lg,
    gap: spacing.lg,
  },
  title: {
    ...typography.heading,
    color: colors.text,
  },
  label: {
    ...typography.label,
    color: colors.text,
    marginBottom: spacing.xs,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  toggleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  toggleLabel: {
    ...typography.body,
    color: colors.text,
  },
  recurrenceRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  intervalInput: {
    width: 60,
    textAlign: "center",
  },
  unitButton: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  unitButtonActive: {
    backgroundColor: colors.module.chore,
    borderColor: colors.module.chore,
  },
  unitButtonText: {
    ...typography.bodySmall,
    color: colors.textSecondary,
  },
  unitButtonTextActive: {
    ...typography.bodySmall,
    color: colors.textInverse,
    fontWeight: "600",
  },
  assigneeRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
  },
  assigneeName: {
    ...typography.body,
    color: colors.text,
  },
  assigneeYou: {
    ...typography.caption,
    color: colors.textSecondary,
    marginLeft: spacing.xs,
  },
  preview: {
    ...typography.bodySmall,
    color: colors.module.chore,
    fontStyle: "italic",
    marginTop: spacing.xs,
  },
  error: {
    ...typography.caption,
    color: colors.error,
  },
  deleteButton: {
    marginTop: spacing.sm,
  },
});
