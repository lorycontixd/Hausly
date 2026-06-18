# Security — Production Readiness

- Read: false
- Approved: false
- Notes: NA

> **Document type:** Security requirements and implementation guide for production deployment.
> **Author:** Lorenzo + Claude
> **Last updated:** June 2026
> **Scope:** All layers — infrastructure, backend, mobile, CI/CD, and operational security.

---

## 1. Current Security Posture

### What's already in place (v0.1.0):
| Layer | Mechanism | Status |
|-------|-----------|--------|
| Authentication | Firebase Auth (ID token verification server-side) | ✅ Implemented |
| Authorization | `household_id` scoping on all queries | ✅ Implemented |
| Tenant isolation | PostgreSQL Row-Level Security policies | ✅ Implemented |
| Input validation | Pydantic/SQLModel schemas on all endpoints | ✅ Implemented |
| Transport security | HTTPS on Container Apps default domain | ✅ By default |
| CORS | Origin allowlist in FastAPI middleware | ✅ Configured |

### What's missing (this document covers):
| Gap | Risk Level | Section |
|-----|------------|---------|
| Secrets in repo (`.env`, `firebase-sa.json`) | **Critical** | §2 |
| No rate limiting | **High** | §3 |
| No dependency vulnerability scanning | **High** | §4 |
| Missing security headers | **Medium** | §5 |
| No request body size limits | **Medium** | §6 |
| No audit logging | **Medium** | §7 |
| Incomplete input constraints | **Medium** | §8 |
| No account deletion flow | **Medium** | §9 |
| No security testing in CI | **Medium** | §10 |

---

## 2. Secret Management — Azure Key Vault

### Problem
Secrets are currently stored in:
- `apps/api/.env` — database URL, SignalR connection string, OpenAI keys
- `apps/api/firebase-sa.json` — Firebase service account private key (committed to repo)
- `apps/mobile/.env` — Firebase config (these are safe to expose — Firebase client config is public by design)

