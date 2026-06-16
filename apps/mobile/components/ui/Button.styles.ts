import { StyleSheet } from "react-native";
import { colors, spacing, borderRadius, typography, shadows } from "@/constants/theme";

export const styles = StyleSheet.create({
  base: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    borderRadius: borderRadius.md,
    gap: spacing.sm,
  },
  primary: {
    backgroundColor: colors.primary,
    ...shadows.sm,
  },
  secondary: {
    backgroundColor: colors.primarySoft,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  destructive: {
    backgroundColor: colors.destructive,
  },
  disabled: {
    opacity: 0.5,
  },
  textPrimary: {
    ...typography.label,
    color: colors.textInverse,
  },
  textSecondary: {
    ...typography.label,
    color: colors.primary,
  },
  textDestructive: {
    ...typography.label,
    color: colors.textInverse,
  },
  small: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
  },
  large: {
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.xxl,
  },
});
