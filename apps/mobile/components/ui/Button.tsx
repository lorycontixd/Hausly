import { Pressable, Text, ActivityIndicator, ViewStyle } from "react-native";
import { styles } from "./Button.styles";
import { colors } from "@/constants/theme";

type ButtonVariant = "primary" | "secondary" | "destructive";
type ButtonSize = "small" | "medium" | "large";

interface ButtonProps {
  title: string;
  onPress: () => void;
  variant?: ButtonVariant;
  size?: ButtonSize;
  disabled?: boolean;
  loading?: boolean;
  style?: ViewStyle;
}

const variantStyles: Record<ButtonVariant, ViewStyle> = {
  primary: styles.primary,
  secondary: styles.secondary,
  destructive: styles.destructive,
};

const textStyleMap: Record<ButtonVariant, object> = {
  primary: styles.textPrimary,
  secondary: styles.textSecondary,
  destructive: styles.textDestructive,
};

export function Button({
  title,
  onPress,
  variant = "primary",
  size = "medium",
  disabled = false,
  loading = false,
  style,
}: ButtonProps) {
  const sizeStyle = size === "medium" ? {} : styles[size];
  const spinnerColor =
    variant === "secondary" ? colors.primary : colors.textInverse;

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      style={[
        styles.base,
        variantStyles[variant],
        sizeStyle,
        (disabled || loading) && styles.disabled,
        style,
      ]}
    >
      {loading && <ActivityIndicator size="small" color={spinnerColor} />}
      <Text style={textStyleMap[variant]}>{title}</Text>
    </Pressable>
  );
}
