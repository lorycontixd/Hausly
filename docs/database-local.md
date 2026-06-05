# Local Database Setup

- Read: false
- Approved: false
- Notes: NA

## Decision

Local and test databases use a real PostgreSQL instance via Docker Compose, with Alembic migrations applied identically to production. Production uses Azure Database for PostgreSQL (Flexible Server, Burstable B1ms tier). The only difference between environments is the `DATABASE_URL` env var.

---

## Stack

| Component | Choice | Notes |
|---|---|---|
| Engine | PostgreSQL 16 | Same major version as Azure Flexible Server (Burstable B1ms in prod) |
| Driver | asyncpg | Async-native, used via SQLAlchemy async engine |
| ORM | SQLModel + SQLAlchemy 2.0 async | Pydantic integration, async session factory |
| Migrations | Alembic (append-only) | Single source of schema truth across all environments |
| Container | Docker Compose | `postgres:16-alpine` image |
| Multi-tenancy | `household_id` FK + Row-Level Security | Applied in migrations, testable locally |

---

## Setup

### Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin) running.
- Python 3.12+ with dev dependencies installed (`pip install -e ".[dev]"` from `apps/api/`).

### Docker Compose Service

A `docker-compose.yml` at repo root (or `apps/api/`) defines the PostgreSQL service:

- Image: `postgres:16-alpine` (pinned to match Azure Flexible Server major version).
- Port: `5433:5432` (avoids conflict with any system-wide PG on 5432).
- Volume: named volume for data persistence between restarts.
- Environment: `POSTGRES_USER=postgres`, `POSTGRES_PASSWORD=postgres`, `POSTGRES_DB=hausly`.

### Environment Variables

```env
# Local development
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/hausly

# Tests (separate DB to avoid dev data interference)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/hausly_test
```

Production uses the Azure Flexible Server connection string — application code is environment-agnostic.

---

## Lifecycle

### Start

```bash
docker compose up -d db          # Start the PG container
cd apps/api && alembic upgrade head   # Apply all migrations (or: make migrate)
```

### Run the API

```bash
make start-api                   # uvicorn with --reload on port 8000
```

### Apply New Migrations

```bash
make migrate-new name="add_chores_table"   # Generate migration
make migrate                               # Apply it
```

### Stop

```bash
docker compose stop db           # Stop container, keep data volume
```

### Reset (destroy data)

```bash
docker compose down -v db        # Remove container + volume
docker compose up -d db          # Fresh container
make migrate                     # Re-apply schema from scratch
```

---

## Plug-and-Play Guarantee

- `hausly/config.py` reads `DATABASE_URL` via pydantic-settings (`.env` file or environment).
- `hausly/database.py` creates the async engine and session factory from that single URL.
- `migrations/env.py` reads the same `DATABASE_URL` via settings.
- Switching between local, CI, and production is purely an env var change. No code branches.

---

## Testing

### Approach: Transaction Rollback

Each test runs inside a rolled-back transaction so no data persists between tests.

**Pattern:**

1. **Session-scoped fixture:** Creates an async engine pointing at the Docker PG container. Runs `alembic upgrade head` once per test session to apply the full schema.
2. **Function-scoped fixture:** Opens a connection, begins a transaction, then creates an `AsyncSession` bound to a nested savepoint (`begin_nested()`).
3. **Dependency override:** The fixture overrides FastAPI's `get_db` dependency to yield the savepoint-bound session.
4. **Teardown:** The outer transaction is rolled back, erasing all changes instantly. The app's normal `session.commit()` calls only commit the savepoint, never the outer transaction.

**Result:**
- Tests are fast (no table drops/recreates between tests).
- Tests are isolated (no shared state leaks).
- RLS policies are exercisable (real PG, real policies).

### CI

- CI pipeline runs `docker compose up -d db` before the test step — identical to local.
- No special CI-only database logic; the fixture works the same everywhere.

---

## Constraints

- Docker must be running for both local development and tests.
- The PG container image major version must stay in sync with Azure Flexible Server (currently 16).
- Use port `5433` locally to avoid collisions with system PostgreSQL.
- Use a dedicated `hausly_test` database for tests to keep dev data intact.
- Alembic migrations are append-only — never edit an applied migration.
