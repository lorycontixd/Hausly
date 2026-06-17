import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { GroceryItem } from "@hausly/types";

interface GroceryList {
  id: string;
  household_id: string;
  name: string;
  is_active: boolean;
  created_at: string;
  archived_at: string | null;
}

interface GroceryItemCreate {
  name: string;
  quantity?: number | null;
  unit?: string | null;
  is_personal?: boolean;
  personal_visibility?: "visible" | "hidden";
}

interface GroceryItemUpdate {
  name?: string;
  quantity?: number | null;
  unit?: string | null;
  is_personal?: boolean;
  personal_visibility?: "visible" | "hidden";
}

interface SessionCompleteRequest {
  bought_item_ids: string[];
  receipt_total: number;
  create_expense: boolean;
}

interface SessionCompleteResponse {
  items_removed: number;
  expense_draft_id: string | null;
  expense_draft: unknown | null;
}

export function useGroceryItems(householdId: string | null) {
  return useQuery({
    queryKey: ["grocery", "items", householdId],
    queryFn: async () => {
      const lists = await api.get<GroceryList[]>(
        `/households/${householdId}/grocery/lists`
      );
      const activeList = lists.find((l) => l.is_active);
      if (!activeList) return [];
      return api.get<GroceryItem[]>(
        `/households/${householdId}/grocery/lists/${activeList.id}/items`
      );
    },
    enabled: householdId != null,
  });
}

export function useAddGroceryItem(householdId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: GroceryItemCreate) =>
      api.post<GroceryItem[]>(
        `/households/${householdId}/grocery/items`,
        [data]
      ),
    onMutate: async (newItem) => {
      await queryClient.cancelQueries({
        queryKey: ["grocery", "items", householdId],
      });
      const queries = queryClient.getQueriesData<GroceryItem[]>({
        queryKey: ["grocery", "items", householdId],
      });
      // Optimistically add to all matching item queries
      for (const [key] of queries) {
        queryClient.setQueryData<GroceryItem[]>(key, (old) => [
          ...(old ?? []),
          {
            id: `temp-${Date.now()}`,
            name: newItem.name,
            quantity: newItem.quantity ?? null,
            unit: newItem.unit ?? null,
            is_bought: false,
            added_by_user_id: "",
            source: "manual",
            is_personal: newItem.is_personal ?? false,
            personal_for_user_id: null,
            personal_visibility: newItem.personal_visibility ?? "visible",
            created_at: new Date().toISOString(),
          },
        ]);
      }
      return { queries };
    },
    onError: (_err, _newItem, context) => {
      if (context?.queries) {
        for (const [key, data] of context.queries) {
          queryClient.setQueryData(key, data);
        }
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: ["grocery", "items", householdId],
      });
    },
  });
}

export function useUpdateGroceryItem(householdId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, data }: { itemId: string; data: GroceryItemUpdate }) =>
      api.patch<GroceryItem>(
        `/households/${householdId}/grocery/items/${itemId}`,
        data
      ),
    onMutate: async ({ itemId, data }) => {
      await queryClient.cancelQueries({
        queryKey: ["grocery", "items", householdId],
      });
      const queries = queryClient.getQueriesData<GroceryItem[]>({
        queryKey: ["grocery", "items", householdId],
      });
      for (const [key] of queries) {
        queryClient.setQueryData<GroceryItem[]>(key, (old) =>
          old?.map((item) =>
            item.id === itemId ? { ...item, ...data } : item
          )
        );
      }
      return { queries };
    },
    onError: (_err, _vars, context) => {
      if (context?.queries) {
        for (const [key, data] of context.queries) {
          queryClient.setQueryData(key, data);
        }
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: ["grocery", "items", householdId],
      });
    },
  });
}

export function useDeleteGroceryItem(householdId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (itemId: string) =>
      api.delete(`/households/${householdId}/grocery/items/${itemId}`),
    onMutate: async (itemId) => {
      await queryClient.cancelQueries({
        queryKey: ["grocery", "items", householdId],
      });
      const queries = queryClient.getQueriesData<GroceryItem[]>({
        queryKey: ["grocery", "items", householdId],
      });
      for (const [key] of queries) {
        queryClient.setQueryData<GroceryItem[]>(key, (old) =>
          old?.filter((item) => item.id !== itemId)
        );
      }
      return { queries };
    },
    onError: (_err, _itemId, context) => {
      if (context?.queries) {
        for (const [key, data] of context.queries) {
          queryClient.setQueryData(key, data);
        }
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: ["grocery", "items", householdId],
      });
    },
  });
}

export function useCompleteSession(householdId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: SessionCompleteRequest) =>
      api.post<SessionCompleteResponse>(
        `/households/${householdId}/grocery/session/complete`,
        data
      ),
    onSuccess: () => {
      queryClient.resetQueries({
        queryKey: ["grocery", "items", householdId],
      });
      queryClient.invalidateQueries({
        queryKey: ["expenses", householdId],
      });
    },
  });
}

export function useArchiveGroceryList(householdId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      api.post(`/households/${householdId}/grocery/lists/archive`, {
        confirm: true,
      }),
    onSuccess: () => {
      queryClient.resetQueries({
        queryKey: ["grocery", "items", householdId],
      });
    },
  });
}
