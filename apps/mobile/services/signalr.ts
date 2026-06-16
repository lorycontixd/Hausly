import {
  HubConnectionBuilder,
  HubConnection,
  LogLevel,
  HubConnectionState,
} from "@microsoft/signalr";
import { api } from "@/services/api";
import { queryClient } from "@/providers/QueryProvider";

interface NegotiateResponse {
  url: string;
  accessToken: string;
}

let connection: HubConnection | null = null;

export async function connectSignalR(householdId: string): Promise<void> {
  if (connection?.state === HubConnectionState.Connected) {
    return;
  }

  const negotiate = await api.post<NegotiateResponse>(
    "/hubs/household/negotiate"
  );

  connection = new HubConnectionBuilder()
    .withUrl(negotiate.url, { accessTokenFactory: () => negotiate.accessToken })
    .withAutomaticReconnect()
    .configureLogging(LogLevel.Warning)
    .build();

  registerEventHandlers(householdId);

  await connection.start();
}

export async function disconnectSignalR(): Promise<void> {
  if (connection) {
    await connection.stop();
    connection = null;
  }
}

export function getConnection(): HubConnection | null {
  return connection;
}

function registerEventHandlers(householdId: string) {
  if (!connection) return;

  // Grocery events
  connection.on("grocery_item_added", () => {
    queryClient.invalidateQueries({ queryKey: ["grocery", "items", householdId] });
  });
  connection.on("grocery_item_updated", () => {
    queryClient.invalidateQueries({ queryKey: ["grocery", "items", householdId] });
  });
  connection.on("grocery_item_removed", () => {
    queryClient.invalidateQueries({ queryKey: ["grocery", "items", householdId] });
  });
  connection.on("grocery_list_archived", () => {
    queryClient.invalidateQueries({ queryKey: ["grocery", householdId] });
  });
  connection.on("grocery_session_completed", () => {
    queryClient.invalidateQueries({ queryKey: ["grocery", householdId] });
    queryClient.invalidateQueries({ queryKey: ["expenses", householdId] });
  });

  // Expense events
  connection.on("expense_created", () => {
    queryClient.invalidateQueries({ queryKey: ["expenses", householdId] });
    queryClient.invalidateQueries({ queryKey: ["balances", householdId] });
  });
  connection.on("expense_confirmed", () => {
    queryClient.invalidateQueries({ queryKey: ["expenses", householdId] });
    queryClient.invalidateQueries({ queryKey: ["balances", householdId] });
  });
  connection.on("expense_settled", () => {
    queryClient.invalidateQueries({ queryKey: ["expenses", householdId] });
    queryClient.invalidateQueries({ queryKey: ["balances", householdId] });
  });

  // Meal events
  connection.on("meal_entry_created", () => {
    queryClient.invalidateQueries({ queryKey: ["meals", householdId] });
  });
  connection.on("meal_entry_updated", () => {
    queryClient.invalidateQueries({ queryKey: ["meals", householdId] });
  });
  connection.on("meal_entry_removed", () => {
    queryClient.invalidateQueries({ queryKey: ["meals", householdId] });
  });

  // Chore events
  connection.on("chore_created", () => {
    queryClient.invalidateQueries({ queryKey: ["chores", householdId] });
  });
  connection.on("chore_deleted", () => {
    queryClient.invalidateQueries({ queryKey: ["chores", householdId] });
  });
  connection.on("assignment_completed", () => {
    queryClient.invalidateQueries({ queryKey: ["chores", "assignments", householdId] });
  });
  connection.on("assignment_updated", () => {
    queryClient.invalidateQueries({ queryKey: ["chores", "assignments", householdId] });
  });

  // Member events
  connection.on("member_joined", () => {
    queryClient.invalidateQueries({ queryKey: ["household", householdId] });
  });
  connection.on("member_left", () => {
    queryClient.invalidateQueries({ queryKey: ["household", householdId] });
  });

  // Household settings events
  connection.on("household_settings_updated", () => {
    queryClient.invalidateQueries({ queryKey: ["household", householdId] });
  });
}
