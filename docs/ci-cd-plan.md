# CI/CD Implementation Plan

- Read: false
- Approved: false
- Notes: NA

> **Document type:** CI/CD pipeline design and implementation guide.
> **Author:** Lorenzo + Claude
> **Last updated:** June 2026
> **Platform:** GitHub Actions
> **Budget:** €0 for CI, ~€4/month for Azure Container Registry

---

## 1. Why CI/CD Now

Without CI/CD, the following failure modes exist:

| Failure mode | Consequence | CI/CD fix |
|---|---|---|
| Type error introduced in PR | API crashes on next deploy | `mypy` + `tsc` gate on every PR |
| Broken migration merged | Database schema corruption in production | `alembic check` + test DB migration in CI |
| Vulnerable dependency added | Security exposure goes unnoticed for weeks | `pip-audit` + `npm audit` gates |
| Manual deploy forgotten step | Production has stale code or missing env vars | Automated deployment with all steps codified |
| "Works on my machine" | Different Python/Node versions, missing deps | Reproducible build in Docker, tested in CI |
| Regression in expense splitting math | Users see wrong amounts | Automated test suite runs on every change |

**Cost of NOT having CI/CD:** A single broken deploy that takes the API down for users. For a household app where people rely on shared data daily, even 30 minutes of downtime erodes trust.

---

## 2. Pipeline Architecture

### 2.1 Trigger Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                        TRIGGER MATRIX                             │
├──────────────────┬──────────────────────────────────────────────┤
│ Event            │ Pipeline                                      │
├──────────────────┼──────────────────────────────────────────────┤
│ PR opened/sync   │ Validate (lint + type + test + security)     │
│ Push to main     │ Validate → Build → Deploy to staging         │
│ Manual dispatch  │ Promote staging → production                  │
│ Schedule (weekly)│ Dependency audit (full vulnerability scan)    │
│ Tag (v*)         │ Mobile release build via EAS                  │
├──────────────────┴──────────────────────────────────────────────┤
```

### 2.2 Pipeline Stages (Detailed)

```
┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────┐
│   LINT &   │──▶│    TEST    │──▶│  SECURITY  │──▶│   BUILD    │──▶│   DEPLOY   │
│ TYPE CHECK │   │            │   │    SCAN    │   │            │   │            │
└────────────┘   └────────────┘   └────────────┘   └────────────┘   └────────────┘
     │                 │                │                 │                │
     ▼                 ▼                ▼                 ▼                ▼
  - ruff lint       - pytest         - bandit          - Docker build   - Push to ACR
  - ruff format     - jest           - pip-audit       - Tag image      - Update Container
  - mypy            - coverage       - npm audit                          Apps revision
  - tsc --noEmit      report                                           - Run migrations
  - eslint                                                             - Health check
```

---

## 3. Stage Details & Reasoning

### 3.1 Lint & Type Check

**Why this runs first:** Fastest stage (~30 seconds). If code doesn't even parse or has obvious type errors, there's no point running expensive tests.

#### Python (API)
| Tool | Purpose | Reasoning |
|---|---|---|
| `ruff check` | Linting (replaces flake8, isort, pyflakes) | 10-100x faster than alternatives. Single tool for all lint rules. |
| `ruff format --check` | Formatting verification (replaces black) | Consistent style, no bikeshedding in reviews. |
| `mypy --strict` | Static type checking | Catches `None` access, wrong argument types, missing returns. FastAPI + Pydantic models benefit enormously from type checking. |

**Why `ruff` over `flake8` + `black` + `isort`:**
- Single dependency instead of three.
- Written in Rust — runs in <1 second on this codebase.
- Drop-in compatible with existing flake8 rules.
- Active maintenance and rapidly expanding rule set.

#### TypeScript (Mobile)
| Tool | Purpose | Reasoning |
|---|---|---|
| `tsc --noEmit` | Type checking without compilation | Catches type errors that ESLint misses. React Native doesn't use tsc for compilation (Babel handles it), but we still want type verification. |
| `eslint` | Code quality and consistency | Catches React hooks violations, unused imports, accessibility issues. |

**Failure behavior:** Any lint or type error fails the pipeline. No warnings-as-errors debates — if the tool flags it, fix it.

### 3.2 Test

**Why tests run after lint:** If there's a syntax error, tests would fail anyway but with a confusing error message. Lint-first gives immediate, actionable feedback.

#### Python Tests
```yaml
- name: Run API tests
  run: |
    cd apps/api
    python -m pytest tests/ -v --tb=short --cov=hausly --cov-report=xml
  env:
    DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/hausly_test
