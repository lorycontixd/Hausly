import { Stack } from "expo-router";
import { GlobalActions } from "@/components/GlobalActions";
import { colors } from "@/constants/theme";

export default function SettingsLayout() {
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: colors.background },
        headerTintColor: colors.text,
        headerTitleStyle: { fontWeight: "600" },
        headerRight: () => <GlobalActions />,
      }}
    >
      <Stack.Screen name="index" options={{ title: "Settings" }} />
      <Stack.Screen name="member" options={{ title: "Manage Member" }} />
      <Stack.Screen name="leave" options={{ title: "Leave Household" }} />
    </Stack>
  );
}
