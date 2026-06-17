import { View, Text, Pressable } from "react-native";
import { styles } from "./GroceryHeader.styles";

interface GroceryHeaderProps {
  isSessionActive: boolean;
  showPersonalOnly: boolean;
  onToggleFilter: () => void;
  onStartSession: () => void;
  onCancelSession: () => void;
  onDoneSession: () => void;
  onClearList: () => void;
  checkedCount: number;
}

export function GroceryHeader({
  isSessionActive,
  showPersonalOnly,
  onToggleFilter,
  onStartSession,
  onCancelSession,
  onDoneSession,
  onClearList,
  checkedCount,
}: GroceryHeaderProps) {
  if (isSessionActive) {
    return (
      <View style={styles.container}>
        <View style={styles.sessionBanner}>
          <Text style={styles.sessionTitle}>🛒 Shopping Mode</Text>
          <Text style={styles.sessionSubtitle}>
            {checkedCount} item{checkedCount !== 1 ? "s" : ""} checked
          </Text>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.actions}>
        <Pressable style={styles.actionButton} onPress={onStartSession}>
          <Text style={styles.actionButtonText}>🛒 Start Shopping</Text>
        </Pressable>
        <Pressable
          style={[styles.filterButton, showPersonalOnly && styles.filterActive]}
          onPress={onToggleFilter}
        >
          <Text
            style={[
              styles.filterButtonText,
              showPersonalOnly && styles.filterActiveText,
            ]}
          >
            {showPersonalOnly ? "👤 Personal" : "All"}
          </Text>
        </Pressable>
        <View style={styles.spacer} />
        <Pressable style={styles.clearButton} onPress={onClearList}>
          <Text style={styles.clearButtonText}>Clear</Text>
        </Pressable>
      </View>
    </View>
  );
}