```

**Test database strategy:**
- CI spins up a PostgreSQL service container (GitHub Actions `services:` block)
- Alembic migrations run against the test DB before tests execute
- Tests use transaction rollback pattern (already in `tests/conftest.py`)
- This validates that migrations are correct AND that application code works against the real schema

**Coverage:**
- Generate coverage report (XML for potential future integration with Codecov/Coveralls)
- Do NOT gate on coverage percentage — it incentivizes bad tests. Gate on: all tests pass.
- Track coverage trend over time to catch regressions (optional GitHub Action comment on PR)

#### Mobile Tests
```yaml
- name: Run mobile tests
  run: |
    cd apps/mobile
    npx jest --ci --passWithNoTests --forceExit
```

**Why `--passWithNoTests`:** Some PRs only touch backend code. The mobile test step should succeed even if no mobile tests exist for the changed code.

**Why `--forceExit`:** Jest sometimes hangs with open handles (timers, async operations). `--forceExit` ensures CI doesn't get stuck.

### 3.3 Security Scan

**Why this is a separate stage (not merged with lint):**
- Security tools have different failure semantics — a lint warning is "fix later", a critical CVE is "don't merge".
- Keeps the pipeline's failure message clear: "failed at security" means "you have a vulnerability", not "you forgot a trailing comma".

| Tool | What it checks | Failure threshold |
|---|---|---|
| `bandit` | Python code for security anti-patterns | Medium+ severity |
| `pip-audit` | Python dependencies against PyPI advisory DB | Any known vulnerability |
| `npm audit` | Node dependencies against npm advisory DB | High+ severity |

**Why `npm audit` threshold is High (not all):**
- Low/moderate npm advisories are often in dev dependencies or have no practical exploit path.
- Failing on every advisory would create constant false-positive noise in a React Native project (large transitive dependency tree).
- High+ ensures real vulnerabilities block merge while keeping the signal-to-noise ratio high.

**Why `bandit` medium+ (not low):**
- Low-severity findings are often stylistic (e.g., "consider using `secrets` module instead of `random`").
- Medium+ catches actual security issues: hardcoded passwords, `assert` for validation, `eval()`, unsafe YAML, weak crypto.

### 3.4 Build

**Only runs on `push to main`** (not on PRs). Reasoning:
- Building a Docker image takes 2-5 minutes and uses GitHub Actions minutes.
- PRs only need validation (will it break?), not artifacts (what does it produce?).
- Building on every PR for a solo dev project wastes the 2000 min/month budget.

```yaml
- name: Build and push Docker image
  run: |
    docker build -t $ACR_LOGIN_SERVER/hausly-api:${{ github.sha }} apps/api/
    docker push $ACR_LOGIN_SERVER/hausly-api:${{ github.sha }}
    docker tag $ACR_LOGIN_SERVER/hausly-api:${{ github.sha }} $ACR_LOGIN_SERVER/hausly-api:latest
    docker push $ACR_LOGIN_SERVER/hausly-api:latest
```

**Image tagging strategy:**
- Every build tagged with the Git commit SHA (immutable, traceable)
- `latest` tag always points to the most recent successful build
- Future: add semantic version tags on release (`v0.2.0`)

**Why Azure Container Registry (ACR) over Docker Hub or GitHub Container Registry:**
- ACR integrates natively with Container Apps (same Azure subscription, no credential management)
- Basic tier: €4/month, 10 GB storage — sufficient for a single-service project
- Docker Hub free tier limits: 1 private repo, rate-limited pulls. Not suitable for CD.
- GitHub Container Registry: free but doesn't have the native Azure integration that removes credential management overhead.

### 3.5 Deploy

**Only runs after successful build on `main`.** Deployment to staging is automatic; production requires manual approval.

```yaml
- name: Deploy to Container Apps (staging)
  run: |
    az containerapp update \
      --name hausly-api-staging \
      --resource-group hausly-dev-rg \
      --image $ACR_LOGIN_SERVER/hausly-api:${{ github.sha }}
```

**Pre-deployment: Run Alembic migrations**
```yaml
- name: Run database migrations
  run: |
    az containerapp job start \
      --name hausly-migrate \
      --resource-group hausly-dev-rg \
      --image $ACR_LOGIN_SERVER/hausly-api:${{ github.sha }} \
      --command "alembic upgrade head"
```

**Why migrations run before deployment (not as an init container):**
- Init containers run on every container restart (including scaling events). Migrations should only run once per deployment.
- Running as a Container Apps Job gives us: explicit success/failure status, logs, retry control, and timeout.
- If migration fails, deployment is aborted — the running app stays on the old (compatible) image.

**Post-deployment: Health check**
```yaml
- name: Verify deployment health
  run: |
    for i in {1..10}; do
      STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://hausly-api-staging.azurecontainerapps.io/api/health)
      if [ "$STATUS" = "200" ]; then exit 0; fi
      sleep 5
    done
    echo "Health check failed after 50 seconds"
    exit 1
