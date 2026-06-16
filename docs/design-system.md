# Hausly Design System — "Soft Pop"

- Read: false
- Approved: false
- Notes: NA

---

## Design Philosophy

**Soft Pop** — soft pastels with a bold primary accent. Each module has its own color identity. Rounded but not bubbly. Approachable yet organized.

**Why this direction:**
- Hausly's moat is cross-module integration. Per-module colors reinforce that structure in the user's mental model.
- Households need *all* members to engage — personality and warmth help with adoption.
- Scalable: new modules (Pinboard, Recipe Book, AI) just get a new accent color.

---

## Color Palette

### Brand Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `primary` | `#6366F1` | Buttons, active states, links |
| `primaryLight` | `#A5B4FC` | Hover accents, progress fills |
| `primaryDark` | `#4338CA` | Pressed states |
| `primarySoft` | `#EEF2FF` | Tinted backgrounds, secondary buttons, avatar fallback |

### Surfaces

| Token | Hex | Usage |
|-------|-----|-------|
| `background` | `#F8FAFC` | App background (slightly cool, not pure white) |
| `surface` | `#FFFFFF` | Cards, sheets, elevated containers |
| `border` | `#E2E8F0` | Dividers, card borders |
| `borderLight` | `#F1F5F9` | Subtle separation |

### Text

| Token | Hex | Usage |
|-------|-----|-------|
| `text` | `#1E293B` | Primary content (slate, not pure black) |
| `textSecondary` | `#64748B` | Supporting text, timestamps |
| `textTertiary` | `#94A3B8` | Placeholders, disabled text |
| `textInverse` | `#FFFFFF` | On primary/dark surfaces |

### Semantic

| Token | Hex | Usage |
|-------|-----|-------|
| `success` | `#10B981` | Confirmations, completed states |
| `warning` | `#F59E0B` | Attention, pending drafts |
| `error` | `#EF4444` | Destructive actions, validation errors |
| `info` | `#3B82F6` | Informational badges |

### Module Accent Colors

Each module gets a dedicated color for headers, FABs, and contextual tints.

| Module | Accent | Soft Tint | Rationale |
|--------|--------|-----------|-----------|
| Grocery | `#10B981` (emerald) | `#ECFDF5` | Fresh, natural |
| Expenses | `#F59E0B` (amber) | `#FFFBEB` | Money, attention |
| Meals | `#EC4899` (pink) | `#FDF2F8` | Warm, food-adjacent |
| Chores | `#8B5CF6` (purple) | `#F5F3FF` | Distinct from primary |

---

## Typography

**Font:** Inter (loaded via `expo-font`, falls back to system default).

| Style | Size | Weight | Line Height | Letter Spacing |
|-------|------|--------|-------------|----------------|
| `heading` | 24 | 700 | 32 | -0.3 |
| `subheading` | 18 | 600 | 24 | -0.2 |
| `body` | 16 | 400 | 24 | 0 |
| `bodySmall` | 14 | 400 | 20 | 0 |
| `caption` | 12 | 500 | 16 | 0 |
| `label` | 14 | 600 | 20 | 0 |

---

## Spacing & Radius

### Spacing Scale

| Token | Value |
|-------|-------|
| `xs` | 4px |
| `sm` | 8px |
| `md` | 12px |
| `lg` | 16px |
| `xl` | 20px |
| `xxl` | 24px |
| `xxxl` | 32px |

**Principle:** Generous padding inside cards (16–20px), tighter between list items (8–12px).

### Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `sm` | 8px | Chips, small badges |
| `md` | 12px | Buttons, inputs |
| `lg` | 16px | Cards |
| `xl` | 20px | Large cards, modals |
| `xxl` | 24px | Bottom sheets |
| `full` | 9999px | Avatars, pills |

---

## Shadows

Layered soft shadows with slate-tinted color (not pure black).

| Level | Offset | Opacity | Radius | Usage |
|-------|--------|---------|--------|-------|
| `sm` | 0, 1 | 0.04 | 3 | Subtle lift (buttons) |
| `md` | 0, 4 | 0.06 | 12 | Cards, elevated surfaces |
| `lg` | 0, 8 | 0.08 | 24 | Modals, popovers |

---

## Icons

**Library:** `lucide-react-native` (MIT, tree-shakeable, consistent 24px grid).

---

## Key UI Patterns

- **Module header tint:** Each module screen has a faint tint of its accent color at the top (e.g., grocery screen has a soft emerald gradient or background).
- **Floating action button:** Per-module FAB in the module's accent color.
- **Status chips:** Draft (amber soft bg + amber text), Confirmed (emerald soft bg + text), Overdue (red soft bg + text).
- **Bottom sheets:** Rounded top corners (24px), drag handle, white surface.
- **Secondary buttons:** Use `primarySoft` background with `primary` text (not gray border).
- **Avatar fallback:** `primarySoft` background with `primary`-colored initials.

---

## Dark Mode

Not in v1. All tokens are semantic (components use `colors.background`, not hard-coded hex), so dark mode is a future token swap.

---

## Haptics

Light haptic feedback on confirm/complete actions via `expo-haptics`. No haptics on navigation or scrolling.

---

## Implementation Reference

Token file: `apps/mobile/constants/theme.ts`
All component styles reference tokens via `@/constants/theme`.
