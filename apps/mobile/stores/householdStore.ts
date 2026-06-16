import { create } from "zustand";
import { HouseholdSettings, HouseholdMember } from "@hausly/types";

interface HouseholdState {
  id: string | null;
  name: string | null;
  inviteCode: string | null;
  members: HouseholdMember[];
  settings: HouseholdSettings | null;
  setHousehold: (data: {
    id: string;
    name: string;
    inviteCode: string;
    members: HouseholdMember[];
    settings: HouseholdSettings;
  }) => void;
  clear: () => void;
}

export const useHouseholdStore = create<HouseholdState>((set) => ({
  id: null,
  name: null,
  inviteCode: null,
  members: [],
  settings: null,
  setHousehold: (data) =>
    set({
      id: data.id,
      name: data.name,
      inviteCode: data.inviteCode,
      members: data.members,
      settings: data.settings,
    }),
  clear: () =>
    set({
      id: null,
      name: null,
      inviteCode: null,
      members: [],
      settings: null,
    }),
}));