```

**Why a health check loop (not a single check):**
- Container Apps takes 10-30 seconds to replace the old revision with the new one.
- A single immediate check would false-fail while the new container is starting.
- 10 retries × 5 seconds = 50 seconds max wait. If it's not healthy by then, something is genuinely wrong.

---

## 4. Workflow Files

### 4.1 PR Validation (`validate.yml`)

Triggers: `pull_request` to `main`

```yaml
name: Validate
on:
  pull_request:
    branches: [main]

jobs:
  api-validate:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: hausly_test
        ports: ['5432:5432']
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install dependencies
        run: |
          cd apps/api
          pip install -e ".[dev]"

      - name: Lint & format check
        run: |
          cd apps/api
          ruff check .
          ruff format --check .

      - name: Type check
        run: |
          cd apps/api
          mypy hausly/ --strict

      - name: Security scan
        run: |
          cd apps/api
          bandit -r hausly/ -ll
          pip-audit

      - name: Run migrations
        run: |
          cd apps/api
          alembic upgrade head
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/hausly_test

      - name: Run tests
        run: |
          cd apps/api
          python -m pytest tests/ -v --tb=short
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/hausly_test

  mobile-validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: apps/mobile/package-lock.json

      - name: Install dependencies
        run: |
          cd apps/mobile
          npm ci

      - name: Type check
        run: |
          cd apps/mobile
          npx tsc --noEmit

      - name: Lint
        run: |
          cd apps/mobile
          npx eslint . --max-warnings 0

      - name: Security scan
        run: |
          cd apps/mobile
          npm audit --audit-level=high

      - name: Run tests
        run: |
          cd apps/mobile
          npx jest --ci --passWithNoTests --forceExit
```

### 4.2 Deploy (`deploy.yml`)

Triggers: `push to main` (after PR merge)

```yaml
name: Build & Deploy
on:
  push:
    branches: [main]

jobs:
  validate:
    # Same as validate.yml jobs (reusable workflow call)
    uses: ./.github/workflows/validate.yml

  build-and-deploy:
    needs: validate
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4

      - name: Login to Azure
        uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Login to ACR
        run: az acr login --name hauslycr

      - name: Build and push image
        run: |
          docker build -t hauslycr.azurecr.io/hausly-api:${{ github.sha }} apps/api/
          docker push hauslycr.azurecr.io/hausly-api:${{ github.sha }}
          docker tag hauslycr.azurecr.io/hausly-api:${{ github.sha }} hauslycr.azurecr.io/hausly-api:latest
          docker push hauslycr.azurecr.io/hausly-api:latest

      - name: Run database migrations
        run: |
          az containerapp job start \
            --name hausly-migrate \
            --resource-group hausly-dev-rg \
            --image hauslycr.azurecr.io/hausly-api:${{ github.sha }} \
            --command "alembic upgrade head"

      - name: Deploy to Container Apps
        run: |
          az containerapp update \
            --name hausly-api \
            --resource-group hausly-dev-rg \
            --image hauslycr.azurecr.io/hausly-api:${{ github.sha }}

      - name: Health check
        run: |
          sleep 15
          for i in $(seq 1 10); do
            STATUS=$(curl -s -o /dev/null -w "%{http_code}" ${{ vars.API_URL }}/api/health)
            if [ "$STATUS" = "200" ]; then echo "Healthy"; exit 0; fi
            sleep 5
          done
          echo "Health check failed"
          exit 1
```

### 4.3 Dependency Audit (`audit.yml`)

Triggers: weekly schedule (catches vulnerabilities disclosed after last deploy)

```yaml
name: Dependency Audit
on:
  schedule:
    - cron: '0 9 * * 1'  # Monday 9am UTC
  workflow_dispatch:  # Allow manual trigger

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Python audit
        run: |
          cd apps/api
          pip install pip-audit
          pip-audit -r requirements.txt

      - name: Node audit
        run: |
          cd apps/mobile
          npm audit --audit-level=moderate

      # Optionally: notify via GitHub issue on failure
```

### 4.4 Mobile Release (`mobile-release.yml`)

Triggers: version tag (`v*`)

```yaml
name: Mobile Release
on:
  push:
    tags: ['v*']

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: expo/expo-github-action@v8
        with:
          eas-version: latest
          token: ${{ secrets.EXPO_TOKEN }}

      - name: Install dependencies
        run: |
          cd apps/mobile
          npm ci

      - name: Build Android (production)
        run: |
          cd apps/mobile
          eas build --platform android --profile production --non-interactive

      # iOS builds require macOS runner ($$$) or EAS Build (free tier)
      - name: Build iOS (production)
        run: |
          cd apps/mobile
          eas build --platform ios --profile production --non-interactive
