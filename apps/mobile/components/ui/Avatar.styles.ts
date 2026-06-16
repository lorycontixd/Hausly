import { StyleSheet } from "react-native";
import { colors, borderRadius, typography } from "@/constants/theme";

export const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    justifyContent: "center",
    borderRadius: borderRadius.full,
    overflow: "hidden",
  },
  image: {
    width: "100%",
    height: "100%",
  },
  fallback: {
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primarySoft,
  },
  initials: {
    ...typography.label,
    color: colors.primary,
  },
  initialsLarge: {
    fontSize: 20,
    fontWeight: "600",
  },
});
