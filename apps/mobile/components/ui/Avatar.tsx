import { View, Image, Text } from "react-native";
import { styles } from "./Avatar.styles";

interface AvatarProps {
  uri?: string | null;
  name: string;
  size?: number;
}

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

export function Avatar({ uri, name, size = 40 }: AvatarProps) {
  const sizeStyle = { width: size, height: size };

  if (uri) {
    return (
      <View style={[styles.container, sizeStyle]}>
        <Image source={{ uri }} style={styles.image} />
      </View>
    );
  }

  return (
    <View style={[styles.container, styles.fallback, sizeStyle]}>
      <Text style={[styles.initials, size > 40 && styles.initialsLarge]}>
        {getInitials(name)}
      </Text>
    </View>
  );
}
