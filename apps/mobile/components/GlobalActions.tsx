import { useState } from "react";
import { Pressable, Text, Alert, View } from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useAuthContext } from "@/providers/AuthProvider";
import { Avatar, Sheet } from "@/components/ui";
import { colors } from "@/constants/theme";
import { styles } from "./GlobalActions.styles";

interface MenuItem {
  icon: string;
  label: string;
  onPress: () => void;
  destructive?: boolean;
}

export function GlobalActions() {
  const [menuVisible, setMenuVisible] = useState(false);
  const router = useRouter();
  const { profile, user, signOut } = useAuthContext();

  const displayName = profile?.display_name || user?.email?.split("@")[0] || "User";

  const handleLogOut = () => {
    setMenuVisible(false);
    Alert.alert("Log Out", "Are you sure you want to log out?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Log Out",
        style: "destructive",
        onPress: () => signOut(),
      },
    ]);
  };

  const menuItems: MenuItem[] = [
    {
      icon: "ℹ️",
      label: "Developer Info",
      onPress: () => {
        setMenuVisible(false);
        router.push("/(modals)/dev-info");
      },
    },
    {
      icon: "📖",
      label: "My Recipes",
      onPress: () => {
        setMenuVisible(false);
        router.push("/(modals)/recipes");
      },
    },
    {
      icon: "⚙️",
      label: "Preferences",
      onPress: () => {
        setMenuVisible(false);
        router.push("/(modals)/preferences");
      },
    },
    {
      icon: "🚪",
      label: "Log Out",
      onPress: handleLogOut,
      destructive: true,
    },
  ];

  return (
    <View style={styles.container}>
      <Pressable
        style={styles.iconButton}
        onPress={() => router.push("/(modals)/profile")}
        accessibilityLabel="Open profile"
      >
        <Avatar name={displayName} size={28} />
      </Pressable>

      <Pressable
        style={styles.iconButton}
        onPress={() => setMenuVisible(true)}
        accessibilityLabel="Open menu"
      >
        <Ionicons
          name="ellipsis-vertical"
          size={20}
          color={colors.textSecondary}
        />
      </Pressable>

      <Sheet visible={menuVisible} onClose={() => setMenuVisible(false)}>
        {menuItems.map((item, index) => (
          <Pressable
            key={item.label}
            style={[
              styles.menuItem,
              index === menuItems.length - 1 && styles.menuItemLast,
            ]}
            onPress={item.onPress}
          >
            <Text style={styles.menuIcon}>{item.icon}</Text>
            <Text
              style={[
                styles.menuLabel,
                item.destructive && styles.menuLabelDestructive,
              ]}
            >
              {item.label}
            </Text>
          </Pressable>
        ))}
      </Sheet>
    </View>
  );
}
