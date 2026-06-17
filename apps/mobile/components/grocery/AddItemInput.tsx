import { useState } from "react";
import { View, Pressable, Text } from "react-native";
import { Input } from "@/components/ui";
import { styles } from "./AddItemInput.styles";

interface AddItemInputProps {
  onAdd: (name: string, isPersonal: boolean) => void;
}

export function AddItemInput({ onAdd }: AddItemInputProps) {
  const [text, setText] = useState("");
  const [isPersonal, setIsPersonal] = useState(false);

  const handleSubmit = () => {
    if (!text.trim()) return;
    onAdd(text, isPersonal);
    setText("");
  };

  return (
    <View style={styles.container}>
      <View style={styles.inputRow}>
        <View style={styles.inputWrapper}>
          <Input
            placeholder="Add an item..."
            value={text}
            onChangeText={setText}
            onSubmitEditing={handleSubmit}
            returnKeyType="done"
          />
        </View>
        <Pressable
          style={[styles.personalToggle, isPersonal && styles.personalToggleActive]}
          onPress={() => setIsPersonal(!isPersonal)}
        >
          <Text style={styles.personalToggleText}>👤</Text>
        </Pressable>
        <Pressable
          style={[styles.addButton, !text.trim() && styles.addButtonDisabled]}
          onPress={handleSubmit}
          disabled={!text.trim()}
        >
          <Text style={styles.addButtonText}>+</Text>
        </Pressable>
      </View>
    </View>
  );
}
