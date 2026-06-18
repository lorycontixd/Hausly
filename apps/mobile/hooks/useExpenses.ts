import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import {
  Expense,
  ExpenseSplit,
  Balance,
  SettlementSuggestion,
} from "@hausly/types";

// --- Interfaces ---

interface ExpenseCreate {
  title: string;
  amount: number;
  currency: string;
  category?: string | null;
  paid_by_user_id: string;
  splits: SplitInput[];
  status: "draft" | "confirmed";
  source?: "manual";
  is_recurring?: boolean;
  recurrence_rule?: string | null;
  next_occurrence_date?: string | null;
}

interface SplitInput {
  user_id: string;
  share_amount: number;
}

interface ExpenseUpdate {
  title?: string;
  amount?: number;
  currency?: string;
  category?: string | null;
  paid_by_user_id?: string;
  splits?: SplitInput[];
}

interface ExpenseFilters {
  status?: "draft" | "confirmed";
  category?: string;
  cursor?: string;
  limit?: number;
}

interface BalanceResponse {
  balances: Balance[];
}

interface SettlementResponse {
  settlements: SettlementSuggestion[];
}

// --- Query Hooks ---

export function useExpenses(
  householdId: string | null,
  filters?: ExpenseFilters
) {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.category) params.set("category", filters.category);
  if (filters?.cursor) params.set("cursor", filters.cursor);
  if (filters?.limit) params.set("limit", String(filters.limit));
  const query = params.toString();

  return useQuery({
    queryKey: ["expenses", householdId, filters],
    queryFn: () =>
      api.get<Expense[]>(
        `/households/${householdId}/expenses${query ? `?${query}` : ""}`
      ),
    enabled: householdId != null,
  });
}

export function useExpense(householdId: string | null, expenseId: string | null) {
  return useQuery({
    queryKey: ["expenses", householdId, expenseId],
    queryFn: () =>
      api.get<Expense>(`/households/${householdId}/expenses/${expenseId}`),
    enabled: householdId != null && expenseId != null,
  });
}

export function useBalances(householdId: string | null) {
  return useQuery({
    queryKey: ["expenses", "balances", householdId],
    queryFn: () =>
      api.get<BalanceResponse>(
        `/households/${householdId}/expenses/balances`
      ),
    enabled: householdId != null,
  });
}

export function useSettlements(householdId: string | null) {
  return useQuery({
    queryKey: ["expenses", "settlements", householdId],
    queryFn: () =>
      api.get<SettlementResponse>(
        `/households/${householdId}/expenses/settlements`
      ),
    enabled: householdId != null,
  });
}

// --- Mutation Hooks ---

export function useCreateExpense(householdId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ExpenseCreate) =>
      api.post<Expense>(`/households/${householdId}/expenses`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["expenses", householdId],
      });
      queryClient.invalidateQueries({
        queryKey: ["expenses", "balances", householdId],
      });
    },
  });
}

export function useUpdateExpense(householdId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      expenseId,
      data,
    }: {
      expenseId: string;
      data: ExpenseUpdate;
    }) =>
      api.patch<Expense>(
        `/households/${householdId}/expenses/${expenseId}`,
        data
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["expenses", householdId],
      });
    },
  });
}

export function useConfirmExpense(householdId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (expenseId: string) =>
      api.post<Expense>(
        `/households/${householdId}/expenses/${expenseId}/confirm`
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["expenses", householdId],
      });
      queryClient.invalidateQueries({
        queryKey: ["expenses", "balances", householdId],
      });
      queryClient.invalidateQueries({
        queryKey: ["expenses", "settlements", householdId],
      });
    },
  });
}

export function useDeleteExpense(householdId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (expenseId: string) =>
      api.delete(`/households/${householdId}/expenses/${expenseId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["expenses", householdId],
      });
      queryClient.invalidateQueries({
        queryKey: ["expenses", "balances", householdId],
      });
    },
  });
}

export function useSettleSplit(householdId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (splitId: string) =>
      api.post<ExpenseSplit>(
        `/households/${householdId}/expenses/splits/${splitId}/settle`
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["expenses", householdId],
      });
      queryClient.invalidateQueries({
        queryKey: ["expenses", "balances", householdId],
      });
      queryClient.invalidateQueries({
        queryKey: ["expenses", "settlements", householdId],
      });
    },
  });
}
