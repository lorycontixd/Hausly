---
description: "Add a new API endpoint following the router/service/schema pattern."
agent: "API Implement"
argument-hint: "Module and endpoint (e.g., 'grocery: POST /items')"
---
# Add Endpoint: {{input}}

Create a new API endpoint for: **{{input}}**

## Steps

1. Read [docs/api-reference.md](docs/api-reference.md) for the endpoint contract (path, method, request/response).
2. Read the relevant `docs/logics/` file if this endpoint has complex behavior.
3. Read existing module code to understand current patterns.

4. Implement in order:
   a. **Schema** (`schemas.py`): Request and response Pydantic models.
   b. **Service** (`service.py`): Business logic function (async, takes session + household_id).
   c. **Router** (`router.py`): Endpoint handler (thin — parse, call service, return).

5. Add appropriate guards:
   - `Depends(get_current_user)` for auth
   - `Depends(get_household_membership)` for household access
   - `Depends(require_module("<module>"))` for module gating

6. Run `ruff check .` and `pytest -v`.

## Output

- Files modified
- Endpoint path and method
- Request/response schema shapes
- Test coverage (if test written)
- Suggested commit message