The API secrets in the repo mean anyone with read access to the codebase has full database and service account access. If this repo is ever made public (or a collaborator's machine is compromised), all infrastructure is exposed.

### Solution: Azure Key Vault

**Why Key Vault:**
- Native integration with Container Apps — secrets injected as env vars at deploy time, no code changes.
- Free tier (10K transactions/month) is more than sufficient.
- Audit trail: every access logged, queryable via Azure Monitor.
- Supports secret rotation without redeployment (Container Apps can poll for updates).
- Role-based access: only the Container Apps managed identity can read secrets, not developers' personal accounts.

**Secrets to store:**

| Secret Name | Current Location | Sensitivity |
|---|---|---|
| `DATABASE-URL` | `.env` | Critical — full DB access |
| `FIREBASE-SA-JSON` | `firebase-sa.json` file | Critical — can impersonate any user |
| `SIGNALR-CONNECTION-STRING` | `.env` | High — can broadcast to all clients |
| `AZURE-OPENAI-KEY` | `.env` | Medium — cost exposure |

**Implementation:**

1. Create Key Vault via Bicep:
   ```bicep
   resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
     name: 'kv-hausly-${environment}'
     location: location
     properties: {
       sku: { family: 'A', name: 'standard' }
       tenantId: subscription().tenantId
       enableRbacAuthorization: true
     }
   }
   ```

2. Grant Container Apps managed identity access:
   - Role: `Key Vault Secrets User` (read-only — cannot modify secrets)
   - Principle of least privilege: the app can read, only the deployment pipeline can write

3. Reference secrets in Container Apps config:
   ```bicep
   secrets: [
     { name: 'database-url', keyVaultUrl: '${keyVault.properties.vaultUri}secrets/DATABASE-URL' }
   ]
   ```

4. Clean up:
   - Add `firebase-sa.json` and `.env` to `.gitignore`
   - Run `git rm --cached apps/api/firebase-sa.json`
   - Consider BFG Repo Cleaner to purge from history (if repo has ever been public or shared)

5. Local development strategy:
   - Developers keep a local `.env` (gitignored) for local dev
   - CI/CD uses Key Vault references
   - No secrets in Docker images or CI logs

### Security properties achieved:
- **Separation of concerns:** app code never handles raw secrets; they arrive as env vars
- **Audit trail:** who accessed what secret, when
- **Rotation without downtime:** update secret in Key Vault, Container Apps picks up new value on next restart
- **Blast radius reduction:** compromised repo ≠ compromised infrastructure

---

## 3. API Rate Limiting

### Problem
Without rate limiting:
- A single script can exhaust Container Apps compute budget (€50/month cap could be hit in hours)
- Credential stuffing attacks on auth endpoints go undetected
- Azure OpenAI rate limits produce cryptic 429 errors to legitimate users
- SignalR free tier (20K messages/day) can be exhausted by one bad actor
- Database connection pool can be starved by a flood of requests

### Solution: `slowapi` middleware

**Why `slowapi`:**
- Built on `limits` library — battle-tested rate limiting logic
- Integrates with FastAPI's dependency injection natively
- Supports multiple storage backends: in-memory (dev), Redis (prod multi-instance)
- Returns proper `429 Too Many Requests` with `Retry-After` header (RFC compliant)
- Minimal code: ~20 lines to configure for the entire app

**Why not alternatives:**
- **nginx rate limiting:** We're on Container Apps, no nginx in front. Would require adding a reverse proxy (complexity + cost).
- **Azure API Management:** Starts at ~€40/month for Developer tier. Overkill for a single API with <1K DAU.
- **Custom middleware:** Reinventing the wheel. `slowapi` handles edge cases (distributed windows, key extraction) already.

**Rate limit configuration:**

| Endpoint Category | Limit | Key | Reasoning |
|---|---|---|---|
| `POST /api/auth/*` | 10/minute | IP address | Auth endpoints are brute-force targets. 10/min allows legitimate retry after typos but blocks automated attacks. |
| `POST, PUT, DELETE` (all write ops) | 30/minute | User ID (from Firebase token) | During active grocery shopping, a user might check off 10-15 items in rapid succession. 30/min gives 2x headroom. |
| `GET` (all read ops) | 120/minute | User ID | TanStack Query may fire multiple parallel fetches on screen load. 120/min = 2/second sustained, sufficient for any UI pattern. |
| `AI endpoints` (future) | 5/minute | User ID | Azure OpenAI costs ~€0.002/request. 5/min * 1000 users * 30 days = €4.32/month worst case. Affordable cap. |
| `GET /api/health` | Unlimited | — | Monitoring must never be rate-limited. |

**Implementation:**

```python
# hausly/middleware/rate_limit.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(
    key_func=get_remote_address,  # fallback for unauthenticated routes
    default_limits=["120/minute"],
    storage_uri="memory://",  # Redis URI for production
)
```

- Apply per-route overrides using `@limiter.limit("10/minute")` decorator on auth routes
- For authenticated routes, extract user ID from the Firebase token as the rate limit key
- Log all 429 responses to Application Insights (abuse detection)

**Production scaling:**
- When running multiple Container Apps replicas, switch storage from `memory://` to `redis://`
- Azure Cache for Redis (Basic C0): ~€13/month. Only needed when scaling to multiple instances.
- Until then, in-memory is correct and free.

---

## 4. Dependency Vulnerability Scanning

### Problem
Python and npm ecosystems have frequent CVE disclosures. A vulnerable dependency in production is a liability even if your own code is secure.

### Tools:

| Tool | Scope | Cost | Integration |
|---|---|---|---|
| **GitHub Dependabot** | Python (pip) + Node (npm) + GitHub Actions | Free | Automatic PRs for vulnerable dependencies |
| **`pip-audit`** | Python packages against PyPI advisory DB | Free | CI step — fails build on known vulnerabilities |
| **`npm audit`** | Node packages against npm advisory DB | Free | CI step — fails build on high/critical severity |
| **Snyk** (optional, future) | Deeper analysis, container image scanning | Free tier: 200 tests/month | GitHub integration |

### Why these tools:
- **Dependabot** catches vulnerabilities you don't know about — creates PRs automatically.
- **`pip-audit`** in CI is a gate — even if you ignore a Dependabot PR, the build fails.
- **`npm audit`** same principle for the mobile app dependencies.
- Together, they provide defense-in-depth: proactive (Dependabot) + reactive (CI gate).

### Configuration:
- Dependabot: weekly checks, max 5 open PRs to avoid noise
- `pip-audit`: run in CI on every push, fail on any severity ≥ HIGH
- `npm audit`: run in CI, fail on `--audit-level=high`

---

## 5. Security Headers

### Problem
Missing headers allow:
- Clickjacking (embedding your API responses in an iframe)
- MIME-type sniffing (browser interpreting response as executable)
- Protocol downgrade attacks (HTTP instead of HTTPS)

### Headers to add:

| Header | Value | Purpose |
|---|---|---|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME-type sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking (API has no frameable content) |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Force HTTPS for 1 year |
| `X-XSS-Protection` | `0` | Disable browser XSS filter (causes more harm than good in modern browsers) |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limit referrer leakage |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Explicitly deny permissions API has no use for |

### Implementation:
```python
# hausly/middleware/security_headers.py
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response
```

**Cost:** €0. Pure code change.

---

## 6. Request Body Size Limits

### Problem
FastAPI/Starlette has no default request body size limit. An attacker can send a 1 GB JSON payload, exhausting Container Apps memory (0.5-2 GB available) and crashing the instance.

### Solution:
- Default limit: **1 MB** for standard API requests (JSON payloads for expenses, grocery items, etc. are typically <10 KB)
- Upload limit: **10 MB** for future image endpoints (receipt photos)
- Implementation: Starlette middleware that reads `Content-Length` header and rejects oversized requests with 413

```python
class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_size: int = 1_048_576):  # 1 MB default
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_size:
            return JSONResponse(status_code=413, content={"detail": "Request too large"})
        return await call_next(request)
```

**Note:** This also limits chunked transfer encoding attacks. For true protection, also limit the actual body read (not just the header), as `Content-Length` can be spoofed.

---

## 7. Audit Logging

### Problem
For a multi-tenant app handling financial data, you need to know:
- Who did what, when, to which household's data
- Unauthorized access attempts
- Admin actions (member removal, household deletion)

### Solution: Structured audit events via Application Insights

**Events to log:**

| Category | Events | Severity |
|---|---|---|
| Auth | Login, logout, token refresh, failed auth | INFO / WARNING |
| Authorization | Access denied (wrong household), RLS violation | WARNING |
| Financial | Expense created, modified, deleted, settled | INFO |
| Admin | Member invited, removed, household settings changed | INFO |
| Security | Rate limit hit, malformed request, oversized payload | WARNING |

**Implementation:**
- Use Python's `logging` module with structured fields (JSON format)
- OpenTelemetry exporter sends to Application Insights
- Every log entry includes: `user_id`, `household_id`, `action`, `target_entity`, `timestamp`
- Sensitive data (amounts, names) are NOT logged — only IDs and action types

**Retention:** Application Insights default retention is 90 days (free). Extend to 1 year only if legally required.

---

## 8. Input Validation Hardening

### Current state:
- Pydantic models enforce types and required fields ✅
- SQLModel parameterizes all queries (no SQL injection) ✅

### Gaps to close:

| Issue | Fix | Example |
|---|---|---|
| Unbounded string fields | Add `max_length` to all `str` fields in Pydantic models | Item name: `max_length=200` |
| Unbounded list fields | Add `max_length` to all `list` fields | Grocery items in batch: `max_length=100` |
| Numeric fields without bounds | Add `ge`/`le` constraints | Amount: `ge=0, le=999999.99` |
| UUID path params not validated | Use `UUID` type annotation (Pydantic validates format) | `/expenses/{expense_id}` |
| Missing enum validation | Use `Literal` or `Enum` types for categorical fields | Split type: `Literal["equal", "percentage", "exact"]` |

### Audit process:
1. Grep all Pydantic models for `str` fields without `max_length`
2. Grep all `list` fields without `max_length`
3. Grep all numeric fields without `ge`/`le`
4. Add constraints based on realistic maximums
5. Add integration test with payloads that exceed all limits → verify 422 responses

**Principle:** Every field that accepts user input has an explicit upper bound. The question is never "should I add a limit?" — it's "what's the right limit?"

---

## 9. Account Deletion & Data Handling

### Requirement
- **Apple App Store:** requires account deletion option (mandatory since June 2022)
- **GDPR Article 17:** right to erasure for EU users
- **Google Play:** requires account deletion option (mandatory since 2024)

### Implementation:

**Endpoint:** `DELETE /api/v1/me`

**Behavior:**
1. Verify user identity (Firebase token validation)
2. If user is household admin and sole admin → require household transfer or deletion first
3. Soft-delete user record (mark `deleted_at = now()`)
4. Remove user from all households (trigger leave flow for each)
5. Delete future meal plan entries owned by user
6. Anonymize past entries: replace `user_id` with a sentinel `DELETED_USER` value
7. Revoke all Firebase Auth sessions
8. Delete Firebase Auth account
9. Queue background job: hard-delete user data after 30-day grace period (allows recovery if accidental)
10. Send confirmation email

**What gets deleted:**
- User profile, preferences, notification tokens
- Future meal plan entries
- Chore assignments (reassigned to unassigned)
- Expense records: anonymized but retained for other household members' records

**What gets retained (anonymized):**
- Past expense entries (other members need their split history)
- Completed chore records (household history)
- Past meal plan entries (historical record)

---

## 10. Security Testing in CI

### Tools:

| Tool | Purpose | When |
|---|---|---|
| `bandit` | Python static analysis for security issues (hardcoded passwords, SQL injection patterns, unsafe deserialization) | Every PR |
| `pip-audit` | Known vulnerability check against Python packages | Every PR |
| `npm audit` | Known vulnerability check against Node packages | Every PR |
| `trivy` (optional) | Container image vulnerability scanning | On image build |

### Why `bandit`:
- Catches security anti-patterns that code review might miss
- False positive rate is manageable (~10% with default config)
- Runs in <10 seconds on a project this size
- Catches: `assert` used for validation (removed in optimized builds), hardcoded passwords, `eval()`, unsafe YAML loading, weak crypto

### CI integration:
```yaml
- name: Security scan (Python)
  run: |
    pip install bandit pip-audit
    bandit -r apps/api/hausly/ -ll  # medium+ severity only
    pip-audit --require-hashes --strict
```

---

## 11. Security Checklist — Pre-Production Gate

Before any production deployment, all items must be verified:

- [ ] All secrets in Azure Key Vault (none in repo, none in images)
- [ ] `firebase-sa.json` removed from git history
- [ ] Rate limiting active on all endpoints
- [ ] Security headers middleware enabled
- [ ] Request body size limits enforced
- [ ] All Pydantic fields have explicit constraints
- [ ] Dependabot enabled and no open critical/high alerts
- [ ] `bandit` passing in CI with no medium+ findings
- [ ] `pip-audit` and `npm audit` passing with no high+ vulnerabilities
- [ ] Account deletion endpoint implemented and tested
- [ ] HTTPS enforced (no HTTP fallback)
- [ ] CORS origins restricted to production domains only
- [ ] Firebase Auth token verification on all protected routes
- [ ] RLS policies tested (cross-household access blocked)
- [ ] Audit logging active for auth and financial events
- [ ] Error responses do not leak stack traces or internal details in production mode
- [ ] No debug endpoints or documentation exposed in production (`docs_url=None` when `ENV=prod`)

---

## 12. Threat Model Summary (STRIDE)

| Threat | Category | Mitigation |
|---|---|---|
| User impersonation | Spoofing | Firebase Auth token verification on every request |
| Cross-household data access | Tampering / Info Disclosure | `household_id` scoping + RLS policies |
| Financial data manipulation | Tampering | Explicit user confirmation on all mutations, audit logging |
| API abuse / DoS | Denial of Service | Rate limiting, request size limits, Container Apps auto-scaling |
| Credential theft | Info Disclosure | Key Vault, no secrets in repo, token rotation |
| Dependency exploits | Elevation of Privilege | Dependabot, `pip-audit`, `npm audit`, `bandit` |
| Session hijacking | Spoofing | Firebase short-lived ID tokens (1 hour), HTTPS only |
| Data exfiltration | Info Disclosure | RLS, no admin endpoints exposed, minimal logging of sensitive data |
