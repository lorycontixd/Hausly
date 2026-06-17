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
  subtitle: {
    ...typography.bodySmall,
    color: colors.module.meal,
  },
  headcountRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  headcountLabel: {
    ...typography.label,
    color: colors.text,
  },
  stepper: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  headcountValue: {
    ...typography.subheading,
    color: colors.text,
    minWidth: 30,
    textAlign: "center",
  },
  deleteButton: {
    marginTop: spacing.sm,
  },
  readOnlyNotice: {
    ...typography.bodySmall,
    color: colors.textSecondary,
    textAlign: "center",
    fontStyle: "italic",
  },
});
