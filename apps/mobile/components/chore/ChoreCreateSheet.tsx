import { useState, useEffect, useMemo } from "react";
import { View, Text, Switch, Pressable, Alert } from "react-native";
import { Chore, RecurrenceUnit } from "@hausly/types";
import { useHouseholdStore } from "@/stores/householdStore";
import { useAuthContext } from "@/providers/AuthProvider";
import { useCreateChore, useUpdateChore, useDeleteChore } from "@/hooks/useChores";
import { Sheet, Input, Button } from "@/components/ui";
import { styles } from "./ChoreCreateSheet.styles";

interface ChoreCreateSheetProps {
  visible: boolean;
  onClose: () => void;
  existingChore: Chore | null;
}

const UNITS: RecurrenceUnit[] = ["days", "weeks", "months"];

export function ChoreCreateSheet({
  visible,
  onClose,
  existingChore,
}: ChoreCreateSheetProps) {
  const householdId = useHouseholdStore((s) => s.id);
  const members = useHouseholdStore((s) => s.members);
  const { profile } = useAuthContext();
  const userId = profile?.user_id ?? "";

  const createChore = useCreateChore(householdId);
  const updateChore = useUpdateChore(householdId);
  const deleteChore = useDeleteChore(householdId);

  const isEditing = existingChore != null;

  const [name, setName] = useState("");
  const [startDate, setStartDate] = useState(
    new Date().toISOString().split("T")[0]
  );
  const [isRecurring, setIsRecurring] = useState(false);
  const [interval, setInterval] = useState("1");
  const [unit, setUnit] = useState<RecurrenceUnit>("weeks");
  const [selectedAssignees, setSelectedAssignees] = useState<string[]>([]);
  const [rotationEnabled, setRotationEnabled] = useState(false);

  useEffect(() => {
    if (visible) {
      if (existingChore) {
        setName(existingChore.name);
        setStartDate(existingChore.start_date);
        setIsRecurring(existingChore.is_recurring);
        setInterval(String(existingChore.recurrence_interval ?? 1));
        setUnit(existingChore.recurrence_unit ?? "weeks");
        setSelectedAssignees(
          existingChore.assignees.map((a) => a.user_id)
        );
        setRotationEnabled(existingChore.rotation_enabled);
      } else {
        setName("");
        setStartDate(new Date().toISOString().split("T")[0]);
        setIsRecurring(false);
        setInterval("1");
        setUnit("weeks");
        setSelectedAssignees([userId]);
        setRotationEnabled(false);
      }
    }
  }, [visible, existingChore, userId]);

  const toggleAssignee = (uid: string) => {
    setSelectedAssignees((prev) =>
      prev.includes(uid) ? prev.filter((id) => id !== uid) : [...prev, uid]
    );
  };

  const rotationPreview = useMemo(() => {
    if (!isRecurring || !rotationEnabled || selectedAssignees.length < 2)
      return null;
    const intervalNum = parseInt(interval, 10) || 1;
    const personalFreq = intervalNum * selectedAssignees.length;
    return `Your turn every ${personalFreq} ${unit}`;
  }, [isRecurring, rotationEnabled, selectedAssignees.length, interval, unit]);

  const canSave =
    name.trim().length > 0 &&
    selectedAssignees.length > 0 &&
    selectedAssignees.includes(userId);

  const handleSave = () => {
    if (!canSave) return;

    const intervalNum = parseInt(interval, 10) || 1;
    const data = {
      name: name.trim(),
      start_date: startDate,
      is_recurring: isRecurring,
      recurrence_interval: isRecurring ? intervalNum : null,
      recurrence_unit: isRecurring ? unit : null,
      assignee_user_ids: selectedAssignees,
      rotation_enabled: selectedAssignees.length > 1 && rotationEnabled,
    };

    if (isEditing && existingChore) {
      updateChore.mutate(
        { choreId: existingChore.id, data },
        { onSuccess: onClose }
      );
    } else {
      createChore.mutate(data, { onSuccess: onClose });
    }
  };

  const handleDelete = () => {
    if (!existingChore) return;
    Alert.alert("Delete chore?", "This will cancel all future assignments.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: () => {
          deleteChore.mutate(existingChore.id, { onSuccess: onClose });
        },
      },
    ]);
  };

  return (
    <Sheet visible={visible} onClose={onClose}>
      <View style={styles.content}>
        <Text style={styles.title}>
          {isEditing ? "Edit Chore" : "New Chore"}
        </Text>

        <View>
          <Text style={styles.label}>Name</Text>
          <Input
            value={name}
            onChangeText={setName}
            placeholder="e.g. Clean bathroom"
          />
        </View>

        <View>
          <Text style={styles.label}>Starting</Text>
          <Input
            value={startDate}
            onChangeText={setStartDate}
            placeholder="YYYY-MM-DD"
          />
        </View>

        <View style={styles.toggleRow}>
          <Text style={styles.toggleLabel}>Make recurring</Text>
          <Switch value={isRecurring} onValueChange={setIsRecurring} />
        </View>

        {isRecurring && (
          <View>
            <Text style={styles.label}>Every</Text>
            <View style={styles.recurrenceRow}>
              <Input
                value={interval}
                onChangeText={setInterval}
                keyboardType="number-pad"
                style={styles.intervalInput}
              />
              {UNITS.map((u) => (
                <Pressable
                  key={u}
                  style={[
                    styles.unitButton,
                    u === unit && styles.unitButtonActive,
                  ]}
                  onPress={() => setUnit(u)}
                >
                  <Text
                    style={
                      u === unit
                        ? styles.unitButtonTextActive
                        : styles.unitButtonText
                    }
                  >
                    {u}
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>
        )}

        <View>
          <Text style={styles.label}>Assign to</Text>
          {members.map((m) => (
            <Pressable
              key={m.user_id}
              style={styles.assigneeRow}
              onPress={() => toggleAssignee(m.user_id)}
            >
              <View style={{ flexDirection: "row", alignItems: "center" }}>
                <Text style={styles.assigneeName}>{m.display_name}</Text>
                {m.user_id === userId && (
                  <Text style={styles.assigneeYou}>(you)</Text>
                )}
              </View>
              <Switch
                value={selectedAssignees.includes(m.user_id)}
                onValueChange={() => toggleAssignee(m.user_id)}
              />
            </Pressable>
          ))}
          {!selectedAssignees.includes(userId) && (
            <Text style={styles.error}>You must include yourself</Text>
          )}
        </View>

        {selectedAssignees.length > 1 && isRecurring && (
          <View style={styles.toggleRow}>
            <Text style={styles.toggleLabel}>Rotate between members</Text>
            <Switch
              value={rotationEnabled}
              onValueChange={setRotationEnabled}
            />
          </View>
        )}

        {rotationPreview && (
          <Text style={styles.preview}>{rotationPreview}</Text>
        )}

        <Button
          title={isEditing ? "Save Changes" : "Create"}
          onPress={handleSave}
          variant="primary"
          disabled={!canSave}
        />

        {isEditing && (
          <Button
            title="Delete Chore"
            onPress={handleDelete}
            variant="destructive"
            style={styles.deleteButton}
          />
        )}
      </View>
    </Sheet>
  );
}
