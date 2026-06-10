import { Redirect } from "expo-router";

// Firebase handles both sign-in and registration in the same flow.
// Redirect to the login screen which has Google/Apple sign-in buttons.
export default function RegisterScreen() {
  return <Redirect href="/(auth)/login" />;
}
