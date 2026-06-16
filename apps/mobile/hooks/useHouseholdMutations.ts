import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import {
  Household,
  HouseholdSettings,
  HouseholdType,
  MemberRole,
} from "@hausly/types";

interface CreateHouseholdData {
  name: string;
  type: HouseholdType;
}

interface UpdateHouseholdData {
  name?: string;
  type?: HouseholdType;
}

interface UpdateSettingsData {
  enabled_modules?: string[];
  default_currency?: string;
  notification_level?: string;
}

interface RoleChangeData {
  householdId: string;
  userId: string;
  role: MemberRole;
}

interface RemoveMemberData {
  householdId: string;
  userId: string;
}

interface LeaveResponse {
  unsettled_expenses: Array<{ id: string; title: string; amount: number }>;
  pending_chores: Array<{ id: string; name: string; due_date: string }>;
}

interface InvitePreview {
  household_name: string;
  member_count: number;
  type: HouseholdType;
}

export function useCreateHousehold() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateHouseholdData) =>
      api.post<Household>("/households", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["household"] });
    },
  });
}

export function useJoinHousehold() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (inviteCode: string) =>
      api.post<Household>("/households/join", { invite_code: inviteCode }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["household"] });
    },
  });
}

export function useUpdateHousehold(householdId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateHouseholdData) =>
      api.patch<Household>(`/households/${householdId}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["household", householdId] });
    },
  });
}

export function useUpdateSettings(householdId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateSettingsData) =>
      api.patch<HouseholdSettings>(
        `/households/${householdId}/settings`,
        data
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["household", householdId] });
    },
  });
}

export function useChangeRole() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ householdId, userId, role }: RoleChangeData) =>
      api.patch(`/households/${householdId}/members/${userId}/role`, { role }),
    onSuccess: (_, { householdId }) => {
      queryClient.invalidateQueries({ queryKey: ["household", householdId] });
    },
  });
}

export function useRemoveMember() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ householdId, userId }: RemoveMemberData) =>
      api.delete(`/households/${householdId}/members/${userId}`),
    onSuccess: (_, { householdId }) => {
      queryClient.invalidateQueries({ queryKey: ["household", householdId] });
    },
  });
}

export function useLeaveHousehold(householdId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      api.post<LeaveResponse>(`/households/${householdId}/leave`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["household"] });
    },
  });
}

export function useRegenerateInviteCode(householdId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      api.post<{ invite_code: string }>(
        `/households/${householdId}/invite-code/regenerate`
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["household", householdId] });
    },
  });
}

export function usePreviewInvite() {
  return useMutation({
    mutationFn: (code: string) =>
      api.get<InvitePreview>(`/invites/${code}/preview`),
  });
}
