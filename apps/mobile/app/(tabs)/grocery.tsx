import { useState, useCallback } from "react";
import { View, FlatList, Alert } from "react-native";
import { useHouseholdStore } from "@/stores/householdStore";
import { useGroceryStore } from "@/stores/groceryStore";
import {
  useGroceryItems,
  useAddGroceryItem,
  useDeleteGroceryItem,
  useCompleteSession,
  useArchiveGroceryList,
} from "@/hooks/useGrocery";
import { useAuthContext } from "@/providers/AuthProvider";
import { GroceryItem } from "@hausly/types";
import { EmptyState, Button } from "@/components/ui";
import { GroceryItemRow } from "@/components/grocery/GroceryItemRow";
import { AddItemInput } from "@/components/grocery/AddItemInput";
import { SessionSummary } from "@/components/grocery/SessionSummary";
import { GroceryHeader } from "@/components/grocery/GroceryHeader";
import { styles } from "@/components/grocery/GroceryScreen.styles";

export default function GroceryScreen() {
  const householdId = useHouseholdStore((s) => s.id);
  const { profile } = useAuthContext();
  const userId = profile?.user_id ?? null;

  const { data: items, isLoading } = useGroceryItems(householdId);
  const addItem = useAddGroceryItem(householdId);
  const deleteItem = useDeleteGroceryItem(householdId);
  const completeSession = useCompleteSession(householdId);
  const archiveList = useArchiveGroceryList(householdId);

  const isSessionActive = useGroceryStore((s) => s.isSessionActive);
  const checkedItemIds = useGroceryStore((s) => s.checkedItemIds);
  const startSession = useGroceryStore((s) => s.startSession);
  const endSession = useGroceryStore((s) => s.endSession);
  const toggleItem = useGroceryStore((s) => s.toggleItem);
  const addPendingOperation = useGroceryStore((s) => s.addPendingOperation);

  const [showPersonalOnly, setShowPersonalOnly] = useState(false);
  const [showSummary, setShowSummary] = useState(false);

  const filteredItems = (items ?? []).filter((item) => {
    if (showPersonalOnly) return item.is_personal;
    return true;
  });

  const handleAddItem = useCallback(
    (name: string, isPersonal: boolean) => {
      if (!name.trim()) return;
      addItem.mutate({ name: name.trim(), is_personal: isPersonal });
    },
    [addItem]
  );

  const handleDeleteItem = useCallback(
    (itemId: string) => {
      deleteItem.mutate(itemId);
    },
    [deleteItem]
  );

  const handleSessionDone = useCallback(() => {
    if (checkedItemIds.size === 0) {
      Alert.alert("No items checked", "Check items before finishing.");
      return;
    }
    setShowSummary(true);
  }, [checkedItemIds]);

  const handleSessionConfirm = useCallback(
    (receiptTotal: number, createExpense: boolean) => {
      if (!householdId) return;

      const payload = {
        bought_item_ids: Array.from(checkedItemIds),
        receipt_total: receiptTotal,
        create_expense: createExpense,
      };

      completeSession.mutate(payload, {
        onSuccess: () => {
          endSession();
          setShowSummary(false);
        },
        onError: () => {
          // Offline: queue for later
          addPendingOperation({
            type: "session_complete",
            payload: { householdId, ...payload },
          });
          endSession();
          setShowSummary(false);
          Alert.alert(
            "Saved offline",
            "Your shopping will be synced when you reconnect."
          );
        },
      });
    },
    [householdId, checkedItemIds, completeSession, endSession, addPendingOperation]
  );

  const handleClearList = useCallback(() => {
    Alert.alert(
      "Clear grocery list",
      "This will archive all items. Are you sure?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Clear",
          style: "destructive",
          onPress: () => archiveList.mutate(),
        },
      ]
    );
  }, [archiveList]);

  const renderItem = useCallback(
    ({ item }: { item: GroceryItem }) => (
      <GroceryItemRow
        item={item}
        isSessionActive={isSessionActive}
        isChecked={checkedItemIds.has(item.id)}
        onToggle={() => toggleItem(item.id)}
        onDelete={() => handleDeleteItem(item.id)}
        isOwner={item.personal_for_user_id === userId}
      />
    ),
    [isSessionActive, checkedItemIds, toggleItem, handleDeleteItem, userId]
  );

  if (showSummary) {
    const checkedItems = (items ?? []).filter((i) => checkedItemIds.has(i.id));
    return (
      <SessionSummary
        items={checkedItems}
        onConfirm={handleSessionConfirm}
        onCancel={() => setShowSummary(false)}
        isLoading={completeSession.isPending}
      />
    );
  }

  return (
    <View style={styles.container}>
      <GroceryHeader
        isSessionActive={isSessionActive}
        showPersonalOnly={showPersonalOnly}
        onToggleFilter={() => setShowPersonalOnly(!showPersonalOnly)}
        onStartSession={startSession}
        onCancelSession={endSession}
        onDoneSession={handleSessionDone}
        onClearList={handleClearList}
        checkedCount={checkedItemIds.size}
      />

      {!isSessionActive && <AddItemInput onAdd={handleAddItem} />}

      <FlatList
        data={filteredItems}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        contentContainerStyle={styles.listContent}
        ListEmptyComponent={
          isLoading ? null : (
            <EmptyState
              icon="🛒"
              title="No items yet"
              message="Add items to your grocery list"
            />
          )
        }
      />

      {isSessionActive && (
        <View style={styles.sessionFooter}>
          <Button
            title="Cancel"
            variant="secondary"
            onPress={endSession}
          />
          <Button
            title={`Done (${checkedItemIds.size})`}
            onPress={handleSessionDone}
          />
        </View>
      )}
    </View>
  );
}
