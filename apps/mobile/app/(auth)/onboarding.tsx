import {
  View,
  Text,
  Pressable,
  ScrollView,
} from "react-native";
import { StyleSheet } from "react-native";
import { useState } from "react";
import { useRouter } from "expo-router";
import { useAuthContext } from "@/providers/AuthProvider";
import { useCreateHousehold, useJoinHousehold, usePreviewInvite } from "@/hooks/useHouseholdMutations";
import { Input, Button, Card } from "@/components/ui";
import { colors, spacing, borderRadius, typography } from "@/constants/theme";
import { HouseholdType } from "@hausly/types";

type Step = "choice" | "create-name" | "create-type" | "join" | "join-preview";

const HOUSEHOLD_TYPES: { value: HouseholdType; label: string; emoji: string }[] = [
  { value: "couple", label: "Couple", emoji: "💑" },
  { value: "friends", label: "Friends", emoji: "👫" },
  { value: "students", label: "Students", emoji: "🎓" },
  { value: "family", label: "Family", emoji: "👨‍👩‍👧‍👦" },
  { value: "custom", label: "Other", emoji: "🏠" },
];

export default function OnboardingScreen() {
  const router = useRouter();
  const { profile, refreshProfile } = useAuthContext();
  const [step, setStep] = useState<Step>("choice");
  const [name, setName] = useState("");
  const [householdType, setHouseholdType] = useState<HouseholdType>("couple");
  const [inviteCode, setInviteCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  const createMutation = useCreateHousehold();
  const joinMutation = useJoinHousehold();
  const previewMutation = usePreviewInvite();

  const handleCreate = async () => {
    if (!name.trim()) return;
    setError(null);
    try {
      await createMutation.mutateAsync({ name: name.trim(), type: householdType });
      await refreshProfile();
      router.replace("/(tabs)");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create household");
    }
  };

  const handlePreviewInvite = async () => {
    if (!inviteCode.trim()) return;
    setError(null);
    try {
      await previewMutation.mutateAsync(inviteCode.trim());
      setStep("join-preview");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Invalid invite code");
    }
  };

  const handleJoin = async () => {
    setError(null);
    try {
      await joinMutation.mutateAsync(inviteCode.trim());
      await refreshProfile();
      router.replace("/(tabs)");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to join household");
    }
  };

  if (step === "choice") {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>
          Welcome{profile?.display_name ? `, ${profile.display_name}` : ""}!
        </Text>
        <Text style={styles.subtitle}>Let&apos;s set up your household</Text>

        <View style={styles.buttons}>
          <Button
            title="Create a new household"
            onPress={() => setStep("create-name")}
            size="large"
          />
          <Button
            title="Join with invite code"
            onPress={() => setStep("join")}
            variant="secondary"
            size="large"
          />
        </View>
      </View>
    );
  }

  if (step === "create-name") {
    return (
      <View style={styles.container}>
        <Pressable onPress={() => setStep("choice")}>
          <Text style={styles.back}>← Back</Text>
        </Pressable>
        <Text style={styles.title}>Name your household</Text>
        <Text style={styles.subtitle}>Choose a name everyone will recognize</Text>

        <Input
          placeholder="e.g. The Apartment"
          value={name}
          onChangeText={setName}
          autoFocus
        />

        <Button
          title="Next"
          onPress={() => setStep("create-type")}
          disabled={!name.trim()}
          size="large"
          style={styles.actionButton}
        />
      </View>
    );
  }

  if (step === "create-type") {
    return (
      <ScrollView contentContainerStyle={styles.container}>
        <Pressable onPress={() => setStep("create-name")}>
          <Text style={styles.back}>← Back</Text>
        </Pressable>
        <Text style={styles.title}>What kind of household?</Text>
        <Text style={styles.subtitle}>
          This helps us set up smart defaults for your modules
        </Text>

        <View style={styles.typeGrid}>
          {HOUSEHOLD_TYPES.map((ht) => (
            <Pressable
              key={ht.value}
              style={[
                styles.typeCard,
                householdType === ht.value && styles.typeCardSelected,
              ]}
              onPress={() => setHouseholdType(ht.value)}
            >
              <Text style={styles.typeEmoji}>{ht.emoji}</Text>
              <Text
                style={[
                  styles.typeLabel,
                  householdType === ht.value && styles.typeLabelSelected,
                ]}
              >
                {ht.label}
              </Text>
            </Pressable>
          ))}
        </View>

        <Button
          title="Create Household"
          onPress={handleCreate}
          loading={createMutation.isPending}
          disabled={!name.trim()}
          size="large"
          style={styles.actionButton}
        />

        {error && <Text style={styles.error}>{error}</Text>}
      </ScrollView>
    );
  }

  if (step === "join") {
    return (
      <View style={styles.container}>
        <Pressable onPress={() => setStep("choice")}>
          <Text style={styles.back}>← Back</Text>
        </Pressable>
        <Text style={styles.title}>Join a household</Text>
        <Text style={styles.subtitle}>
          Enter the invite code shared by your household admin
        </Text>

        <Input
          placeholder="Enter invite code"
          value={inviteCode}
          onChangeText={setInviteCode}
          autoCapitalize="characters"
          autoFocus
        />

        <Button
          title="Preview"
          onPress={handlePreviewInvite}
          loading={previewMutation.isPending}
          disabled={!inviteCode.trim()}
          size="large"
          style={styles.actionButton}
        />

        {error && <Text style={styles.error}>{error}</Text>}
      </View>
    );
  }

  // step === "join-preview"
  const preview = previewMutation.data;
  return (
    <View style={styles.container}>
      <Pressable onPress={() => setStep("join")}>
        <Text style={styles.back}>← Back</Text>
      </Pressable>
      <Text style={styles.title}>Join this household?</Text>

      <Card elevated style={styles.previewCard}>
        <Text style={styles.previewName}>{preview?.household_name}</Text>
        <Text style={styles.previewMeta}>
          {preview?.type} · {preview?.member_count}{" "}
          {preview?.member_count === 1 ? "member" : "members"}
        </Text>
      </Card>

      <Button
        title="Join Household"
        onPress={handleJoin}
        loading={joinMutation.isPending}
        size="large"
        style={styles.actionButton}
      />

      {error && <Text style={styles.error}>{error}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    padding: spacing.xxl,
    backgroundColor: colors.background,
  },
  title: {
    ...typography.heading,
    fontSize: 28,
    color: colors.text,
    marginBottom: spacing.sm,
  },
  subtitle: {
    ...typography.body,
    color: colors.textSecondary,
    marginBottom: spacing.xxxl,
  },
  buttons: {
    gap: spacing.md,
  },
  back: {
    ...typography.body,
    color: colors.primary,
    marginBottom: spacing.xxl,
  },
  actionButton: {
    marginTop: spacing.lg,
  },
  typeGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.md,
    marginBottom: spacing.xxl,
  },
  typeCard: {
    width: "47%",
    paddingVertical: spacing.xl,
    paddingHorizontal: spacing.lg,
    borderRadius: borderRadius.md,
    borderWidth: 2,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: "center",
    gap: spacing.sm,
  },
  typeCardSelected: {
    borderColor: colors.primary,
    backgroundColor: colors.primarySoft,
  },
  typeEmoji: {
    fontSize: 28,
  },
  typeLabel: {
    ...typography.label,
    color: colors.textSecondary,
  },
  typeLabelSelected: {
    color: colors.primary,
  },
  previewCard: {
    padding: spacing.xl,
    marginBottom: spacing.lg,
    alignItems: "center",
  },
  previewName: {
    ...typography.subheading,
    color: colors.text,
    marginBottom: spacing.xs,
  },
  previewMeta: {
    ...typography.bodySmall,
    color: colors.textSecondary,
    textTransform: "capitalize",
  },
  error: {
    color: colors.error,
    ...typography.bodySmall,
    textAlign: "center",
    marginTop: spacing.md,
  },
});
