---
description: "Use when working with shared TypeScript types between mobile and API. Covers packages/types/ conventions."
applyTo: "packages/types/**"
---
# Shared Types Conventions (packages/types/)

## Purpose

This package holds TypeScript types that represent the API contract between backend and mobile. Types here are consumed by `apps/mobile/` via the `@hausly/types` alias.

## Rules

- Types should be generated from the FastAPI OpenAPI schema when possible.
- Do not hand-write types that duplicate what the API already defines.
- Export all public types from `src/index.ts`.
- Use `interface` for entity shapes, `type` for unions and enums.
- Mirror the API response structure exactly — no client-side transformations in type definitions.

## Naming

- Entity responses: `<Entity>Response` (e.g., `ExpenseResponse`, `GroceryItemResponse`)
- Create payloads: `<Entity>Create` (e.g., `ExpenseCreate`)
- Update payloads: `<Entity>Update` (e.g., `ExpenseUpdate`)
- Enums: PascalCase (e.g., `ExpenseStatus`, `SplitMode`)
