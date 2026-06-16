import { ActivityIndicator, View, StyleSheet } from "react-native";
import { colors } from "@/constants/theme";

interface LoadingSpinnerProps {
  size?: "small" | "large";
  color?: string;
}

export function LoadingSpinner({
  size = "large",
  color = colors.primary,
}: LoadingSpinnerProps) {
  return (
    <View style={loadingStyles.container}>
      <ActivityIndicator size={size} color={color} />
    </View>
  );
}

const loadingStyles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
});
