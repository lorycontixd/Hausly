import { View, StyleSheet } from "react-native";
import { EmptyState } from "@/components/ui";
import { colors } from "@/constants/theme";

export default function PreferencesScreen() {
  return (
    <View style={styles.container}>
      <EmptyState
        icon="⚙️"
        title="Preferences"
        message="User preferences coming soon."
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
});
