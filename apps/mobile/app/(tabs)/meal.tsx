import { useCallback, useMemo } from "react";
import { ScrollView } from "react-native";
import { useHouseholdStore } from "@/stores/householdStore";
import { useMealStore } from "@/stores/mealStore";
import { useMealEntries } from "@/hooks/useMeals";
import { MealWeekView } from "@/components/meal/MealWeekView";
import { MealEntrySheet } from "@/components/meal/MealEntrySheet";
import { LoadingSpinner, EmptyState } from "@/components/ui";
import { MealPlanEntry, MealSlot } from "@hausly/types";

function getWeekDays(offset: number): string[] {
  const today = new Date();
  const monday = new Date(today);
  const day = today.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  monday.setDate(today.getDate() + diff + offset * 7);

  const days: string[] = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    days.push(d.toISOString().split("T")[0]);
  }
  return days;
}

function getWeekLabel(days: string[]): string {
  const start = new Date(days[0] + "T00:00:00");
  const end = new Date(days[6] + "T00:00:00");
  const opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" };
  return `${start.toLocaleDateString(undefined, opts)} – ${end.toLocaleDateString(undefined, opts)}`;
}

export default function MealScreen() {
  const householdId = useHouseholdStore((s) => s.id);

  const weekOffset = useMealStore((s) => s.weekOffset);
  const nextWeek = useMealStore((s) => s.nextWeek);
  const prevWeek = useMealStore((s) => s.prevWeek);
  const sheetVisible = useMealStore((s) => s.sheetVisible);
  const selectedSlot = useMealStore((s) => s.selectedSlot);
  const editingEntryId = useMealStore((s) => s.editingEntryId);
  const openSheet = useMealStore((s) => s.openSheet);
  const closeSheet = useMealStore((s) => s.closeSheet);

  const days = useMemo(() => getWeekDays(weekOffset), [weekOffset]);
  const weekLabel = useMemo(() => getWeekLabel(days), [days]);

  const { data: entries, isLoading } = useMealEntries(
    householdId,
    days[0],
    days[6]
  );

  const handleSlotPress = useCallback(
    (date: string, slot: MealSlot, entry: MealPlanEntry | null) => {
      openSheet({ date, slot }, entry?.id);
    },
    [openSheet]
  );

  const activeEntry = useMemo(() => {
    if (!editingEntryId || !entries) return null;
    return entries.find((e) => e.id === editingEntryId) ?? null;
  }, [editingEntryId, entries]);

  if (!householdId) {
    return (
      <EmptyState
        icon="🏠"
        title="No household"
        message="Join or create a household to start meal planning."
      />
    );
  }

  if (isLoading) {
    return <LoadingSpinner />;
  }

  return (
    <>
      <ScrollView style={{ flex: 1 }}>
        <MealWeekView
          days={days}
          entries={entries ?? []}
          onSlotPress={handleSlotPress}
          onPrevWeek={prevWeek}
          onNextWeek={nextWeek}
          weekLabel={weekLabel}
        />
      </ScrollView>

      {selectedSlot && (
        <MealEntrySheet
          visible={sheetVisible}
          onClose={closeSheet}
          date={selectedSlot.date}
          slot={selectedSlot.slot}
          existingEntry={activeEntry}
        />
      )}
    </>
  );
}
