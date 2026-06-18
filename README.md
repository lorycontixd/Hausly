# Hausly — Companion App for Shared Living

A mobile companion app for people who share a living space. Manages groceries, expenses, meal planning, and chores with cross-module intelligence.

## Versions

| Component | Version | Source of Truth |
|-----------|---------|-----------------|
| API | 0.1.0 | `apps/api/pyproject.toml` |
| Mobile | 0.1.0 | `apps/mobile/app.json` |

## Architecture

- **Mobile:** React Native + Expo (TypeScript)
- **Backend:** FastAPI (Python, async)
- **Database:** PostgreSQL (Azure Flexible Server)
- **Real-time:** Azure SignalR Service
- **Auth:** Firebase Auth

## Repository Structure

```
hausly/
├── apps/
│   ├── mobile/    # React Native + Expo
│   └── api/       # FastAPI backend
├── packages/
│   └── types/     # Shared TypeScript types (generated from OpenAPI)
├── infra/         # Azure Bicep IaC
└── docs/          # Project documentation
```

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 16
- Firebase project (for auth)

### Backend

```bash
cd apps/api
cp .env.example .env  # Fill in your values
pip install -e ".[dev]"
alembic upgrade head
uvicorn hausly.main:app --reload
```

### Mobile

```bash
cd apps/mobile
npm install
npx expo start
```

## Documentation

- [Master Plan](docs/planning/hausly-project-master-plan.md)
- [Implementation Plan](docs/planning/implementation-plan-v1.md)
- [API Reference](docs/api-reference.md)
- [Data Models](docs/data-models.md)

## Commands

```bash
make start-api       # Start backend dev server
make start-mobile    # Start Expo dev server
make test-api        # Run backend tests
make lint            # Lint all code
make migrate         # Run Alembic migrations
```

## License

See [LICENSE](LICENSE).
