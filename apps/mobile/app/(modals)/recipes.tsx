import { View, StyleSheet } from "react-native";
import { EmptyState } from "@/components/ui";
import { colors } from "@/constants/theme";

export default function RecipesScreen() {
  return (
    <View style={styles.container}>
      <EmptyState
        icon="📖"
        title="My Recipes"
        message="Recipe book coming soon — stay tuned!"
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
