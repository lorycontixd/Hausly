import { StyleSheet } from "react-native";
import { colors, spacing, borderRadius, shadows } from "@/constants/theme";

export const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.xl,
    borderWidth: 1,
    borderColor: colors.border,
  },
  shadow: {
    ...shadows.md,
    borderColor: colors.borderLight,
  },
});
