import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { logMealSlotClaimed } from "@/services/analytics";
import { MealPlanEntry } from "@hausly/types";

interface MealEntryCreate {
  date: string;
  slot: "lunch" | "dinner";
  text: string;
  headcount?: number;
}

interface MealEntryUpdate {
  text?: string;
  headcount?: number;
}

export function useMealEntries(
  householdId: string | null,
  start: string,
  end: string
) {
  return useQuery({
    queryKey: ["meals", householdId, start, end],
    queryFn: () =>
      api.get<MealPlanEntry[]>(
        `/households/${householdId}/meals?start=${start}&end=${end}`
      ),
    enabled: householdId != null,
  });
}

export function useCreateMeal(householdId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: MealEntryCreate) =>
      api.post<MealPlanEntry>(`/households/${householdId}/meals`, data),
    onSuccess: (_data, variables) => {
      const today = new Date().toISOString().split("T")[0];
      const dayOffset = Math.round(
        (new Date(variables.date).getTime() - new Date(today).getTime()) / 86400000,
      );
      logMealSlotClaimed(variables.slot, dayOffset);
      queryClient.invalidateQueries({ queryKey: ["meals", householdId] });
    },
  });
}

export function useUpdateMeal(householdId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      entryId,
      data,
    }: {
      entryId: string;
      data: MealEntryUpdate;
    }) =>
      api.patch<MealPlanEntry>(
        `/households/${householdId}/meals/${entryId}`,
        data
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["meals", householdId] });
    },
  });
}

export function useDeleteMeal(householdId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (entryId: string) =>
      api.delete(`/households/${householdId}/meals/${entryId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["meals", householdId] });
    },
  });
}