```

---

## 5. Environment & Secrets Configuration

### GitHub Repository Secrets

| Secret | Purpose | Source |
|---|---|---|
| `AZURE_CREDENTIALS` | Service principal JSON for Azure CLI login | `az ad sp create-for-rbac` |
| `EXPO_TOKEN` | EAS Build authentication | Expo account settings |

### GitHub Repository Variables

| Variable | Purpose | Example |
|---|---|---|
| `API_URL` | Deployed API base URL for health checks | `https://hausly-api.azurecontainerapps.io` |
| `ACR_LOGIN_SERVER` | Container Registry server | `hauslycr.azurecr.io` |

### GitHub Environments

| Environment | Protection rules | Purpose |
|---|---|---|
| `staging` | None (auto-deploy on push to main) | Pre-production validation |
| `production` | Manual approval required | User-facing deployment |

**Why manual approval for production:**
- Solo developer: you want to verify staging works before promoting.
- Prevents accidental production deployments from a hurried merge.
- GitHub's environment protection rules enforce this with zero additional tooling.

---

## 6. GitHub Actions Minutes Budget

Monthly allowance (private repo): **2,000 minutes on ubuntu-latest.**

**Estimated usage per month:**

| Workflow | Frequency | Duration | Monthly minutes |
|---|---|---|---|
| PR Validation | ~30 PRs × 2 jobs | ~4 min/job | ~240 min |
| Build & Deploy | ~15 merges | ~8 min | ~120 min |
| Dependency Audit | 4× (weekly) | ~2 min | ~8 min |
| Mobile Release | ~2× | ~5 min | ~10 min |
| **Total** | | | **~378 min** |

**Headroom:** ~1,600 minutes unused. Sufficient even if PR frequency doubles.

---

## 7. Future Enhancements (Not in initial implementation)

| Enhancement | When to add | Reasoning |
|---|---|---|
| **Staging environment** (separate Container App) | When you have beta testers | Validate deploys before they hit production users |
| **Canary deployments** | >1K DAU | Gradually shift traffic to new revision, rollback on error spike |
| **Preview environments per PR** | When team grows beyond 1 | Each PR gets its own ephemeral API instance for testing |
| **Container image scanning (Trivy)** | Before production launch | Scan base image for OS-level CVEs |
| **Performance regression tests** | When baseline is established | Alert if P95 latency increases between deploys |
| **Database migration dry-run** | When migrations get complex | Run `alembic upgrade --sql` to preview SQL without executing |

---

## 8. Rollback Strategy

### API Rollback
Container Apps keeps previous revisions. Rollback = reactivate the previous revision:
```bash
az containerapp revision activate \
  --name hausly-api \
  --resource-group hausly-dev-rg \
  --revision <previous-revision-name>
```

### Database Rollback
- Alembic `downgrade -1` if the migration is reversible.
- If not: restore from Azure PostgreSQL point-in-time backup (granularity: any point in last 7 days).
- **Critical rule:** Never deploy a migration that destroys data (DROP COLUMN, DROP TABLE) without a separate, earlier migration that stops the code from using that column/table.

### Mobile Rollback
- EAS Update: push a new OTA update that reverts JS bundle to previous version.
- If native code changed: submit a new store build (takes 1-3 days for review).
- **Lesson:** keep native code changes infrequent and batched. JS-only changes can be hotfixed in minutes via EAS Update.

---

## 9. Implementation Steps

### Phase 1: Foundation (Day 1)
1. Add `ruff` and `mypy` to `apps/api/pyproject.toml` dev dependencies
2. Add `eslint` config to `apps/mobile/` (if not already present)
3. Create `.github/workflows/validate.yml`
4. Verify it passes on current codebase (fix any lint/type issues)
5. Create `.github/dependabot.yml`

### Phase 2: Container Registry (Day 2)
1. Create ACR via Bicep (`infra/modules/container-registry.bicep`)
2. Create Azure service principal for GitHub Actions
3. Store `AZURE_CREDENTIALS` in GitHub Secrets
4. Create `.github/workflows/deploy.yml`
5. Test: push to main, verify image appears in ACR

### Phase 3: Deployment (Day 3)
1. Configure Container Apps to pull from ACR
2. Create Container Apps Job for migrations
3. Add health check verification to deploy workflow
4. Test: full push-to-main → deploy → health check cycle
5. Create `.github/workflows/audit.yml`

### Phase 4: Mobile CI (Day 4)
1. Add mobile validation job to `validate.yml`
2. Create `.github/workflows/mobile-release.yml`
3. Configure EAS Build profiles (development, preview, production)
4. Store `EXPO_TOKEN` in GitHub Secrets
5. Test: create a tag, verify EAS Build triggers
