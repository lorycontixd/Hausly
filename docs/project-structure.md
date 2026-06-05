# Hausly — Monorepo Structure

```
hausly/
├── CLAUDE.md                              # context file for Claude Code — project conventions, module map
├── README.md
├── LICENSE
├── .gitignore
├── .env.example                           # every env var documented — never commit secrets
├── Makefile                               # start · test · migrate · lint — works across both apps
│
├── apps/
│   ├── mobile/                            # React Native + Expo
│   │   ├── app/                           # Expo Router — file-based routes
│   │   │   ├── (auth)/
│   │   │   │   ├── login.tsx
│   │   │   │   ├── register.tsx
│   │   │   │   └── onboarding.tsx         # household type selection + smart defaults
│   │   │   ├── (tabs)/
│   │   │   │   ├── index.tsx              # home dashboard — balance summary + active items
│   │   │   │   ├── grocery.tsx
│   │   │   │   ├── expense.tsx
│   │   │   │   ├── meal.tsx
│   │   │   │   └── chores.tsx
│   │   │   └── _layout.tsx
│   │   ├── components/
│   │   │   ├── grocery/
│   │   │   ├── expense/
│   │   │   ├── meal/
│   │   │   ├── chores/
│   │   │   └── ui/                        # shared design-system primitives (Button, Card, Sheet…)
│   │   ├── hooks/                         # useHousehold, useCurrentUser, useOfflineSync…
│   │   ├── stores/                        # Zustand — one store per domain module
│   │   │   ├── groceryStore.ts
│   │   │   ├── expenseStore.ts
│   │   │   ├── mealStore.ts
│   │   │   └── householdStore.ts
│   │   ├── services/
│   │   │   ├── api.ts                     # typed API client, auth header injection
│   │   │   ├── firebase.ts                # Firebase Auth init + session management
│   │   │   └── signalr.ts                 # Azure SignalR client — real-time grocery/expense sync
│   │   ├── i18n/                          # externalized strings — i18n-ready from day 1
│   │   │   └── en.json
│   │   ├── assets/
│   │   ├── constants/
│   │   ├── app.json                       # Expo config — bundle ID, plugins, EAS
│   │   ├── babel.config.js
│   │   ├── tsconfig.json
│   │   └── package.json
│   │
│   └── api/                               # FastAPI + Python
│       ├── hausly/                        # Python package root
│       │   ├── __init__.py
│       │   ├── main.py                    # FastAPI app — mounts all module routers
│       │   ├── config.py                  # pydantic-settings — typed env config
│       │   ├── database.py                # async SQLAlchemy engine + session factory (asyncpg)
│       │   ├── dependencies.py            # shared FastAPI deps: auth guard, db session, household check
│       │   ├── auth/
│       │   │   ├── __init__.py
│       │   │   └── firebase.py            # Firebase Admin SDK — token verification + uid extraction
│       │   ├── modules/                   # one sub-package per domain — mirrors the app tabs exactly
│       │   │   ├── grocery/               # 4-file pattern repeated in every module
│       │   │   │   ├── models.py          # SQLAlchemy ORM model
│       │   │   │   ├── schemas.py         # Pydantic request / response schemas
│       │   │   │   ├── service.py         # business logic — calls SignalR after mutations
│       │   │   │   └── router.py          # FastAPI router, mounted in main.py
│       │   │   ├── expense/               # same 4-file structure
│       │   │   ├── meal/                  # same 4-file structure
│       │   │   ├── chores/                # same 4-file structure
│       │   │   ├── household/             # group mgmt · invites · leaving flow · subscription transfer
│       │   │   └── users/                 # profile · notification prefs · household memberships
│       │   ├── realtime/
│       │   │   ├── __init__.py
│       │   │   └── signalr.py             # Azure SignalR hub — broadcasts mutations to all household clients
│       │   ├── ai/
│       │   │   ├── __init__.py
│       │   │   ├── service.py             # AIService class — AI_PROVIDER env var selects provider
│       │   │   └── prompts/               # prompt templates as .txt / .j2 files — one per AI feature
│       │   └── gdpr/                      # pre-launch requirement — not backlog
│       │       ├── __init__.py
│       │       └── export.py              # background task: full household data → JSON + CSV archive
│       ├── migrations/                    # Alembic — always reviewed before applying
│       │   ├── env.py
│       │   └── versions/                  # auto-generated migration scripts
│       ├── tests/
│       │   ├── conftest.py                # fixtures, async test DB, Firebase auth mocking
│       │   └── modules/                   # mirrors hausly/modules/ layout exactly
│       ├── Dockerfile                     # multi-stage build — dev + prod targets, runs on Container Apps
│       ├── pyproject.toml                 # uv · ruff (lint+fmt) · pytest · mypy · dep groups (dev/prod)
│       └── alembic.ini
│
├── packages/                              # shared code (TS only — no shared Python needed)
│   └── types/                             # single source of truth for API contracts
│       ├── src/
│       │   └── index.ts                   # HouseholdMember · GroceryItem · Expense · MealEntry…
│       ├── package.json
│       └── tsconfig.json
│
├── infra/                                 # Azure Bicep — IaC for every resource
│   ├── main.bicep                         # orchestrates all modules, accepts environment param
│   ├── modules/
│   │   ├── container-apps.bicep           # FastAPI service · scale-to-zero · env vars from Key Vault
│   │   ├── postgres.bicep                 # Flexible Server · PgBouncer built-in · RLS for multi-tenancy
│   │   ├── signalr.bicep                  # managed WebSocket backplane — no Redis needed
│   │   └── storage.bicep                  # Blob Storage — receipt photos + GDPR export archives
│   └── parameters/                        # dev vs prod split enforces cheapest-tier-first rule
│       ├── dev.json                        # Free SignalR · Burstable B1ms Postgres · scale-to-zero
│       └── prod.json                       # production-grade tiers — requires explicit decision to promote
│
├── docs/
│   ├── architecture.md                    # system diagram · data flow · module crosstalk map
│   ├── api-reference.md
│   ├── adr/                               # Architecture Decision Records — captures the WHY
│   │   ├── 001-tech-stack.md              # FastAPI · Expo · Azure · Firebase Auth rationale
│   │   ├── 002-offline-sync.md            # last-write-wins v1 · CRDT grocery list v1.1
│   │   └── 003-financial-mutations.md     # user-confirmed only — never automatic
│   └── hausly-project-plan.md             # living brainstorm doc
│
└── .github/
    └── workflows/
        ├── api-ci.yml                     # ruff · mypy · pytest on every PR
        ├── mobile-ci.yml                  # tsc · expo prebuild check on every PR
        └── deploy.yml                     # build → push to Container Registry → deploy on main
```
