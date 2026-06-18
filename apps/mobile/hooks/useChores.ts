import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { logChoreCompleted } from "@/services/analytics";
import { Chore, ChoreAssignment } from "@hausly/types";

// --- Interfaces ---

interface ChoreCreate {
  name: string;
  start_date: string;
  is_recurring: boolean;
  recurrence_interval?: number | null;
  recurrence_unit?: "days" | "weeks" | "months" | null;
  assignee_user_ids: string[];
  rotation_enabled: boolean;
}

interface ChoreUpdate {
  name?: string;
  is_recurring?: boolean;
  recurrence_interval?: number | null;
  recurrence_unit?: "days" | "weeks" | "months" | null;
  assignee_user_ids?: string[];
  rotation_enabled?: boolean;
}

interface AssignmentFilters {
  status?: "pending" | "completed" | "cancelled";
  user_id?: string;
  start_date?: string;
  end_date?: string;
}

// --- Query Hooks ---

export function useChores(householdId: string | null) {
  return useQuery({
    queryKey: ["chores", householdId],
    queryFn: () =>
      api.get<Chore[]>(`/households/${householdId}/chores`),
    enabled: householdId != null,
  });
}

export function useChore(householdId: string | null, choreId: string | null) {
  return useQuery({
    queryKey: ["chores", householdId, choreId],
    queryFn: () =>
      api.get<Chore>(`/households/${householdId}/chores/${choreId}`),
    enabled: householdId != null && choreId != null,
  });
}

export function useAssignments(
  householdId: string | null,
  filters?: AssignmentFilters
) {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.user_id) params.set("user_id", filters.user_id);
  if (filters?.start_date) params.set("start_date", filters.start_date);
  if (filters?.end_date) params.set("end_date", filters.end_date);
  const query = params.toString();

  return useQuery({
    queryKey: ["chores", "assignments", householdId, filters],
    queryFn: () =>
      api.get<ChoreAssignment[]>(
        `/households/${householdId}/chores/assignments${query ? `?${query}` : ""}`
      ),
    enabled: householdId != null,
  });
}

// --- Mutation Hooks ---

export function useCreateChore(householdId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ChoreCreate) =>
      api.post<Chore>(`/households/${householdId}/chores`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chores", householdId] });
      queryClient.invalidateQueries({
        queryKey: ["chores", "assignments", householdId],
      });
    },
  });
}

export function useUpdateChore(householdId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ choreId, data }: { choreId: string; data: ChoreUpdate }) =>
      api.patch<Chore>(
        `/households/${householdId}/chores/${choreId}`,
        data
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chores", householdId] });
      queryClient.invalidateQueries({
        queryKey: ["chores", "assignments", householdId],
      });
    },
  });
}

export function useDeleteChore(householdId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (choreId: string) =>
      api.delete(`/households/${householdId}/chores/${choreId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chores", householdId] });
      queryClient.invalidateQueries({
        queryKey: ["chores", "assignments", householdId],
      });
    },
  });
}

export function useCompleteAssignment(householdId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assignmentId: string) =>
      api.post<ChoreAssignment>(
        `/households/${householdId}/chores/assignments/${assignmentId}/complete`
      ),
    onSuccess: () => {
      logChoreCompleted(true, 0);
      queryClient.invalidateQueries({
        queryKey: ["chores", "assignments", householdId],
      });
    },
  });
}

export function usePostponeAssignment(householdId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      assignmentId,
      postponeTo,
    }: {
      assignmentId: string;
      postponeTo: string;
    }) =>
      api.post<ChoreAssignment>(
        `/households/${householdId}/chores/assignments/${assignmentId}/postpone`,
        { postpone_to: postponeTo }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["chores", "assignments", householdId],
      });
    },
  });
}

export function useCancelAssignment(householdId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assignmentId: string) =>
      api.post<ChoreAssignment>(
        `/households/${householdId}/chores/assignments/${assignmentId}/cancel`
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["chores", "assignments", householdId],
      });
    },
  });
}
