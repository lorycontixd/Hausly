/**
 * Tests for SignalR client event handler registration.
 * Success criterion: SignalR connection established and events received
 *                    that invalidate relevant TanStack Query caches.
 */

// Mock modules before imports
const mockOn = jest.fn();
const mockStart = jest.fn().mockResolvedValue(undefined);
const mockStop = jest.fn().mockResolvedValue(undefined);
const mockBuild = jest.fn().mockReturnValue({
  on: mockOn,
  start: mockStart,
  stop: mockStop,
  state: "Disconnected",
});

jest.mock("@microsoft/signalr", () => ({
  HubConnectionBuilder: jest.fn().mockImplementation(() => ({
    withUrl: jest.fn().mockReturnThis(),
    withAutomaticReconnect: jest.fn().mockReturnThis(),
    configureLogging: jest.fn().mockReturnThis(),
    build: mockBuild,
  })),
  LogLevel: { Warning: 4 },
  HubConnectionState: { Connected: "Connected", Disconnected: "Disconnected" },
}));

jest.mock("@/services/api", () => ({
  api: {
    post: jest.fn().mockResolvedValue({
      url: "https://signalr.example.com/hub",
      accessToken: "test-token-123",
    }),
  },
}));

const mockInvalidateQueries = jest.fn();
jest.mock("@/providers/QueryProvider", () => ({
  queryClient: {
    invalidateQueries: (...args: unknown[]) => mockInvalidateQueries(...args),
  },
}));

import { connectSignalR, disconnectSignalR } from "./signalr";

beforeEach(() => {
  jest.clearAllMocks();
});

describe("SignalR Client", () => {
  // Success criterion: SignalR connection established
  test("connectSignalR_negotiates_and_starts_connection", async () => {
    const { api } = require("@/services/api");

    await connectSignalR("household-123");

    // Verified negotiate endpoint called
    expect(api.post).toHaveBeenCalledWith("/hubs/household/negotiate");
    // Connection started
    expect(mockStart).toHaveBeenCalled();
  });

  // Success criterion: Events received that invalidate caches
  test("connectSignalR_registers_all_expected_event_handlers", async () => {
    await connectSignalR("household-123");

    const registeredEvents = mockOn.mock.calls.map(
      (call: unknown[]) => call[0]
    );

    // Grocery events (5)
    expect(registeredEvents).toContain("grocery_item_added");
    expect(registeredEvents).toContain("grocery_item_updated");
    expect(registeredEvents).toContain("grocery_item_removed");
    expect(registeredEvents).toContain("grocery_list_archived");
    expect(registeredEvents).toContain("grocery_session_completed");

    // Expense events (3)
    expect(registeredEvents).toContain("expense_created");
    expect(registeredEvents).toContain("expense_confirmed");
    expect(registeredEvents).toContain("expense_settled");

    // Meal events (3)
    expect(registeredEvents).toContain("meal_entry_created");
    expect(registeredEvents).toContain("meal_entry_updated");
    expect(registeredEvents).toContain("meal_entry_removed");

    // Chore events (4)
    expect(registeredEvents).toContain("chore_created");
    expect(registeredEvents).toContain("chore_deleted");
    expect(registeredEvents).toContain("assignment_completed");
    expect(registeredEvents).toContain("assignment_updated");

    // Member events (2)
    expect(registeredEvents).toContain("member_joined");
    expect(registeredEvents).toContain("member_left");

    // Household settings (1)
    expect(registeredEvents).toContain("household_settings_updated");

    // Total: 18 event registrations
    expect(mockOn).toHaveBeenCalledTimes(18);
  });

  // Success criterion: Events invalidate correct query caches
  test("grocery_item_added_event_invalidates_grocery_items_cache", async () => {
    await connectSignalR("hh-test");

    // Find the grocery_item_added handler
    const groceryCall = mockOn.mock.calls.find(
      (call: unknown[]) => call[0] === "grocery_item_added"
    );
    expect(groceryCall).toBeDefined();

    // Invoke the handler
    const handler = groceryCall![1] as () => void;
    handler();

    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ["grocery", "items", "hh-test"],
    });
  });

  test("expense_created_event_invalidates_expenses_and_balances", async () => {
    await connectSignalR("hh-test");

    const expenseCall = mockOn.mock.calls.find(
      (call: unknown[]) => call[0] === "expense_created"
    );
    const handler = expenseCall![1] as () => void;
    handler();

    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ["expenses", "hh-test"],
    });
    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ["balances", "hh-test"],
    });
  });

  test("member_joined_event_invalidates_household_cache", async () => {
    await connectSignalR("hh-test");

    const memberCall = mockOn.mock.calls.find(
      (call: unknown[]) => call[0] === "member_joined"
    );
    const handler = memberCall![1] as () => void;
    handler();

    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ["household", "hh-test"],
    });
  });

  // Edge case: grocery_session_completed cross-invalidates grocery AND expenses
  test("grocery_session_completed_invalidates_both_grocery_and_expense_caches", async () => {
    await connectSignalR("hh-test");

    const sessionCall = mockOn.mock.calls.find(
      (call: unknown[]) => call[0] === "grocery_session_completed"
    );
    const handler = sessionCall![1] as () => void;
    handler();

    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ["grocery", "hh-test"],
    });
    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ["expenses", "hh-test"],
    });
  });
});
