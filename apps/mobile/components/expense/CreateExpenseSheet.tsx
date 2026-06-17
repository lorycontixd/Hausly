import { useState, useMemo, useCallback, useEffect } from "react";
import { View, Text, TextInput, Pressable, Alert } from "react-native";
import { HouseholdMember } from "@hausly/types";
import { Sheet, Button, Input } from "@/components/ui";
import { SplitMode } from "@/stores/expenseStore";
import { styles } from "./CreateExpenseSheet.styles";
import { colors } from "@/constants/theme";

interface CreateExpenseSheetProps {
  visible: boolean;
  onClose: () => void;
  members: HouseholdMember[];
  currentUserId: string;
  defaultCurrency: string;
  onSubmit: (data: {
    title: string;
    amount: number;
    currency: string;
    category: string | null;
    paid_by_user_id: string;
    splits: { user_id: string; share_amount: number }[];
    status: "draft" | "confirmed";
  }) => void;
  isSubmitting: boolean;
}

export function CreateExpenseSheet({
  visible,
  onClose,
  members,
  currentUserId,
  defaultCurrency,
  onSubmit,
  isSubmitting,
}: CreateExpenseSheetProps) {
  const [title, setTitle] = useState("");
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("");
  const [paidByUserId, setPaidByUserId] = useState(currentUserId);
  const [splitMode, setSplitMode] = useState<SplitMode>("equal");
  const [participants, setParticipants] = useState<string[]>(
    members.map((m) => m.user_id)
  );
  const [customAmounts, setCustomAmounts] = useState<Record<string, string>>({});
  const [percentages, setPercentages] = useState<Record<string, string>>({});

  // Reset form state whenever sheet opens
  useEffect(() => {
    if (visible) {
      setTitle("");
      setAmount("");
      setCategory("");
      setPaidByUserId(currentUserId);
      setSplitMode("equal");
      setParticipants(members.map((m) => m.user_id));
      setCustomAmounts({});
      setPercentages({});
    }
  }, [visible, currentUserId, members]);

  const parsedAmount = parseFloat(amount) || 0;

  const toggleParticipant = useCallback((userId: string) => {
    setParticipants((prev) =>
      prev.includes(userId)
        ? prev.filter((id) => id !== userId)
        : [...prev, userId]
    );
  }, []);

  const computedSplits = useMemo(() => {
    if (participants.length === 0) return [];

    if (splitMode === "equal") {
      const perPerson = parsedAmount / participants.length;
      const rounded = Math.floor(perPerson * 100) / 100;
      const remainder = parsedAmount - rounded * participants.length;

      return participants.map((userId, index) => ({
        user_id: userId,
        share_amount:
          index === participants.length - 1
            ? Math.round((rounded + remainder) * 100) / 100
            : rounded,
      }));
    }

    if (splitMode === "custom") {
      return participants.map((userId) => ({
        user_id: userId,
        share_amount: parseFloat(customAmounts[userId] ?? "0") || 0,
      }));
    }

    // percentage
    return participants.map((userId) => {
      const pct = parseFloat(percentages[userId] ?? "0") || 0;
      return {
        user_id: userId,
        share_amount: Math.round((parsedAmount * pct) / 100 * 100) / 100,
      };
    });
  }, [splitMode, parsedAmount, participants, customAmounts, percentages]);

  const validationError = useMemo(() => {
    if (!title.trim()) return "Title is required";
    if (parsedAmount <= 0) return "Amount must be greater than 0";
    if (participants.length === 0) return "Select at least one participant";

    if (splitMode === "custom") {
      const total = computedSplits.reduce((sum, s) => sum + s.share_amount, 0);
      if (Math.abs(total - parsedAmount) > 0.01) {
        return `Split total (${total.toFixed(2)}) doesn't match amount (${parsedAmount.toFixed(2)})`;
      }
    }

    if (splitMode === "percentage") {
      const totalPct = participants.reduce(
        (sum, uid) => sum + (parseFloat(percentages[uid] ?? "0") || 0),
        0
      );
      if (Math.abs(totalPct - 100) > 0.01) {
        return `Percentages sum to ${totalPct.toFixed(1)}%, must equal 100%`;
      }
    }

    return null;
  }, [title, parsedAmount, participants, splitMode, computedSplits, percentages]);

  const handleSubmit = useCallback(
    (status: "draft" | "confirmed") => {
      if (validationError) {
        Alert.alert("Validation Error", validationError);
        return;
      }

      onSubmit({
        title: title.trim(),
        amount: parsedAmount,
        currency: defaultCurrency,
        category: category.trim() || null,
        paid_by_user_id: paidByUserId,
        splits: computedSplits,
        status,
      });
    },
    [
      validationError,
      title,
      parsedAmount,
      defaultCurrency,
      category,
      paidByUserId,
      computedSplits,
      onSubmit,
    ]
  );

  const resetForm = useCallback(() => {
    setTitle("");
    setAmount("");
    setCategory("");
    setPaidByUserId(currentUserId);
    setSplitMode("equal");
    setParticipants(members.map((m) => m.user_id));
    setCustomAmounts({});
    setPercentages({});
  }, [currentUserId, members]);

  const handleClose = useCallback(() => {
    resetForm();
    onClose();
  }, [resetForm, onClose]);

  const getMemberName = (userId: string) => {
    if (userId === currentUserId) return "You";
    const member = members.find((m) => m.user_id === userId);
    return member?.display_name || member?.email || "Unknown";
  };

  return (
    <Sheet visible={visible} onClose={handleClose}>
      <View style={styles.container}>
        <Text style={styles.title}>New Expense</Text>

        {/* Amount */}
        <View style={styles.amountRow}>
          <Text style={styles.currencyLabel}>{defaultCurrency}</Text>
          <TextInput
            style={styles.amountInput}
            value={amount}
            onChangeText={setAmount}
            placeholder="0.00"
            placeholderTextColor={colors.textTertiary}
            keyboardType="decimal-pad"
          />
        </View>

        {/* Title */}
        <Input
          label="Title"
          value={title}
          onChangeText={setTitle}
          placeholder="What was this for?"
        />

        {/* Category */}
        <Input
          label="Category"
          value={category}
          onChangeText={setCategory}
          placeholder="food, transport, utilities..."
          style={{ marginTop: 8 }}
        />

        {/* Paid by */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>Paid by</Text>
          <View style={styles.paidByRow}>
            {members.map((member) => (
              <Pressable
                key={member.user_id}
                style={[
                  styles.memberChip,
                  paidByUserId === member.user_id && styles.memberChipActive,
                ]}
                onPress={() => setPaidByUserId(member.user_id)}
              >
                <Text
                  style={[
                    styles.memberChipText,
                    paidByUserId === member.user_id && styles.memberChipTextActive,
                  ]}
                >
                  {getMemberName(member.user_id)}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>

        {/* Participants */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>Split between</Text>
          {members.map((member) => (
            <Pressable
              key={member.user_id}
              style={styles.participantRow}
              onPress={() => toggleParticipant(member.user_id)}
            >
              <View
                style={[
                  styles.participantCheck,
                  participants.includes(member.user_id) && styles.participantCheckActive,
                ]}
              >
                {participants.includes(member.user_id) && (
                  <Text style={styles.checkmark}>✓</Text>
                )}
              </View>
              <Text style={styles.participantName}>
                {getMemberName(member.user_id)}
              </Text>
            </Pressable>
          ))}
        </View>

        {/* Split mode */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>Split mode</Text>
          <View style={styles.splitModeRow}>
            {(["equal", "custom", "percentage"] as SplitMode[]).map((mode) => (
              <Pressable
                key={mode}
                style={[
                  styles.splitModeButton,
                  splitMode === mode && styles.splitModeButtonActive,
                ]}
                onPress={() => setSplitMode(mode)}
              >
                <Text
                  style={[
                    styles.splitModeText,
                    splitMode === mode && styles.splitModeTextActive,
                  ]}
                >
                  {mode.charAt(0).toUpperCase() + mode.slice(1)}
                </Text>
              </Pressable>
            ))}
          </View>

          {/* Split details */}
          {participants.map((userId) => (
            <View key={userId} style={styles.splitRow}>
              <Text style={styles.splitName}>{getMemberName(userId)}</Text>
              {splitMode === "equal" && (
                <Text style={styles.splitEqual}>
                  {parsedAmount > 0
                    ? `${defaultCurrency} ${(parsedAmount / participants.length).toFixed(2)}`
                    : "—"}
                </Text>
              )}
              {splitMode === "custom" && (
                <TextInput
                  style={styles.splitInput}
                  value={customAmounts[userId] ?? ""}
                  onChangeText={(v) =>
                    setCustomAmounts((prev) => ({ ...prev, [userId]: v }))
                  }
                  placeholder="0.00"
                  placeholderTextColor={colors.textTertiary}
                  keyboardType="decimal-pad"
                />
              )}
              {splitMode === "percentage" && (
                <View style={{ flexDirection: "row", alignItems: "center" }}>
                  <TextInput
                    style={styles.splitInput}
                    value={percentages[userId] ?? ""}
                    onChangeText={(v) =>
                      setPercentages((prev) => ({ ...prev, [userId]: v }))
                    }
                    placeholder="0"
                    placeholderTextColor={colors.textTertiary}
                    keyboardType="decimal-pad"
                  />
                  <Text style={styles.splitSuffix}>%</Text>
                </View>
              )}
            </View>
          ))}

          {validationError && splitMode !== "equal" && (
            <Text style={styles.validationError}>{validationError}</Text>
          )}
        </View>

        {/* Actions */}
        <View style={styles.buttonRow}>
          <Button
            title="Save Draft"
            variant="secondary"
            onPress={() => handleSubmit("draft")}
            loading={isSubmitting}
            style={{ flex: 1 }}
          />
          <Button
            title="Confirm"
            variant="primary"
            onPress={() => handleSubmit("confirmed")}
            loading={isSubmitting}
            style={{ flex: 1 }}
          />
        </View>
      </View>
    </Sheet>
  );
}
