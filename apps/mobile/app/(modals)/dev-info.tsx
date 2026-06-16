import { View, Text, ScrollView, Platform, StyleSheet } from "react-native";
import Constants from "expo-constants";
import { Card } from "@/components/ui";
import { colors, spacing, typography } from "@/constants/theme";

interface InfoRow {
  label: string;
  value: string;
}

export default function DevInfoScreen() {
  const rows: InfoRow[] = [
    {
      label: "App Version",
      value: Constants.expoConfig?.version ?? "—",
    },
    {
      label: "API Version",
      value: "v1",
    },
    {
      label: "Platform",
      value: `${Platform.OS} ${Platform.Version}`,
    },
    {
      label: "Environment",
      value: __DEV__ ? "Development" : "Production",
    },
  ];

  return (
    <ScrollView
      style={styles.scrollView}
      contentContainerStyle={styles.content}
    >
      <Card elevated style={styles.card}>
        {rows.map((row, index) => (
          <View
            key={row.label}
            style={[styles.row, index < rows.length - 1 && styles.rowBorder]}
          >
            <Text style={styles.label}>{row.label}</Text>
            <Text style={styles.value}>{row.value}</Text>
          </View>
        ))}
      </Card>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scrollView: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.lg,
    paddingBottom: spacing.xxxl,
  },
  card: {
    padding: spacing.lg,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.md,
  },
  rowBorder: {
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  label: {
    ...typography.body,
    color: colors.textSecondary,
  },
  value: {
    ...typography.body,
    color: colors.text,
    fontWeight: "500",
  },
});
