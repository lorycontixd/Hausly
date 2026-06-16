import { View, ViewStyle } from "react-native";
import { styles } from "./Card.styles";

interface CardProps {
  children: React.ReactNode;
  elevated?: boolean;
  style?: ViewStyle;
}

export function Card({ children, elevated = false, style }: CardProps) {
  return (
    <View style={[styles.container, elevated && styles.shadow, style]}>
      {children}
    </View>
  );
}
