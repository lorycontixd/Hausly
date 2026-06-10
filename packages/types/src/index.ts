/**
 * Hausly Shared Types
 *
 * These types are the single source of truth for API contracts.
 * Generated from the FastAPI OpenAPI schema once the backend is implemented.
 */

// --- Enums ---

export type HouseholdType = "couple" | "friends" | "students" | "family" | "custom";
export type MemberRole = "admin" | "member";
export type SubscriptionTier = "free" | "paid";
export type NotificationLevel = "low" | "medium" | "high";
export type MealSlot = "lunch" | "dinner";
export type ExpenseStatus = "draft" | "confirmed";
export type ExpenseSource = "manual" | "grocery_integration" | "recurring_auto";
export type GroceryItemSource = "manual" | "meal_plan" | "ai_suggestion";
export type PersonalVisibility = "visible" | "hidden";
export type RecurrenceUnit = "days" | "weeks" | "months";
export type ChoreAssignmentStatus = "pending" | "completed" | "cancelled";
export type ModuleName = "grocery" | "expense" | "meal" | "chores" | "pinboard";

// --- Core Entities ---

export interface User {
  id: string;
  display_name: string;
  email: string;
  avatar_url: string | null;
}

export interface HouseholdMember {
  user_id: string;
  display_name: string;
  role: MemberRole;
  joined_at: string;
}

export interface Household {
  id: string;
  name: string;
  type: HouseholdType;
  invite_code: string;
  subscription_tier: SubscriptionTier;
  members: HouseholdMember[];
  settings: HouseholdSettings;
}

export interface HouseholdSettings {
  default_currency: string;
  enabled_modules: ModuleName[];
  notification_level: NotificationLevel;
}

// --- Grocery ---

export interface GroceryItem {
  id: string;
  name: string;
  quantity: number | null;
  unit: string | null;
  is_bought: boolean;
  added_by_user_id: string;
  source: GroceryItemSource;
  is_personal: boolean;
  personal_for_user_id: string | null;
  personal_visibility: PersonalVisibility;
  created_at: string;
}

// --- Expense ---

export interface Expense {
  id: string;
  title: string;
  amount: number;
  currency: string;
  category: string | null;
  paid_by_user_id: string;
  status: ExpenseStatus;
  source: ExpenseSource;
  splits: ExpenseSplit[];
  created_at: string;
  confirmed_at: string | null;
}

export interface ExpenseSplit {
  id: string;
  user_id: string;
  share_amount: number;
  is_settled: boolean;
  settled_at: string | null;
}

export interface Balance {
  user_a_id: string;
  user_b_id: string;
  net_amount: number;
  direction: "a_owes_b" | "b_owes_a" | "settled";
}

export interface SettlementSuggestion {
  from_user_id: string;
  to_user_id: string;
  amount: number;
}

// --- Meal Planner ---

export interface MealPlanEntry {
  id: string;
  date: string;
  slot: MealSlot;
  text: string;
  headcount: number;
  owner_user_id: string;
  owner_display_name: string;
  created_at: string;
}

// --- Chores ---

export interface Chore {
  id: string;
  name: string;
  is_recurring: boolean;
  recurrence_interval: number | null;
  recurrence_unit: RecurrenceUnit | null;
  start_date: string;
  rotation_enabled: boolean;
  assignees: ChoreAssignee[];
  created_at: string;
}

export interface ChoreAssignee {
  user_id: string;
  display_name: string;
  position: number;
}

export interface ChoreAssignment {
  id: string;
  chore_id: string;
  chore_name: string;
  assigned_to_user_id: string;
  assigned_to_display_name: string;
  due_date: string;
  postponed_to: string | null;
  status: ChoreAssignmentStatus;
  completed_at: string | null;
  completed_by_user_id: string | null;
  completed_by_display_name: string | null;
}

// --- API Responses ---

export interface HouseholdMembership {
  id: string;
  name: string;
  role: string;
}

export interface VerifyResponse {
  user_id: string;
  display_name: string;
  email: string;
  avatar_url: string | null;
  households: HouseholdMembership[];
}
