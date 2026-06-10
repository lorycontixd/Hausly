import { View, Text, TextInput, Pressable, ActivityIndicator } from "react-native";
import { StyleSheet } from "react-native";
import { useState } from "react";
import { useRouter } from "expo-router";
import { api, VerifyResponse } from "@/services/api";
import { useAuthContext } from "@/providers/AuthProvider";

type Step = "choice" | "create" | "join";

interface HouseholdCreateResponse {
  id: string;
  name: string;
  invite_code: string;
}

export default function OnboardingScreen() {
  const router = useRouter();
  const { profile } = useAuthContext();
  const [step, setStep] = useState<Step>("choice");
  const [name, setName] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!name.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await api.post<HouseholdCreateResponse>("/households", {
        name: name.trim(),
        type: "couple",
      });
      router.replace("/(tabs)");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create household");
    } finally {
      setLoading(false);
    }
  };

  const handleJoin = async () => {
    if (!inviteCode.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await api.post("/households/join", { invite_code: inviteCode.trim() });
      router.replace("/(tabs)");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to join household");
    } finally {
      setLoading(false);
    }
  };

  if (step === "choice") {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>Welcome{profile?.display_name ? `, ${profile.display_name}` : ""}!</Text>
        <Text style={styles.subtitle}>Let&apos;s set up your household</Text>

        <View style={styles.buttons}>
          <Pressable style={styles.primaryButton} onPress={() => setStep("create")}>
            <Text style={styles.primaryButtonText}>Create a new household</Text>
          </Pressable>

          <Pressable style={styles.secondaryButton} onPress={() => setStep("join")}>
            <Text style={styles.secondaryButtonText}>Join with invite code</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  if (step === "create") {
    return (
      <View style={styles.container}>
        <Pressable onPress={() => setStep("choice")}>
          <Text style={styles.back}>← Back</Text>
        </Pressable>
        <Text style={styles.title}>Name your household</Text>

        <TextInput
          style={styles.input}
          placeholder="e.g. The Apartment"
          value={name}
          onChangeText={setName}
          autoFocus
        />

        <Pressable
          style={[styles.primaryButton, !name.trim() && styles.disabled]}
          onPress={handleCreate}
          disabled={loading || !name.trim()}
        >
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.primaryButtonText}>Create</Text>
          )}
        </Pressable>

        {error && <Text style={styles.error}>{error}</Text>}
      </View>
    );
  }

  // step === "join"
  return (
    <View style={styles.container}>
      <Pressable onPress={() => setStep("choice")}>
        <Text style={styles.back}>← Back</Text>
      </Pressable>
      <Text style={styles.title}>Join a household</Text>

      <TextInput
        style={styles.input}
        placeholder="Enter invite code"
        value={inviteCode}
        onChangeText={setInviteCode}
        autoCapitalize="characters"
        autoFocus
      />

      <Pressable
        style={[styles.primaryButton, !inviteCode.trim() && styles.disabled]}
        onPress={handleJoin}
        disabled={loading || !inviteCode.trim()}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.primaryButtonText}>Join</Text>
        )}
      </Pressable>

      {error && <Text style={styles.error}>{error}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    padding: 24,
    backgroundColor: "#fff",
  },
  title: {
    fontSize: 28,
    fontWeight: "700",
    color: "#1a1a1a",
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: "#666",
    marginBottom: 48,
  },
  buttons: {
    gap: 12,
  },
  primaryButton: {
    backgroundColor: "#4F46E5",
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: "center",
  },
  primaryButtonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
  },
  secondaryButton: {
    borderWidth: 2,
    borderColor: "#4F46E5",
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: "center",
  },
  secondaryButtonText: {
    color: "#4F46E5",
    fontSize: 16,
    fontWeight: "600",
  },
  input: {
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 16,
    marginBottom: 16,
  },
  back: {
    fontSize: 16,
    color: "#4F46E5",
    marginBottom: 24,
  },
  disabled: {
    opacity: 0.5,
  },
  error: {
    color: "#dc2626",
    fontSize: 14,
    textAlign: "center",
    marginTop: 12,
  },
});
