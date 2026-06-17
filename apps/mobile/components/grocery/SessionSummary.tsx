import { useState } from "react";
import { View, Text, Switch, ScrollView } from "react-native";
import { GroceryItem } from "@hausly/types";
import { Button, Input } from "@/components/ui";
import { styles } from "./SessionSummary.styles";

interface SessionSummaryProps {
  items: GroceryItem[];
  onConfirm: (receiptTotal: number, createExpense: boolean) => void;
  onCancel: () => void;
  isLoading: boolean;
}

export function SessionSummary({
  items,
  onConfirm,
  onCancel,
  isLoading,
}: SessionSummaryProps) {
  const [receiptTotal, setReceiptTotal] = useState("");
  const [createExpense, setCreateExpense] = useState(true);

  const sharedItems = items.filter((i) => !i.is_personal);
  const personalItems = items.filter((i) => i.is_personal);

  const handleConfirm = () => {
    const amount = parseFloat(receiptTotal);
    if (createExpense && (isNaN(amount) || amount <= 0)) return;
    onConfirm(createExpense ? amount : 0, createExpense);
  };

  const isValid = !createExpense || (receiptTotal !== "" && parseFloat(receiptTotal) > 0);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Shopping Summary</Text>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>
          Shared items ({sharedItems.length})
        </Text>
        {sharedItems.map((item) => (
          <Text key={item.id} style={styles.itemText}>
            • {item.name}
            {item.quantity ? ` (${item.quantity}${item.unit ? ` ${item.unit}` : ""})` : ""}
          </Text>
        ))}
        {sharedItems.length === 0 && (
          <Text style={styles.emptyText}>No shared items</Text>
        )}
      </View>

      {personalItems.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>
            Personal items ({personalItems.length})
          </Text>
          {personalItems.map((item) => (
            <Text key={item.id} style={styles.itemText}>
              • {item.name} 👤
            </Text>
          ))}
          <Text style={styles.personalNote}>
            Personal items are not included in the shared expense.
          </Text>
        </View>
      )}

      <View style={styles.section}>
        <View style={styles.toggleRow}>
          <Text style={styles.toggleLabel}>Create shared expense</Text>
          <Switch
            value={createExpense}
            onValueChange={setCreateExpense}
            trackColor={{ true: "#10B981" }}
          />
        </View>

        {createExpense && (
          <Input
            label="Receipt total"
            placeholder="0.00"
            value={receiptTotal}
            onChangeText={setReceiptTotal}
            keyboardType="decimal-pad"
          />
        )}
      </View>

      <View style={styles.actions}>
        <Button
          title="Back"
          variant="secondary"
          onPress={onCancel}
          style={styles.actionButton}
        />
        <Button
          title="Confirm"
          onPress={handleConfirm}
          disabled={!isValid}
          loading={isLoading}
          style={styles.actionButton}
        />
      </View>
    </ScrollView>
  );
}
