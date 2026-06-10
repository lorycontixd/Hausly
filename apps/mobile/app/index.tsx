import { Redirect } from "expo-router";
import { useAuthContext } from "@/providers/AuthProvider";

export default function Index() {
  const { status, hasHousehold } = useAuthContext();

  if (status === "unauthenticated") {
    return <Redirect href="/(auth)/login" />;
  }

  if (status === "authenticated" && !hasHousehold) {
    return <Redirect href="/(auth)/onboarding" />;
  }

  return <Redirect href="/(tabs)" />;
}
