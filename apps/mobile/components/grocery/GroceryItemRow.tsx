import { View, Text, Pressable } from "react-native";
import { GroceryItem } from "@hausly/types";
import { styles } from "./GroceryItemRow.styles";

interface GroceryItemRowProps {
  item: GroceryItem;
  isSessionActive: boolean;
  isChecked: boolean;
  onToggle: () => void;
  onDelete: () => void;
  isOwner: boolean;
}

export function GroceryItemRow({
  item,
  isSessionActive,
  isChecked,
  onToggle,
  onDelete,
  isOwner,
}: GroceryItemRowProps) {
  const quantityText = item.quantity
    ? `${item.quantity}${item.unit ? ` ${item.unit}` : ""}`
    : null;

  return (
    <Pressable
      style={[styles.container, isChecked && styles.checked]}
      onPress={isSessionActive ? onToggle : undefined}
      onLongPress={!isSessionActive ? onDelete : undefined}
    >
      {isSessionActive && (
        <View style={[styles.checkbox, isChecked && styles.checkboxActive]}>
          {isChecked && <Text style={styles.checkmark}>✓</Text>}
        </View>
      )}

      <View style={styles.content}>
        <Text style={[styles.name, isChecked && styles.nameChecked]}>
          {item.name}
        </Text>
        {quantityText && <Text style={styles.quantity}>{quantityText}</Text>}
      </View>

      {item.is_personal && (
        <View style={styles.personalBadge}>
          <Text style={styles.personalBadgeText}>
            {isOwner ? "👤" : "🔒"}
          </Text>
        </View>
      )}
    </Pressable>
  );
}
