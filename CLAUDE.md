# CLAUDE.md — Hausly Project Directives

> **Audience:** Claude Code instances working in this repo.
> **Purpose:** Set the rules of engagement before the first commit, so behaviour is consistent across sessions.
> **Status:** Living document. Update it when project conventions change.

---

## 1. Project Context

Hausly is a mobile companion app for shared living (couples, flatmates, students, families, etc..). The product thesis is **integration as the moat** — no single-purpose competitor offers cross-module intelligence between groceries, expenses, meal planning, and chores. The MVP must demonstrate that integration chain (meal plan → grocery list → expense split) from day one.

This is a **solo developer side project** with business ambitions. Optimise for **shipping over perfection**. Cleverness that costs a week is usually the wrong trade.

---

## 2. Source of Truth

- **`hausly-project-plan.md`** is the source of truth for product scope, architecture, and settled decisions.
- Before suggesting a change to anything in §1–§9 of the plan, read the relevant **Decision Log (§10)** entry. Decisions are logged with rationale; if you can't beat the rationale, don't reopen the decision.
- If a user request conflicts with the plan, **surface the conflict explicitly** before writing code. Don't silently deviate.
- If a request is ambiguous, prefer the interpretation consistent with the plan.

---

## 3. Repository Layout (target)

The repository has a similar layout. A deeper structure is found inside 'docs/hausly-project-structure.md'.

```
hausly/
├── apps/
│   ├── mobile/            # React Native + Expo (TypeScript)
│   └── api/               # FastAPI (Python, async)
├── packages/
│   └── shared-types/      # Generated from OpenAPI; consumed by mobile
├── infra/                 # Bicep / Terraform for Azure resources
├── docs/
│   └── hausly-project-plan.md
    └── ...
├── CLAUDE.md              # This file
└── README.md
```

Don't create directories speculatively. Build the structure as the first real code lands in each area.
**Project structure**: The full project structure is found at **hausly-project-structure.md** inside the docs folder.

### Docs
The documentation of the project is found inside the 'docs' folder.
IMPORTANT: Before reading any file, read the 'docs/docs.md' file to figure out which file is worth analyzing for the current task.

---

## 4. Tech Stack (reference — see plan §4 for rationale)

| Layer | Choice |
|---|---|
| Client | React Native + Expo (managed workflow), TypeScript |
| Client state | Zustand or Jotai |
| Server state | TanStack Query |
| Local DB | expo-sqlite or WatermelonDB |
| Backend | FastAPI (Python, async) |
| ORM | SQLModel + Alembic |
| Database | Azure Database for PostgreSQL (Flexible Server) |
| Real-time | Azure SignalR Service |
| Auth | Firebase Auth |
| Storage | Azure Blob Storage |
| AI | Azure OpenAI (GPT-4o-mini) via `AIService` class |
| Hosting | Azure Container Apps (scale-to-zero) |

Locked decisions. Don't propose alternatives unless a logged decision is being revisited, or you really think the alternative gain is huge.

---

## 5. Build / Run / Test

To be filled in as the repo materialises. Until then: if you scaffold a build/test command, document it here in the same commit.

```
# mobile (Expo)
# api (FastAPI)
# infra
# db migrations
```

---

## 6. Coding Conventions

### TypeScript / React Native
- Strict mode on. `any` requires an inline comment explaining why.
- Functional components and hooks only.
- Co-locate `Component.tsx`, `Component.styles.ts`, `Component.test.tsx`.
- Use path aliases (`@/features/...`) over deep relative imports.
- Server data: TanStack Query. Local UI state: Zustand or Jotai. Don't mix the two domains.
- Never store entitlement flags (free vs paid features) in client state as the source of truth — always re-verify server-side.

### Python / FastAPI
- Async by default for any I/O.
- Pydantic models (or SQLModel) for every request and response schema. Never return raw ORM objects.
- A service/repository layer separates HTTP handlers from DB code. Handlers stay thin.
- All DB queries are scoped by `household_id`. Row-Level Security is the safety net, not the access control.
- Alembic migrations are **append-only**. Never edit a migration that has been applied anywhere — create a new one.
- Long-running work goes through a background queue, not the request thread.

### Cross-cutting
- Type-safe API contract: generate the mobile types from the FastAPI OpenAPI schema. Don't hand-write them.
- Tests where they matter (auth flow, expense splitting math, RLS policies, offline sync conflict resolution). Avoid testing trivia for coverage's sake.
- Commit messages: imperative mood, prefix with module (`mobile:`, `api:`, `infra:`).

---

## 7. Architectural Principles (non-negotiable unless explicitly revisited via §10)

