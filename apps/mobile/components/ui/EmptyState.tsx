import { View, Text } from "react-native";
import { styles } from "./EmptyState.styles";

interface EmptyStateProps {
  icon?: string;
  title: string;
  message?: string;
}

export function EmptyState({
  icon = "📭",
  title,
  message,
}: EmptyStateProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.icon}>{icon}</Text>
      <Text style={styles.title}>{title}</Text>
      {message && <Text style={styles.message}>{message}</Text>}
    </View>
  );
}
