import { useEffect } from "react";
import { Stack, useRouter, useSegments } from "expo-router";
import { ActivityIndicator, View } from "react-native";
import { QueryProvider } from "@/providers/QueryProvider";
import { AuthProvider, useAuthContext } from "@/providers/AuthProvider";

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { status, hasHousehold } = useAuthContext();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (status === "loading") return;

    const inAuthGroup = segments[0] === "(auth)";

    if (status === "unauthenticated" && !inAuthGroup) {
      router.replace("/(auth)/login");
    } else if (status === "authenticated" && inAuthGroup) {
      if (hasHousehold) {
        router.replace("/(tabs)");
      } else {
        router.replace("/(auth)/onboarding");
      }
    }
  }, [status, hasHousehold, segments, router]);

  if (status === "loading") {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  return <>{children}</>;
}

export default function RootLayout() {
  return (
    <QueryProvider>
      <AuthProvider>
        <AuthGuard>
          <Stack screenOptions={{ headerShown: false }} />
        </AuthGuard>
      </AuthProvider>
    </QueryProvider>
  );
}
