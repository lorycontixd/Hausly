# Global Actions — Implementation Plan [completed]

- Read: true
- Approved: true
- Notes: NA

---

## Overview

Add two persistent header buttons (user avatar + three-dots menu) that appear on all tab screens after login. These are user-level controls unrelated to any household or module.

**Motivation:** Currently there is no UI surface for user-level features (profile, logout, recipes, preferences). Logout isn't exposed anywhere in the app. Recipes (v2, user-level) need a dedicated entry point separate from household tabs.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Button placement | `headerRight` on tab `screenOptions` | Native-feeling, no layout hacks, aligns right per convention |
| Three-dots panel | Bottom `Sheet` (existing component) | Reuses existing UI primitive, consistent with app patterns |
| Navigation target | `(modals)` route group with `presentation: "modal"` | Slides up over tabs, stack back arrow works automatically |
| User settings menu label | "Preferences" | Avoids collision with existing "Settings" tab (household settings) |
| Back navigation | Standard Stack back arrow | Native platform convention; no custom home button |
| Recipes screen | Empty placeholder with `EmptyState` | v2 scope — no recipe backend exists yet |
| User settings screen | Empty placeholder | No user-level settings model/API exists yet |

---

## Route Structure

```
app/
  _layout.tsx                 ← EDIT: register (modals) group in root Stack
  (tabs)/
    _layout.tsx               ← EDIT: add headerRight with GlobalActions
    settings/
      _layout.tsx             ← EDIT: add headerRight to nested Stack screens
  (modals)/                   ← NEW route group
    _layout.tsx               ← Stack with presentation: "modal"
    profile.tsx               ← User profile screen
    recipes.tsx               ← Empty placeholder (v2)
    preferences.tsx           ← User-level preferences (empty for now)
    dev-info.tsx              ← Version and build info
```

---

## File Inventory

| File | Action | Purpose |
|------|--------|---------|
| `components/GlobalActions.tsx` | Create | Header component: avatar button + three-dots button |
| `components/GlobalActions.styles.ts` | Create | Co-located styles |
| `app/(modals)/_layout.tsx` | Create | Modal Stack layout with presentation: "modal" |
| `app/(modals)/profile.tsx` | Create | User profile: avatar, name, email, current household |
| `app/(modals)/recipes.tsx` | Create | Empty placeholder with EmptyState |
| `app/(modals)/preferences.tsx` | Create | Empty placeholder with EmptyState |
| `app/(modals)/dev-info.tsx` | Create | App version, API version, environment |
| `app/(tabs)/_layout.tsx` | Edit | Add `headerRight: () => <GlobalActions />` to screenOptions |
| `app/(tabs)/settings/_layout.tsx` | Edit | Add `headerRight` to nested Stack screenOptions |
| `app/_layout.tsx` | Edit | Add `(modals)` screen group to root Stack |
| `i18n/en.json` | Edit | Add global actions strings |

---

## Implementation Steps

### Step 1: Create GlobalActions header component

**File:** `components/GlobalActions.tsx` + `components/GlobalActions.styles.ts`

Renders two `Pressable` elements in a horizontal row, right-aligned:

1. **User avatar** — uses existing `Avatar` component (28px) with the user's display name initials. On press → `router.push("/(modals)/profile")`.
2. **Three-dots icon** — `Ionicons` `ellipsis-vertical` (from `@expo/vector-icons`, already installed as transitive dependency). On press → opens a local `Sheet` state.

The `Sheet` contains four menu rows, each a `Pressable` with emoji/icon + label:

| Item | Icon | Action |
|------|------|--------|
| Developer Info | `ℹ️` | `router.push("/(modals)/dev-info")` + close sheet |
| My Recipes | `📖` | `router.push("/(modals)/recipes")` + close sheet |
| Preferences | `⚙️` | `router.push("/(modals)/preferences")` + close sheet |
| Log Out | `🚪` | `Alert.alert` confirmation → `signOut()` + close sheet |

Component consumes `useAuthContext()` for display name and `signOut`, and `useRouter()` for navigation.

### Step 2: Create (modals) route group

**File:** `app/(modals)/_layout.tsx`

```tsx
<Stack
  screenOptions={{
    presentation: "modal",
    headerStyle: { backgroundColor: colors.background },
    headerTintColor: colors.text,
    headerTitleStyle: { fontWeight: "600" },
  }}
>
  <Stack.Screen name="profile" options={{ title: "Profile" }} />
  <Stack.Screen name="recipes" options={{ title: "My Recipes" }} />
  <Stack.Screen name="preferences" options={{ title: "Preferences" }} />
  <Stack.Screen name="dev-info" options={{ title: "About" }} />
</Stack>
```

This automatically provides a back arrow/close button on each screen.

### Step 3: Profile screen

**File:** `app/(modals)/profile.tsx`

Content (read-only for v1):
- Large `Avatar` (80px) centered at top — shows profile picture URI or initials
- **Display name** — from `profile.display_name` or fallback to email prefix
- **Email** — from `profile.email` or Firebase user email
- **Current household** — from `profile.households[0].name` (or "No household" if empty)

Styled with `Card` sections using existing design tokens. No edit functionality in v1 (no profile update API exists).

### Step 4: Dev Info screen

**File:** `app/(modals)/dev-info.tsx`

Content:
- **App version** — from `expo-constants` (`Constants.expoConfig?.version`)
- **API version** — hardcoded `v1`
- **Platform** — `Platform.OS` + `Platform.Version`
- **Environment** — `__DEV__` flag → "Development" or "Production"

