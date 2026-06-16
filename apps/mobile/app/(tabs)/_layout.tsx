import { Tabs } from "expo-router";
import { Text } from "react-native";
import { useHouseholdStore } from "@/stores/householdStore";
import { useHousehold } from "@/hooks/useHousehold";
import { GlobalActions } from "@/components/GlobalActions";
import { ModuleName } from "@hausly/types";
import { colors } from "@/constants/theme";

interface TabConfig {
  name: string;
  title: string;
  icon: string;
  module?: ModuleName;
}

const TAB_CONFIG: TabConfig[] = [
  { name: "index", title: "Home", icon: "🏠" },
  { name: "grocery", title: "Grocery", icon: "🛒", module: "grocery" },
  { name: "expense", title: "Expenses", icon: "💰", module: "expense" },
  { name: "meal", title: "Meals", icon: "🍽️", module: "meal" },
  { name: "chores", title: "Chores", icon: "✅", module: "chores" },
  { name: "settings", title: "Settings", icon: "⚙️" },
];

export default function TabsLayout() {
  useHousehold(); // Fetch household data and populate store on tab mount
  const enabledModules = useHouseholdStore((s) => s.settings?.enabled_modules);

  return (
    <Tabs
      screenOptions={{
        headerShown: true,
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textTertiary,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
        },
        headerStyle: {
          backgroundColor: colors.background,
        },
        headerTintColor: colors.text,
        headerTitleStyle: {
          fontWeight: "600",
        },
        headerRight: () => <GlobalActions />,
      }}
    >
      {TAB_CONFIG.map((tab) => {
        const isHidden =
          tab.module != null &&
          enabledModules != null &&
          !enabledModules.includes(tab.module);

        return (
          <Tabs.Screen
            key={tab.name}
            name={tab.name}
            options={{
              title: tab.title,
              href: isHidden ? null : undefined,
              headerShown: tab.name !== "settings",
              tabBarIcon: ({ color }) => (
                <Text style={{ fontSize: 20, color }}>{tab.icon}</Text>
              ),
            }}
          />
        );
      })}
    </Tabs>
  );
}
