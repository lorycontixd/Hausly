import { Pressable, Text, View } from "react-native";
import { MealPlanEntry, MealSlot } from "@hausly/types";
import { useHouseholdStore } from "@/stores/householdStore";
import { styles } from "./MealSlotCard.styles";

interface MealSlotCardProps {
  slot: MealSlot;
  entry: MealPlanEntry | null;
  onPress: () => void;
}

export function MealSlotCard({ slot, entry, onPress }: MealSlotCardProps) {
  const slotLabel = slot === "lunch" ? "🍽️ Lunch" : "🌙 Dinner";
  const members = useHouseholdStore((s) => s.members);

  const ownerName = entry?.owner_display_name
    || members.find((m) => m.user_id === entry?.owner_user_id)?.display_name
    || "Someone";

  return (
    <Pressable style={styles.container} onPress={onPress}>
      <Text style={styles.slotLabel}>{slotLabel}</Text>
      {entry ? (
        <View style={styles.content}>
          <Text style={styles.text} numberOfLines={2}>
            {entry.text}
          </Text>
          <View style={styles.meta}>
            <Text style={styles.owner}>{ownerName}</Text>
            <Text style={styles.headcount}>👥 {entry.headcount}</Text>
          </View>
        </View>
      ) : (
        <View style={styles.empty}>
          <Text style={styles.emptyText}>Tap to claim</Text>
        </View>
      )}
    </Pressable>
  );
}
