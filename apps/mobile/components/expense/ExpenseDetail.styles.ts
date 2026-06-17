import { StyleSheet } from "react-native";
import { colors, spacing, borderRadius, shadows, typography } from "@/constants/theme";

export const styles = StyleSheet.create({
  container: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xxxl,
  },
  header: {
    alignItems: "center",
    paddingVertical: spacing.xl,
  },
  amount: {
    ...typography.heading,
    fontSize: 32,
    color: colors.text,
  },
  title: {
    ...typography.subheading,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  badge: {
    marginTop: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
  },
  badgeDraft: {
    backgroundColor: colors.warning + "20",
  },
  badgeConfirmed: {
    backgroundColor: colors.success + "20",
  },
  badgeText: {
    ...typography.caption,
    fontWeight: "600",
  },
  badgeTextDraft: {
    color: colors.warning,
  },
  badgeTextConfirmed: {
    color: colors.success,
  },
  section: {
    marginTop: spacing.xl,
  },
  sectionTitle: {
    ...typography.label,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  infoRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
  },
  infoLabel: {
    ...typography.bodySmall,
    color: colors.textSecondary,
  },
  infoValue: {
    ...typography.bodySmall,
    color: colors.text,
    fontWeight: "500",
  },
  splitRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  splitName: {
    ...typography.body,
    color: colors.text,
  },
  splitAmount: {
    ...typography.body,
    color: colors.text,
    fontWeight: "500",
  },
  splitSettled: {
    ...typography.caption,
    color: colors.success,
    marginTop: 2,
  },
  splitUnsettled: {
    ...typography.caption,
    color: colors.textTertiary,
    marginTop: 2,
  },
  actionRow: {
    flexDirection: "row",
    gap: spacing.md,
    marginTop: spacing.xxl,
  },
  sourceTag: {
    ...typography.caption,
    color: colors.textTertiary,
    marginTop: spacing.xs,
  },
});
