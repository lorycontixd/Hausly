---
description: "Use when writing Python backend code, FastAPI endpoints, SQLModel models, Alembic migrations, or async services. Covers apps/api/ conventions."
applyTo: "apps/api/**"
---
# API Backend Conventions (apps/api/)

## Architecture Layers

```
router (thin) → service (business logic) → repository/ORM (data access)
```

- Routers: HTTP concerns only — parse request, call service, return response.
- Services: Business logic, validation, cross-module calls. Never import FastAPI here.
- Models: SQLModel classes. Never return raw ORM objects from services.

## File Patterns

| File | Role |
|------|------|
| `modules/<name>/models.py` | SQLModel table definitions |
| `modules/<name>/schemas.py` | Pydantic request/response models |
| `modules/<name>/service.py` | Business logic functions (async) |
| `modules/<name>/router.py` | FastAPI router with endpoint handlers |

## Coding Rules

- All I/O is `async`/`await`. No synchronous DB calls.
- Every function that touches the DB takes `session: AsyncSession` as parameter.
- All DB queries are scoped by `household_id`. Never query without tenant filter.
- Use `Depends()` for auth, DB session, and module-access checks.
- Type every function parameter and return value.
- Use `UUID` for all primary keys (generated server-side).
- Timestamps use `datetime` with UTC timezone.

## Schemas

- Request schemas: `<Entity>Create`, `<Entity>Update` (partial with Optional fields).
- Response schemas: `<Entity>Response` — always include `id`, `created_at`.
- Never expose internal fields (e.g., `household_id` in responses when it's already in the URL path).

## Migrations (Alembic)

- Append-only. Never edit an applied migration.
- Naming: `NNN_descriptive_name.py` (e.g., `003_grocery.py`).
- Always include `upgrade()` and `downgrade()`.
- Add RLS policies in the same migration that creates the table.
- Test with `alembic upgrade head` on a clean DB.

## Error Handling

- Use `HTTPException` with appropriate status codes in routers only.
- Services raise domain exceptions; routers catch and translate to HTTP.
- Standard codes: 400 (validation), 401 (auth), 403 (forbidden/module disabled), 404 (not found), 409 (conflict).

## Testing

- Use `pytest-asyncio` with the transaction rollback fixture from `tests/conftest.py`.
- Test file naming: `tests/modules/test_<module>.py`.
- Test the service layer primarily; router tests for auth/guard logic only.
- Every test function is `async def test_...`.

## Dependencies Pattern

```python
from hausly.dependencies import get_current_user, get_db, get_household_membership, require_module

@router.post("/", dependencies=[Depends(require_module("grocery"))])
async def create_item(
    data: ItemCreate,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_item(db, membership.household_id, user.id, data)
```

## SQL Scripts (`scripts/sql/`)

- When SQL commands are requested to perform complex or multi-step database operations (e.g., data resets, manual migrations, tenant cleanup, test setup), save the command as a `.sql` file in `apps/api/scripts/sql/`.
- File naming: `<verb>_<entity>_<context>.sql` (e.g., `remove_user_from_household.sql`).
- Each script must include a header comment explaining: purpose, usage instructions, constraints respected, and a warning if it bypasses service-layer logic.
- Scripts are for dev/test use only. Never run raw SQL against production without a logged decision.

## Commit Messages

Prefix: `api:` (e.g., `api: add grocery session complete endpoint`)
