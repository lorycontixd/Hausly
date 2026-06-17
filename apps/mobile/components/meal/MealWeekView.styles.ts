import { StyleSheet } from "react-native";
import { colors, spacing, typography } from "@/constants/theme";

export const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  navButton: {
    padding: spacing.sm,
  },
  navText: {
    fontSize: 28,
    color: colors.primary,
    fontWeight: "600",
  },
  weekLabel: {
    ...typography.subheading,
    color: colors.text,
  },
  dayRow: {
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  dayLabel: {
    ...typography.label,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  slotsRow: {
    flexDirection: "row",
  },
  slotGap: {
    width: spacing.sm,
  },
});
