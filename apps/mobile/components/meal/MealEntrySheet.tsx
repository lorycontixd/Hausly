import { useState, useEffect } from "react";
import { View, Text, Alert } from "react-native";
import { MealPlanEntry } from "@hausly/types";
import { useHouseholdStore } from "@/stores/householdStore";
import { useCreateMeal, useUpdateMeal, useDeleteMeal } from "@/hooks/useMeals";
import { useAuthContext } from "@/providers/AuthProvider";
import { Sheet, Input, Button } from "@/components/ui";
import { styles } from "./MealEntrySheet.styles";

interface MealEntrySheetProps {
  visible: boolean;
  onClose: () => void;
  date: string;
  slot: "lunch" | "dinner";
  existingEntry: MealPlanEntry | null;
}

export function MealEntrySheet({
  visible,
  onClose,
  date,
  slot,
  existingEntry,
}: MealEntrySheetProps) {
  const householdId = useHouseholdStore((s) => s.id);
  const members = useHouseholdStore((s) => s.members);
  const memberCount = members.length;
  const { profile } = useAuthContext();
  const userId = profile?.user_id ?? null;

  const createMeal = useCreateMeal(householdId);
  const updateMeal = useUpdateMeal(householdId);
  const deleteMeal = useDeleteMeal(householdId);

  const [text, setText] = useState("");
  const [headcount, setHeadcount] = useState(memberCount || 2);

  const isOwner = existingEntry?.owner_user_id === userId;
  const isEditing = existingEntry != null;
  const ownerName = existingEntry?.owner_display_name
    || members.find((m) => m.user_id === existingEntry?.owner_user_id)?.display_name
    || "the owner";

  useEffect(() => {
    if (visible) {
      if (existingEntry) {
        setText(existingEntry.text);
        setHeadcount(existingEntry.headcount);
      } else {
        setText("");
        setHeadcount(memberCount || 2);
      }
    }
  }, [visible, existingEntry, memberCount]);

  const handleSave = () => {
    if (!text.trim()) return;

    if (isEditing && existingEntry) {
      updateMeal.mutate(
        { entryId: existingEntry.id, data: { text: text.trim(), headcount } },
        {
          onSuccess: onClose,
          onError: (err) =>
            Alert.alert("Error", err.message || "Could not update meal entry."),
        }
      );
    } else {
      createMeal.mutate(
        { date, slot, text: text.trim(), headcount },
        {
          onSuccess: onClose,
          onError: (err) => {
            const code = (err as { code?: string }).code;
            if (code === "CONFLICT" || (err.message && err.message.includes("409"))) {
              Alert.alert(
                "Slot taken",
                "Someone already claimed this slot. Pull to refresh."
              );
            } else {
              Alert.alert("Error", err.message || "Could not create meal entry.");
            }
            onClose();
          },
        }
      );
    }
  };

  const handleDelete = () => {
    if (!existingEntry) return;
    Alert.alert("Delete entry", "Remove this meal entry?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: () => {
          deleteMeal.mutate(existingEntry.id, { onSuccess: onClose });
        },
      },
    ]);
  };

  const slotLabel = slot === "lunch" ? "Lunch" : "Dinner";
  const dateLabel = new Date(date + "T00:00:00").toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });

  return (
    <Sheet visible={visible} onClose={onClose}>
      <View style={styles.content}>
        <Text style={styles.title}>
          {isEditing ? "Edit Meal" : "Claim Slot"}
        </Text>
        <Text style={styles.subtitle}>
          {slotLabel} — {dateLabel}
        </Text>

        <Input
          label="What's cooking?"
          placeholder="e.g. Pasta al pomodoro"
          value={text}
          onChangeText={setText}
          editable={!isEditing || isOwner}
        />

        <View style={styles.headcountRow}>
          <Text style={styles.headcountLabel}>Headcount</Text>
          <View style={styles.stepper}>
            <Button
              title="−"
              variant="secondary"
              size="small"
              onPress={() => setHeadcount(Math.max(1, headcount - 1))}
              disabled={headcount <= 1 || (isEditing && !isOwner)}
            />
            <Text style={styles.headcountValue}>{headcount}</Text>
            <Button
              title="+"
              variant="secondary"
              size="small"
              onPress={() => setHeadcount(headcount + 1)}
              disabled={isEditing && !isOwner}
            />
          </View>
        </View>

        {(!isEditing || isOwner) && (
          <Button
            title={isEditing ? "Save Changes" : "Claim Slot"}
            onPress={handleSave}
            loading={createMeal.isPending || updateMeal.isPending}
            disabled={!text.trim()}
          />
        )}

        {isEditing && isOwner && (
          <Button
            title="Delete Entry"
            variant="destructive"
            onPress={handleDelete}
            loading={deleteMeal.isPending}
            style={styles.deleteButton}
          />
        )}

        {isEditing && !isOwner && (
          <Text style={styles.readOnlyNotice}>
            Only {ownerName} or an admin can edit this entry.
          </Text>
        )}
      </View>
    </Sheet>
  );
}
