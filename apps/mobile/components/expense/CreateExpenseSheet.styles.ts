import { StyleSheet } from "react-native";
import { colors, spacing, borderRadius, typography } from "@/constants/theme";

export const styles = StyleSheet.create({
  container: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xxxl,
  },
  title: {
    ...typography.subheading,
    color: colors.text,
    marginBottom: spacing.xl,
  },
  amountRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.lg,
  },
  currencyLabel: {
    ...typography.heading,
    color: colors.textSecondary,
    marginRight: spacing.sm,
  },
  amountInput: {
    flex: 1,
    ...typography.heading,
    color: colors.text,
    padding: spacing.sm,
    borderBottomWidth: 2,
    borderBottomColor: colors.module.expense,
  },
  section: {
    marginBottom: spacing.lg,
  },
  sectionLabel: {
    ...typography.label,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  paidByRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  memberChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.full,
    backgroundColor: colors.borderLight,
  },
  memberChipActive: {
    backgroundColor: colors.module.expense,
  },
  memberChipText: {
    ...typography.bodySmall,
    color: colors.textSecondary,
  },
  memberChipTextActive: {
    color: colors.textInverse,
  },
  splitModeRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  splitModeButton: {
    flex: 1,
    paddingVertical: spacing.sm,
    alignItems: "center",
    borderRadius: borderRadius.sm,
    backgroundColor: colors.borderLight,
  },
  splitModeButtonActive: {
    backgroundColor: colors.module.expenseSoft,
    borderWidth: 1,
    borderColor: colors.module.expense,
  },
  splitModeText: {
    ...typography.caption,
    color: colors.textSecondary,
  },
  splitModeTextActive: {
    color: colors.module.expense,
    fontWeight: "600",
  },
  splitRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
  },
  splitName: {
    ...typography.body,
    color: colors.text,
    flex: 1,
  },
  splitInput: {
    width: 80,
    textAlign: "right",
    ...typography.body,
    color: colors.text,
    padding: spacing.xs,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  splitEqual: {
    ...typography.body,
    color: colors.textSecondary,
    textAlign: "right",
    width: 80,
  },
  splitSuffix: {
    ...typography.caption,
    color: colors.textTertiary,
    marginLeft: spacing.xs,
  },
  validationError: {
    ...typography.caption,
    color: colors.error,
    marginTop: spacing.xs,
  },
  buttonRow: {
    flexDirection: "row",
    gap: spacing.md,
    marginTop: spacing.xl,
  },
  participantCheck: {
    width: 24,
    height: 24,
    borderRadius: 4,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.sm,
  },
  participantCheckActive: {
    borderColor: colors.module.expense,
    backgroundColor: colors.module.expense,
  },
  checkmark: {
    color: colors.textInverse,
    fontSize: 14,
    fontWeight: "700",
  },
  participantRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.sm,
  },
  participantName: {
    ...typography.body,
    color: colors.text,
  },
});
