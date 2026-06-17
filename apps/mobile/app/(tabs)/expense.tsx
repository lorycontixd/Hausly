import { useState, useCallback, useMemo } from "react";
import { View, Text, FlatList, Pressable, Alert } from "react-native";
import { useHouseholdStore } from "@/stores/householdStore";
import { useExpenseStore } from "@/stores/expenseStore";
import {
  useExpenses,
  useBalances,
  useSettlements,
  useCreateExpense,
  useConfirmExpense,
  useDeleteExpense,
  useSettleSplit,
} from "@/hooks/useExpenses";
import { useAuthContext } from "@/providers/AuthProvider";
import { Expense, SettlementSuggestion } from "@hausly/types";
import { EmptyState, LoadingSpinner } from "@/components/ui";
import { ExpenseListItem } from "@/components/expense/ExpenseListItem";
import { BalanceSummary } from "@/components/expense/BalanceSummary";
import { SettlementList } from "@/components/expense/SettlementList";
import { CreateExpenseSheet } from "@/components/expense/CreateExpenseSheet";
import { ExpenseDetail } from "@/components/expense/ExpenseDetail";
import { styles } from "@/components/expense/ExpenseScreen.styles";

type TabView = "expenses" | "balances" | "settlements";

export default function ExpenseScreen() {
  const householdId = useHouseholdStore((s) => s.id);
  const members = useHouseholdStore((s) => s.members);
  const settings = useHouseholdStore((s) => s.settings);
  const { profile } = useAuthContext();
  const currentUserId = profile?.user_id ?? "";

  const activeTab = useExpenseStore((s) => s.activeTab);
  const setActiveTab = useExpenseStore((s) => s.setActiveTab);
  const statusFilter = useExpenseStore((s) => s.statusFilter);
  const setStatusFilter = useExpenseStore((s) => s.setStatusFilter);

  const [showCreate, setShowCreate] = useState(false);
  const [selectedExpense, setSelectedExpense] = useState<Expense | null>(null);

  // Queries
  const expenseFilters = useMemo(
    () => (statusFilter === "all" ? {} : { status: statusFilter as "draft" | "confirmed" }),
    [statusFilter]
  );
  const { data: expenses, isLoading: expensesLoading } = useExpenses(
    householdId,
    expenseFilters
  );
  const { data: balancesData } = useBalances(householdId);
  const { data: settlementsData } = useSettlements(householdId);

  // Mutations
  const createExpense = useCreateExpense(householdId);
  const confirmExpense = useConfirmExpense(householdId);
  const deleteExpense = useDeleteExpense(householdId);
  const settleSplit = useSettleSplit(householdId);

  const handleCreateSubmit = useCallback(
    (data: Parameters<typeof createExpense.mutate>[0]) => {
      createExpense.mutate(
        { ...data, source: "manual" },
        {
          onSuccess: () => setShowCreate(false),
          onError: (err) => Alert.alert("Error", err.message),
        }
      );
    },
    [createExpense]
  );

  const handleConfirm = useCallback(() => {
    if (!selectedExpense) return;
    confirmExpense.mutate(selectedExpense.id, {
      onSuccess: () => setSelectedExpense(null),
      onError: (err) => Alert.alert("Error", err.message),
    });
  }, [selectedExpense, confirmExpense]);

  const handleDelete = useCallback(() => {
    if (!selectedExpense) return;
    Alert.alert("Delete Expense", "Are you sure you want to delete this draft?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: () => {
          deleteExpense.mutate(selectedExpense.id, {
            onSuccess: () => setSelectedExpense(null),
            onError: (err) => Alert.alert("Error", err.message),
          });
        },
      },
    ]);
  }, [selectedExpense, deleteExpense]);

  const handleSettle = useCallback(
    (suggestion: SettlementSuggestion) => {
      // Find splits from the debtor that are owed to the creditor
      const relevantExpenses = (expenses ?? []).filter(
        (e) =>
          e.status === "confirmed" &&
          e.paid_by_user_id === suggestion.to_user_id
      );
      const unsettledSplits = relevantExpenses.flatMap((e) =>
        e.splits.filter(
          (s) => s.user_id === suggestion.from_user_id && !s.is_settled
        )
      );

      if (unsettledSplits.length === 0) {
        Alert.alert("Info", "No unsettled splits found for this pair.");
        return;
      }

      Alert.alert(
        "Settle Up",
        `Mark €${suggestion.amount.toFixed(2)} from ${getMemberName(suggestion.from_user_id)} to ${getMemberName(suggestion.to_user_id)} as settled?`,
        [
          { text: "Cancel", style: "cancel" },
          {
            text: "Settle",
            onPress: () => {
              // Settle all relevant splits
              for (const split of unsettledSplits) {
                settleSplit.mutate(split.id);
              }
            },
          },
        ]
      );
    },
    [expenses, settleSplit]
  );

  const getMemberName = useCallback(
    (userId: string) => {
      if (userId === currentUserId) return "You";
      const member = members.find((m) => m.user_id === userId);
      return member?.display_name || member?.email || "Unknown";
    },
    [currentUserId, members]
  );

  const renderExpenseItem = useCallback(
    ({ item }: { item: Expense }) => (
      <ExpenseListItem
        expense={item}
        paidByName={getMemberName(item.paid_by_user_id)}
        onPress={() => setSelectedExpense(item)}
      />
    ),
    [getMemberName]
  );

  const renderTabContent = () => {
    if (activeTab === "balances") {
      return (
        <BalanceSummary
          balances={balancesData?.balances ?? []}
          members={members}
          currentUserId={currentUserId}
        />
      );
    }

    if (activeTab === "settlements") {
      return (
        <SettlementList
          suggestions={settlementsData?.settlements ?? []}
          members={members}
          currentUserId={currentUserId}
          onSettle={handleSettle}
          isSettling={settleSplit.isPending}
        />
      );
    }

    // Expenses tab
    if (expensesLoading) {
      return <LoadingSpinner />;
    }

    if (!expenses || expenses.length === 0) {
      return (
        <EmptyState
          title="No expenses yet"
          message="Tap + to add your first expense"
        />
      );
    }

    return (
      <FlatList
        data={expenses}
        keyExtractor={(item) => item.id}
        renderItem={renderExpenseItem}
        contentContainerStyle={styles.listContent}
      />
    );
  };

  return (
    <View style={styles.container}>
      {/* Tab bar */}
      <View style={styles.tabBar}>
        {(["expenses", "balances", "settlements"] as TabView[]).map((tab) => (
          <Pressable
            key={tab}
            style={[styles.tab, activeTab === tab && styles.tabActive]}
            onPress={() => setActiveTab(tab)}
          >
            <Text
              style={[styles.tabText, activeTab === tab && styles.tabTextActive]}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </Text>
          </Pressable>
        ))}
      </View>

      {/* Filters (expenses tab only) */}
      {activeTab === "expenses" && (
        <View style={styles.filterRow}>
          {(["all", "draft", "confirmed"] as const).map((filter) => (
            <Pressable
              key={filter}
              style={[
                styles.filterChip,
                statusFilter === filter && styles.filterChipActive,
              ]}
              onPress={() => setStatusFilter(filter)}
            >
              <Text
                style={[
                  styles.filterChipText,
                  statusFilter === filter && styles.filterChipTextActive,
                ]}
              >
                {filter.charAt(0).toUpperCase() + filter.slice(1)}
              </Text>
            </Pressable>
          ))}
        </View>
      )}

      {/* Content */}
      {renderTabContent()}

      {/* FAB */}
      {activeTab === "expenses" && (
        <Pressable style={styles.fab} onPress={() => setShowCreate(true)}>
          <Text style={styles.fabText}>+</Text>
        </Pressable>
      )}

      {/* Create sheet */}
      <CreateExpenseSheet
        visible={showCreate}
        onClose={() => setShowCreate(false)}
        members={members}
        currentUserId={currentUserId}
        defaultCurrency={settings?.default_currency ?? "EUR"}
        onSubmit={handleCreateSubmit}
        isSubmitting={createExpense.isPending}
      />

      {/* Detail sheet */}
      <ExpenseDetail
        visible={selectedExpense != null}
        onClose={() => setSelectedExpense(null)}
        expense={selectedExpense}
        members={members}
        currentUserId={currentUserId}
        onConfirm={handleConfirm}
        onDelete={handleDelete}
        isConfirming={confirmExpense.isPending}
        isDeleting={deleteExpense.isPending}
      />
    </View>
  );
}