1. **All financial mutations require explicit user confirmation.** No silent writes to expense data from AI, grocery → expense integration, recurring expenses, or any auto-generation. Drafts always, commits on tap. (Plan §2.3)
2. **Multi-tenancy via `household_id` FK + Row-Level Security.** Every household-scoped table has the FK; every query is scoped; RLS policies enforce isolation even when application code forgets. Test that RLS actually blocks cross-household reads.
3. **AI access only through `AIService`.** Provider-specific SDK calls live inside the class. The active provider is selected by an env var. If you find yourself importing `openai` or `anthropic` anywhere else, stop. (Plan §4.8)
4. **Real-time updates flow through Azure SignalR.** Don't introduce a second pub/sub. Don't push real-time logic into the client.
5. **Conflict resolution = last-write-wins for v1, all modules.** CRDT for the grocery list is deferred to v1.1. Do not pre-build CRDT plumbing "just in case". (Plan §7.4)
6. **Free vs paid tier enforcement is server-side.** The client may hide a button, but the server must reject a request from a free-tier user trying to call an AI endpoint.
7. **Recipes are user-level, not household-level.** Owner is `User`, not `Household`. Save = fork. Don't shortcut to a shared-household recipe table. (Plan §9.1 #17)
8. **Graceful degradation when a member doesn't engage.** Any chore can be marked done by anyone. The app must remain useful with 3 of 4 active users.

---

## 8. Azure Infrastructure Discipline

Standing rule from the project owner: **start every new Azure resource at the cheapest tier available for dev, free where possible.** Production-grade tiers only on an explicit, logged decision.

| Service | Dev tier to use | Notes |
|---|---|---|
| SignalR Service | **Free** (20 concurrent, 20K msg/day) | Sufficient for early development |
| Container Apps | **Consumption** plan, scale-to-zero | Pays only when active |
| PostgreSQL Flexible Server | **Burstable B1ms** (smallest) | No free tier exists for Flexible Server |
| Blob Storage | Hot tier, minimal usage | Cents/month at dev scale |
| Azure OpenAI | Pay-per-token, **strict rate limits** during dev | Cap monthly spend explicitly |
| Firebase Auth | Free tier | Covers the app's scale for a long time |

Do not provision anything in a separate resource group from `hausly-dev-rg` without flagging it. Keep dev and prod environments in distinct resource groups when prod arrives.

---

## 9. Decision Log Discipline

The Decision Log lives at the bottom of `hausly-project-plan.md` (§10). It is the project's institutional memory.

- For any **non-trivial** architectural, product, or trade-off decision: append an entry.
- Format: `| Decision | Rationale | Date |` — one row.
- A decision is "non-trivial" if a future contributor (or future you) would reasonably question it or want to revisit it.
- When a question in §9.2 (Still Open) is resolved, move it to §9.1 (Resolved) with a one-line resolution, then add a row in §10.
- **Do not silently overturn a logged decision.** Either accept it, or propose explicitly that it be revisited and explain why.

---

## 10. What to Push Back On

You are expected to be **critical and honest**, not deferential. If a request shows one of these patterns, raise it before coding:

- **Scope creep** into modules not in the current version's roadmap (Plan §2.1).
- **Sub-feature toggles** in settings. The plan explicitly forbids these (Plan §2.3 — "smart defaults, not smart visibility").
- **Auto-writes to financial data**, however small.
- **Provider-specific AI code** outside the `AIService` class.
- **Premature optimisation:** sharding, caching layers, CRDTs, custom protocols, microservices — all wrong for v1.
- **Premature scaling spend:** a "Standard" or "Premium" Azure tier in a dev environment without a logged decision.
- **Anything that breaks graceful degradation** when one household member doesn't engage.
- **Reopening a decision in §10 without engaging the original rationale.**

"Yes-and" agreement on architectural choices is not helpful. If something looks wrong, say so. The author would rather be challenged early than have to undo work later.

---

## 11. Standing Strategic Risks (track, don't try to solve in code)

These are the open structural questions about the product. They are not bugs to fix in a PR — they are concerns to keep in mind when reviewing design decisions.

1. **Multi-module adoption is the entire moat.** The "integration > individual modules" thesis only pays off if households actually use ≥2 modules. There is currently no mechanism to measure or drive this. Features that nudge users toward the cross-module chain (e.g. the meal-plan → grocery → expense flow surfacing during onboarding) are worth more than incremental polish on any single module.
2. **Admin-pays + graceful-degradation tension.** The admin is the only paying user, but the plan requires graceful degradation when any member (including, implicitly, the admin) disengages. There is no plan for the case where the admin becomes inactive without formally leaving. Surface this if a feature decision touches subscription state.
3. **AI as a 2026 premium differentiator is a hard sell.** Receipt OCR, NLP input, and basic recipe parsing are increasingly table-stakes in consumer apps. The paid tier needs more than AI to justify itself in this market — the "all modules + unlimited members" half of the offer needs to carry weight on its own.

---

## 12. Out of Scope (do not build, do not propose)

- **Web app** (deferred — Plan §2.2; revisit only with explicit user research justification)
- **Shared calendar module** (dismissed — Plan §2.2)
- **In-app chat / messaging** (dismissed — pinboard replaces it)
- **Payment processing in-app** (deferred to v3+; settlement is external)
- **AI chatbot / household assistant interface** (dismissed)
- **Predictive grocery ordering** (deferred to v4+)
- **Localisation beyond English in v1** (code must be i18n-ready; no extra translations shipped)
- **CRDT-based offline merge in v1** (deferred to v1.1, grocery list only)

---

## 13. When in Doubt

- Plan says X, user says Y → ask which one wins, log the answer.
- Two acceptable approaches → pick the cheaper / smaller / more reversible one.
- About to build something "for later" → don't.
- About to add a third-party dependency → justify it briefly in the PR description.
- About to write more than 200 lines without showing the user → stop and check in.
