---
description: "Use when writing React Native / Expo mobile code, TypeScript components, hooks, stores, or navigation. Covers apps/mobile/ conventions."
applyTo: "apps/mobile/**"
---
# Mobile Conventions (apps/mobile/)

## Architecture

- **Navigation**: Expo Router (file-based routing in `app/`)
- **Server state**: TanStack Query — all API data fetched/cached here
- **Local UI state**: Zustand stores — ephemeral UI state only
- **Real-time**: SignalR client invalidates TanStack Query caches on events

Never mix server state (TanStack Query) with local UI state (Zustand). They are separate domains.

## File Patterns

| File | Role |
|------|------|
| `app/(tabs)/<name>.tsx` | Tab screen |
| `app/(auth)/<name>.tsx` | Auth flow screen |
| `components/ui/<Name>.tsx` | Reusable UI primitive |
| `components/ui/<Name>.styles.ts` | Co-located styles |
| `hooks/use<Name>.ts` | Custom hook (query or logic) |
| `stores/<name>Store.ts` | Zustand store |
| `services/<name>.ts` | External service client (API, Firebase, SignalR) |

## Component Rules

- Functional components only. No class components.
- Co-locate: `Component.tsx`, `Component.styles.ts`, `Component.test.tsx` together.
- Export components as named exports, not default.
- Use path aliases: `@/components/...`, `@/hooks/...`, `@/services/...`.

## TypeScript

- Strict mode enforced. No implicit `any`.
- If `any` is unavoidable, add `// eslint-disable-next-line -- <reason>` with explanation.
- Prefer `interface` for component props, `type` for unions/intersections.
- Import types from `@hausly/types` (packages/types) for API contracts.

## TanStack Query Hooks

```typescript
// hooks/useGrocery.ts
export function useGroceryItems(householdId: string) {
  return useQuery({
    queryKey: ['grocery', 'items', householdId],
    queryFn: () => api.grocery.getItems(householdId),
  });
}

export function useAddGroceryItem(householdId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: GroceryItemCreate) => api.grocery.addItem(householdId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['grocery', 'items', householdId] });
    },
  });
}
```

## Zustand Stores

- Only for local, ephemeral UI state (e.g., shopping session toggle, form drafts).
- Never cache server data in Zustand — that's TanStack Query's job.
- Keep stores small and focused (one per concern).

## SignalR Integration

- SignalR events should call `queryClient.invalidateQueries()` to trigger refetch.
- Never manually update TanStack Query cache from SignalR — invalidate and let the query refetch.

## Styling

- Use `StyleSheet.create()` in co-located `.styles.ts` files.
- No inline styles except trivial one-offs.
- Design tokens (colors, spacing, typography) from a shared theme.

## Navigation

- Use Expo Router's file-based routing.
- Auth guard in `app/_layout.tsx` — redirect unauthenticated users.
- Tab visibility driven by `household.settings.enabled_modules`.

## Commit Messages

Prefix: `mobile:` (e.g., `mobile: implement grocery list screen`)
