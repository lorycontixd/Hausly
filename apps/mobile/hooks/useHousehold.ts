import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useHouseholdStore } from "@/stores/householdStore";
import { useAuthContext } from "@/providers/AuthProvider";
import { Household } from "@hausly/types";

export function useHousehold() {
  const { profile } = useAuthContext();
  const householdMembership = profile?.households?.[0];
  const householdId = householdMembership?.id ?? null;
  const setHousehold = useHouseholdStore((s) => s.setHousehold);
  const clear = useHouseholdStore((s) => s.clear);

  const query = useQuery({
    queryKey: ["household", householdId],
    queryFn: () => api.get<Household>(`/households/${householdId}`),
    enabled: householdId != null,
  });

  useEffect(() => {
    if (query.data) {
      setHousehold({
        id: query.data.id,
        name: query.data.name,
        inviteCode: query.data.invite_code,
        members: query.data.members,
        settings: query.data.settings,
      });
    } else if (!householdId) {
      clear();
    }
  }, [query.data, householdId, setHousehold, clear]);

  return {
    household: query.data ?? null,
    householdId,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}
