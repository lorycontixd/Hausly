import { useState } from "react";
import { View, Text, TextInput, TextInputProps, ViewStyle } from "react-native";
import { styles } from "./Input.styles";
import { colors } from "@/constants/theme";

interface InputProps extends Omit<TextInputProps, "style"> {
  label?: string;
  error?: string;
  style?: ViewStyle;
}

export function Input({ label, error, style, ...inputProps }: InputProps) {
  const [focused, setFocused] = useState(false);

  return (
    <View style={[styles.container, style]}>
      {label && <Text style={styles.label}>{label}</Text>}
      <View
        style={[
          styles.inputContainer,
          focused && styles.inputContainerFocused,
          error != null && styles.inputContainerError,
        ]}
      >
        <TextInput
          style={styles.input}
          placeholderTextColor={colors.textTertiary}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          {...inputProps}
        />
      </View>
      {error != null && <Text style={styles.error}>{error}</Text>}
    </View>
  );
}
