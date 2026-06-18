import { useState } from "react";
import { View, Text } from "react-native";
import { Sheet, Input, Button } from "@/components/ui";
import { StyleSheet } from "react-native";
import { colors, spacing, typography } from "@/constants/theme";

interface PostponeSheetProps {
  visible: boolean;
  onClose: () => void;
  onConfirm: (date: string) => void;
}

export function PostponeSheet({ visible, onClose, onConfirm }: PostponeSheetProps) {
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const [date, setDate] = useState(tomorrow.toISOString().split("T")[0]);

  const handleConfirm = () => {
    if (!date) return;
    onConfirm(date);
    onClose();
  };

  return (
    <Sheet visible={visible} onClose={onClose}>
      <View style={sheetStyles.content}>
        <Text style={sheetStyles.title}>Postpone to</Text>
        <Input
          value={date}
          onChangeText={setDate}
          placeholder="YYYY-MM-DD"
        />
        <Button title="Confirm" onPress={handleConfirm} variant="primary" />
      </View>
    </Sheet>
  );
}

const sheetStyles = StyleSheet.create({
  content: {
    padding: spacing.lg,
    gap: spacing.lg,
  },
  title: {
    ...typography.subheading,
    color: colors.text,
  },
});
