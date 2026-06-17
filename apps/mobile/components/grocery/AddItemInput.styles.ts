import { StyleSheet } from "react-native";
import { colors, spacing, borderRadius } from "@/constants/theme";

export const styles = StyleSheet.create({
  container: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  inputWrapper: {
    flex: 1,
  },
  personalToggle: {
    width: 40,
    height: 40,
    borderRadius: borderRadius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  personalToggleActive: {
    backgroundColor: colors.module.grocerySoft,
    borderColor: colors.module.grocery,
  },
  personalToggleText: {
    fontSize: 18,
  },
  addButton: {
    width: 40,
    height: 40,
    borderRadius: borderRadius.sm,
    backgroundColor: colors.module.grocery,
    alignItems: "center",
    justifyContent: "center",
  },
  addButtonDisabled: {
    opacity: 0.4,
  },
  addButtonText: {
    color: colors.textInverse,
    fontSize: 22,
    fontWeight: "700",
  },
});
