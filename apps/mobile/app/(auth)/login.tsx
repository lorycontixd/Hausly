import { View, Text, TextInput, Pressable, Platform, ActivityIndicator } from "react-native";
import { StyleSheet } from "react-native";
import { useState } from "react";
import { useAuthContext } from "@/providers/AuthProvider";
import { colors, spacing, borderRadius, typography } from "@/constants/theme";

type Mode = "providers" | "signin" | "signup";

export default function LoginScreen() {
  const { signInGoogle, signInApple, signInEmail, createAccount, error } = useAuthContext();
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<Mode>("providers");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const handleGoogle = async () => {
    setLoading(true);
    await signInGoogle();
    setLoading(false);
  };

  const handleApple = async () => {
    setLoading(true);
    await signInApple();
    setLoading(false);
  };

  const handleEmailSignIn = async () => {
    setLocalError(null);
    if (!email.trim() || !password) {
      setLocalError("Email and password are required");
      return;
    }
    setLoading(true);
    await signInEmail(email.trim(), password);
    setLoading(false);
  };

  const handleEmailSignUp = async () => {
    setLocalError(null);
    if (!email.trim() || !password) {
      setLocalError("Email and password are required");
      return;
    }
    if (password.length < 6) {
      setLocalError("Password must be at least 6 characters");
      return;
    }
    if (password !== confirmPassword) {
      setLocalError("Passwords do not match");
      return;
    }
    setLoading(true);
    await createAccount(email.trim(), password);
    setLoading(false);
  };

  const displayError = localError || error;

  if (mode === "signin" || mode === "signup") {
    const isSignUp = mode === "signup";
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.title}>Hausly</Text>
          <Text style={styles.subtitle}>
            {isSignUp ? "Create your account" : "Sign in with email"}
          </Text>
        </View>

        <View style={styles.form}>
          <TextInput
            style={styles.input}
            placeholder="Email"
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            keyboardType="email-address"
            textContentType="emailAddress"
            autoComplete="email"
          />
          <TextInput
            style={styles.input}
            placeholder="Password"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            textContentType={isSignUp ? "newPassword" : "password"}
            autoComplete={isSignUp ? "new-password" : "current-password"}
          />
          {isSignUp && (
            <TextInput
              style={styles.input}
              placeholder="Confirm password"
              value={confirmPassword}
              onChangeText={setConfirmPassword}
              secureTextEntry
              textContentType="newPassword"
              autoComplete="new-password"
            />
          )}

          <Pressable
            style={[styles.emailButton, loading && styles.disabled]}
            onPress={isSignUp ? handleEmailSignUp : handleEmailSignIn}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.emailButtonText}>
                {isSignUp ? "Create Account" : "Sign In"}
              </Text>
            )}
          </Pressable>

          {displayError && <Text style={styles.error}>{displayError}</Text>}

          <Pressable onPress={() => setMode(isSignUp ? "signin" : "signup")}>
            <Text style={styles.switchText}>
              {isSignUp ? "Already have an account? Sign in" : "Don't have an account? Sign up"}
            </Text>
          </Pressable>

          <Pressable onPress={() => { setMode("providers"); setLocalError(null); }}>
            <Text style={styles.backText}>← Back to sign-in options</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Hausly</Text>
        <Text style={styles.subtitle}>Your shared living companion</Text>
      </View>

      <View style={styles.buttons}>
        <Pressable style={[styles.googleButton, loading && styles.disabled]} onPress={handleGoogle} disabled={loading}>
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.googleButtonText}>Continue with Google</Text>
          )}
        </Pressable>

        {Platform.OS === "ios" && (
          <Pressable style={[styles.appleButton, loading && styles.disabled]} onPress={handleApple} disabled={loading}>
            {loading ? (
              <ActivityIndicator color="#000" />
            ) : (
              <Text style={styles.appleButtonText}>Continue with Apple</Text>
            )}
          </Pressable>
        )}

        <Pressable style={[styles.emailButton, loading && styles.disabled]} onPress={() => setMode("signin")} disabled={loading}>
          <Text style={styles.emailButtonText}>Continue with Email</Text>
        </Pressable>

        {displayError && <Text style={styles.error}>{displayError}</Text>}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.xxl,
    backgroundColor: colors.background,
  },
  header: {
    alignItems: "center",
    marginBottom: 64,
  },
  title: {
    fontSize: 32,
    fontWeight: "700",
    color: colors.text,
    letterSpacing: -0.5,
  },
  subtitle: {
    ...typography.body,
    color: colors.textSecondary,
    marginTop: spacing.sm,
  },
  buttons: {
    width: "100%",
    gap: spacing.md,
  },
  form: {
    width: "100%",
    gap: spacing.md,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: 14,
    fontSize: 16,
    color: colors.text,
    backgroundColor: colors.surface,
  },
  googleButton: {
    backgroundColor: "#4285F4",
    paddingVertical: spacing.lg,
    borderRadius: borderRadius.md,
    alignItems: "center",
  },
  googleButtonText: {
    color: colors.textInverse,
    ...typography.label,
  },
  appleButton: {
    backgroundColor: "#000",
    paddingVertical: spacing.lg,
    borderRadius: borderRadius.md,
    alignItems: "center",
  },
  appleButtonText: {
    color: colors.textInverse,
    ...typography.label,
  },
  emailButton: {
    backgroundColor: colors.primary,
    paddingVertical: spacing.lg,
    borderRadius: borderRadius.md,
    alignItems: "center",
  },
  emailButtonText: {
    color: colors.textInverse,
    ...typography.label,
  },
  switchText: {
    color: colors.primary,
    ...typography.bodySmall,
    textAlign: "center",
    marginTop: spacing.xs,
  },
  backText: {
    color: colors.textSecondary,
    ...typography.bodySmall,
    textAlign: "center",
    marginTop: spacing.xs,
  },
  error: {
    color: colors.error,
    ...typography.bodySmall,
    textAlign: "center",
    marginTop: spacing.sm,
  },
  disabled: {
    opacity: 0.6,
  },
});
