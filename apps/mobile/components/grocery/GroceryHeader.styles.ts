import { StyleSheet } from "react-native";
import { colors, spacing, borderRadius, typography } from "@/constants/theme";

export const styles = StyleSheet.create({
  container: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  actions: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  actionButton: {
    backgroundColor: colors.module.grocery,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.sm,
  },
  actionButtonText: {
    ...typography.label,
    color: colors.textInverse,
  },
  filterButton: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  filterActive: {
    backgroundColor: colors.module.grocerySoft,
    borderColor: colors.module.grocery,
  },
  filterButtonText: {
    ...typography.bodySmall,
    color: colors.textSecondary,
  },
  filterActiveText: {
    color: colors.module.grocery,
  },
  spacer: {
    flex: 1,
  },
  clearButton: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
  },
  clearButtonText: {
    ...typography.bodySmall,
    color: colors.destructive,
  },
  sessionBanner: {
    backgroundColor: colors.module.grocerySoft,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    borderRadius: borderRadius.md,
    alignItems: "center",
  },
  sessionTitle: {
    ...typography.subheading,
    color: colors.module.grocery,
  },
  sessionSubtitle: {
    ...typography.bodySmall,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
});
