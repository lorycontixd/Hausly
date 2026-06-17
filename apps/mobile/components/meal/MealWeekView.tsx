import { View, Text, Pressable } from "react-native";
import { MealPlanEntry, MealSlot } from "@hausly/types";
import { MealSlotCard } from "./MealSlotCard";
import { styles } from "./MealWeekView.styles";

interface MealWeekViewProps {
  days: string[];
  entries: MealPlanEntry[];
  onSlotPress: (date: string, slot: MealSlot, entry: MealPlanEntry | null) => void;
  onPrevWeek: () => void;
  onNextWeek: () => void;
  weekLabel: string;
}

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function formatDayLabel(dateStr: string): string {
  const date = new Date(dateStr + "T00:00:00");
  const dayIndex = (date.getDay() + 6) % 7;
  const day = date.getDate();
  return `${DAY_LABELS[dayIndex]} ${day}`;
}

function getEntryForSlot(
  entries: MealPlanEntry[],
  date: string,
  slot: MealSlot
): MealPlanEntry | null {
  return entries.find((e) => e.date === date && e.slot === slot) ?? null;
}

export function MealWeekView({
  days,
  entries,
  onSlotPress,
  onPrevWeek,
  onNextWeek,
  weekLabel,
}: MealWeekViewProps) {
  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Pressable onPress={onPrevWeek} style={styles.navButton}>
          <Text style={styles.navText}>‹</Text>
        </Pressable>
        <Text style={styles.weekLabel}>{weekLabel}</Text>
        <Pressable onPress={onNextWeek} style={styles.navButton}>
          <Text style={styles.navText}>›</Text>
        </Pressable>
      </View>

      {days.map((date) => {
        const lunchEntry = getEntryForSlot(entries, date, "lunch");
        const dinnerEntry = getEntryForSlot(entries, date, "dinner");

        return (
          <View key={date} style={styles.dayRow}>
            <Text style={styles.dayLabel}>{formatDayLabel(date)}</Text>
            <View style={styles.slotsRow}>
              <MealSlotCard
                slot="lunch"
                entry={lunchEntry}
                onPress={() => onSlotPress(date, "lunch", lunchEntry)}
              />
              <View style={styles.slotGap} />
              <MealSlotCard
                slot="dinner"
                entry={dinnerEntry}
                onPress={() => onSlotPress(date, "dinner", dinnerEntry)}
              />
            </View>
          </View>
        );
      })}
    </View>
  );
}