Displayed as a simple list of label/value rows in a `Card`.

### Step 5: Recipes placeholder

**File:** `app/(modals)/recipes.tsx`

- `EmptyState` component with title "My Recipes" and message "Recipe book coming soon — stay tuned!"
- No interactable elements

### Step 6: Preferences placeholder

**File:** `app/(modals)/preferences.tsx`

- `EmptyState` component with title "Preferences" and message "User preferences coming soon."
- No interactable elements

### Step 7: Wire into tabs layout

**File:** `app/(tabs)/_layout.tsx`

- Import `GlobalActions`
- Add to `Tabs` `screenOptions`: `headerRight: () => <GlobalActions />`
- For the `settings` tab (which sets `headerShown: false` and has its own Stack), the nested `settings/_layout.tsx` needs `headerRight` added to its Stack `screenOptions` so the buttons appear on Settings sub-screens too.

### Step 8: Wire into root layout

**File:** `app/_layout.tsx`

- Add `(modals)` as a screen group inside the root `Stack`:
```tsx
<Stack.Screen
  name="(modals)"
  options={{ headerShown: false, presentation: "modal" }}
/>
```

### Step 9: Add i18n strings

**File:** `i18n/en.json`

Add a `"global"` section:
```json
"global": {
  "profile": "Profile",
  "recipes": "My Recipes",
  "preferences": "Preferences",
  "devInfo": "Developer Info",
  "logOut": "Log Out",
  "logOutConfirm": "Are you sure you want to log out?",
  "recipesComingSoon": "Recipe book coming soon — stay tuned!",
  "preferencesComingSoon": "User preferences coming soon.",
  "version": "Version",
  "apiVersion": "API Version",
  "platform": "Platform",
  "environment": "Environment"
}
```

---

## User Settings Brainstorm (pick later)

Ten candidate user-level preferences for future implementation. These are all user-scoped (not household-scoped) and would require a `UserSettings` model on the backend.

| # | Setting | Type | Description |
|---|---------|------|-------------|
| 1 | **Theme** | `light` / `dark` / `system` | App appearance. System follows device setting. |
| 2 | **Language** | enum | Display language. English-only for v1, but picker is ready for i18n expansion. |
| 3 | **Notification level** | `off` / `quiet` / `normal` / `all` | User-level override for notification aggressivity (master plan decision #2: group → user priority order). |
| 4 | **Chore reminder timing** | `1h` / `3h` / `1d` / `2d` | How early to receive a reminder before a chore assignment is due. |
| 5 | **Week start day** | `monday` / `sunday` | Affects the meal planner weekly view and chore assignment grouping. |
| 6 | **Default currency** | ISO 4217 code | Personal fallback currency when creating new expenses (overrides household default). |
| 7 | **Haptic feedback** | boolean | Enable/disable vibration on button presses and swipe actions. |
| 8 | **Compact mode** | boolean | Denser list items across all modules vs spacious card layout. |
| 9 | **Biometric lock** | boolean | Require Face ID / fingerprint to open the app after backgrounding. |
| 10 | **Auto-archive checked items** | boolean | Automatically hide completed grocery items after a session instead of keeping them visible with a strikethrough. |

---

## What This Does NOT Include

- **Profile editing** — no `PUT /users/me` endpoint exists. Read-only for v1.
- **Actual preferences functionality** — no `UserSettings` model or API. Placeholder only.
- **Recipe functionality** — v2 scope per master plan.
- **Custom home button** — standard Stack back arrow used.
- **Logout from existing Settings tab** — logout lives exclusively in the three-dots menu.

---

## Dependencies

- `@expo/vector-icons` — already installed as transitive dependency via Expo
- `expo-constants` — already available in Expo managed workflow
- All other imports (`Sheet`, `Avatar`, `EmptyState`, `Card`, `Button`) are existing components

No new packages required.

---

## Success Criteria

- [x] User avatar and three-dots icon visible on all tab screen headers (right-aligned)
- [x] Avatar press navigates to profile modal
- [x] Three-dots press opens bottom sheet with 4 items
- [x] Each sheet item navigates to correct modal screen (or triggers logout)
- [x] Logout shows confirmation alert before signing out
- [x] All modal screens have a working back arrow to dismiss
- [x] Profile shows user's display name, email, current household name, and avatar
- [x] Dev Info shows app version, API version, platform, environment
- [x] Recipes and Preferences show empty placeholders
- [x] TypeScript strict mode passes with zero errors
- [x] Buttons also appear on the nested Settings stack screens

---

## Completed:
- Created `GlobalActions` component (`components/GlobalActions.tsx` + `.styles.ts`): user avatar (28px) + three-dots icon in `headerRight`, opens `Sheet` with 4 menu items (Developer Info, My Recipes, Preferences, Log Out with confirmation alert).
- Created `(modals)` route group with `presentation: "modal"` and 4 screens: profile (avatar, name, email, household), dev-info (version, API, platform, environment via expo-constants), recipes (EmptyState placeholder), preferences (EmptyState placeholder).
- Wired `headerRight: () => <GlobalActions />` into `(tabs)/_layout.tsx` screenOptions and `settings/_layout.tsx` nested Stack screenOptions.
- Registered `(modals)` group in root `_layout.tsx` Stack.
- Added `global` i18n strings section to `i18n/en.json`.
- Zero new dependencies. Zero TypeScript errors.
