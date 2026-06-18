import { StyleSheet } from "react-native";
import { colors, spacing, typography } from "@/constants/theme";

export const styles = StyleSheet.create({
  container: {
    marginBottom: spacing.xl,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.md,
    paddingHorizontal: spacing.lg,
  },
  sectionTitle: {
    ...typography.label,
    color: colors.textSecondary,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  overdueTitle: {
    ...typography.label,
    color: colors.error,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  badge: {
    ...typography.caption,
    color: colors.textTertiary,
  },
  list: {
    paddingHorizontal: spacing.lg,
  },
});
