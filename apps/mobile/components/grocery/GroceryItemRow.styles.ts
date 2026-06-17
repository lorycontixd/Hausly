import { StyleSheet } from "react-native";
import { colors, spacing, borderRadius, typography } from "@/constants/theme";

export const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  checked: {
    backgroundColor: colors.module.grocerySoft,
    borderColor: colors.module.grocery,
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: borderRadius.sm,
    borderWidth: 2,
    borderColor: colors.border,
    marginRight: spacing.md,
    alignItems: "center",
    justifyContent: "center",
  },
  checkboxActive: {
    backgroundColor: colors.module.grocery,
    borderColor: colors.module.grocery,
  },
  checkmark: {
    color: colors.textInverse,
    fontSize: 14,
    fontWeight: "700",
  },
  content: {
    flex: 1,
  },
  name: {
    ...typography.body,
    color: colors.text,
  },
  nameChecked: {
    textDecorationLine: "line-through",
    color: colors.textSecondary,
  },
  quantity: {
    ...typography.caption,
    color: colors.textTertiary,
    marginTop: 2,
  },
  personalBadge: {
    marginLeft: spacing.sm,
  },
  personalBadgeText: {
    fontSize: 16,
  },
});
