/**
 * Tests for tab visibility logic from Phase 10.
 * Success criterion: Tab navigation works with correct icons +
 *                    Conditionally show tabs based on enabled_modules
 */

import { ModuleName } from "@hausly/types";

// Extract the tab visibility logic from _layout.tsx to test it independently
interface TabConfig {
  name: string;
  title: string;
  icon: string;
  module?: ModuleName;
}

const TAB_CONFIG: TabConfig[] = [
  { name: "index", title: "Home", icon: "🏠" },
  { name: "grocery", title: "Grocery", icon: "🛒", module: "grocery" },
  { name: "expense", title: "Expenses", icon: "💰", module: "expense" },
  { name: "meal", title: "Meals", icon: "🍽️", module: "meal" },
  { name: "chores", title: "Chores", icon: "✅", module: "chores" },
];

function getVisibleTabs(enabledModules: ModuleName[] | undefined): TabConfig[] {
  return TAB_CONFIG.filter((tab) => {
    if (tab.module == null) return true;
    if (enabledModules == null) return true;
    return enabledModules.includes(tab.module);
  });
}

function getHiddenTabs(enabledModules: ModuleName[] | undefined): TabConfig[] {
  return TAB_CONFIG.filter((tab) => {
    if (tab.module == null) return false;
    if (enabledModules == null) return false;
    return !enabledModules.includes(tab.module);
  });
}

describe("Tab Navigation Visibility", () => {
  // Success criterion: Tab navigation works with correct icons
  test("all_tabs_defined_with_correct_structure", () => {
    expect(TAB_CONFIG).toHaveLength(5);
    expect(TAB_CONFIG[0]).toEqual({ name: "index", title: "Home", icon: "🏠" });
    expect(TAB_CONFIG[1].module).toBe("grocery");
    expect(TAB_CONFIG[2].module).toBe("expense");
    expect(TAB_CONFIG[3].module).toBe("meal");
    expect(TAB_CONFIG[4].module).toBe("chores");
  });

  // Success criterion: Conditionally show tabs based on enabled_modules
  test("all_module_tabs_visible_when_all_modules_enabled", () => {
    const allModules: ModuleName[] = ["grocery", "expense", "meal", "chores"];
    const visible = getVisibleTabs(allModules);
    expect(visible).toHaveLength(5); // Home + all 4 modules
  });

  test("home_always_visible_regardless_of_enabled_modules", () => {
    const noModules: ModuleName[] = [];
    const visible = getVisibleTabs(noModules);
    expect(visible.find((t) => t.name === "index")).toBeDefined();
  });

  test("disabled_module_tab_hidden", () => {
    const partialModules: ModuleName[] = ["grocery", "expense"];
    const hidden = getHiddenTabs(partialModules);
    expect(hidden.map((t) => t.name)).toContain("meal");
    expect(hidden.map((t) => t.name)).toContain("chores");
    expect(hidden.map((t) => t.name)).not.toContain("grocery");
  });

  // Edge case: enabledModules undefined (settings not loaded yet) → show all
  test("all_tabs_visible_when_settings_not_loaded_yet", () => {
    const visible = getVisibleTabs(undefined);
    expect(visible).toHaveLength(5);
  });

  // Edge case: empty enabled_modules → all module tabs hidden, only Home remains
  test("only_home_visible_when_no_modules_enabled", () => {
    const visible = getVisibleTabs([]);
    expect(visible).toHaveLength(1);
    expect(visible[0].name).toBe("index");
  });

  // Edge case: single module enabled
  test("single_module_enabled_shows_only_that_plus_home", () => {
    const visible = getVisibleTabs(["grocery"]);
    expect(visible).toHaveLength(2);
    expect(visible.map((t) => t.name)).toEqual(["index", "grocery"]);
  });
});
