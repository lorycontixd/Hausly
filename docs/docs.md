This file indexes the documents inside the docs directory so AI agents can quickly choose the right source.
The 'planning' directory contains files for project planning, implementation planning, etc.. 

# docs.md
Purpose: Documentation index and entry point.
Use when: You need to understand which docs file to read first for a task.

# planning/implementation-plan-v1.md
Purpose: Step-by-step implementation plan for the MVP (v1), optimized for coding agent consumption.
Contains:
- 16 sequential phases from scaffolding through integration testing.
- Per-phase steps with inputs, outputs, and success criteria.
- Dependency graph between phases.
- Environment variable reference and constraints checklist.
Use when:
- Implementing any v1 feature — follow the phase order.
- Checking what to build next.
- Verifying implementation completeness.

# planning/hausly-project-master-plan.md
Purpose: Primary product and architecture plan (living decision document).
Contains:
- Product vision, target users, and differentiation strategy.
- Versioned roadmap (v1, v2, v3), including explicit deferred and dismissed features.
- Cross-cutting non-negotiable rules (for example: all financial mutations require explicit user confirmation).
- Group lifecycle flows, technical stack decisions, cost constraints, AI strategy, monetization, risks, open questions, and a decision log.
Use when:
- Making product or architecture choices.
- Evaluating whether a request is in scope or conflicts with prior decisions.
- Implementing features that must follow established constraints.

# project-structure.md
Purpose: Target monorepo layout reference.
Contains:
- Proposed folder/file structure for apps, packages, infra, docs, and CI workflows.
- Short role notes for key files and modules.
Use when:
- Creating new files or directories in the repo.
- Checking where a new component, service, module, or infrastructure file should live.

# project-tree.html
Purpose: Interactive HTML visualization of the same target repository structure.
Contains:
- Expand/collapse tree view.
- Color legend by file type and inline notes for important paths.
Use when:
- You need a quick visual scan of the intended structure.
- Reviewing structure interactively in an editor/browser.

# data-models.md
Purpose: Core database entities, their properties, relationships, and household-scoped constraints.
Use when:
- Designing or modifying database tables.
- Implementing models, schemas, or migrations.
- Checking entity ownership rules (user-level vs household-level).

# database-local.md
Purpose: Local PostgreSQL setup via Docker Compose, lifecycle commands, and test fixture strategy (transaction rollback).
Use when:
- Setting up or running the local database.
- Writing or debugging pytest fixtures for database tests.
- Checking how test isolation works (transaction rollback pattern).
- Verifying that local setup matches production (version, RLS, migrations).

# signalr-architecture.md
Purpose: Real-time architecture using Azure SignalR Service in serverless mode.
Contains:
- Architecture diagram showing client ↔ SignalR Service ↔ FastAPI data flow.
- Connection flow (negotiate, token generation, group assignment via JWT claims).
- REST API patterns for broadcasting from the backend to household groups.
- Token signing details (client token and server token).
- Technology decisions and failure handling strategy.
Use when:
- Implementing the SignalR negotiate endpoint or broadcast service (Phase 7).
- Understanding how real-time events flow from backend to mobile clients.
- Debugging WebSocket connection issues.

# api-reference.md
Purpose: Endpoint-by-endpoint API behaviour reference (REST and WebSocket).
Contains:
- Route paths, methods, request/response schemas, auth requirements, and real-time event contracts.
Use when:
- Implementing or consuming API endpoints.
- Verifying request/response shapes and auth guards.
- Checking real-time event names and payloads.

# logics/ (directory)
Purpose: Detailed behaviour explanations for complex app features.
Contains files that describe how specific features work end-to-end: data flow, algorithms, integration chains, and frontend expectations.
Use when:
- Implementing a feature whose logic spans multiple modules or has non-obvious rules.
- Understanding how data flows across module boundaries (e.g. grocery → expense).
- Checking expected frontend behaviour for a feature.

Files:
- logics/expense-splits.md — Split modes, balance calculation, settlement algorithm, draft→confirm flow, grocery integration, and frontend screen designs.
- logics/grocery-session.md — Shopping session lifecycle, client-side state, session completion, expense creation, personal item handling, offline behaviour, and simultaneous shopping.
- logics/chore-schedule.md — Per-chore recurrence model, rotation logic, assignment generation, overdue blocking, postpone/cancel, member departure, and frontend design.

# planning/global-actions-plan.md
Purpose: Implementation plan for the global header action buttons (user avatar + three-dots menu).
Contains:
- Route structure for `(modals)` group (profile, recipes, preferences, dev-info).
- GlobalActions component design and wiring.
- User settings brainstorm (10 candidates for future implementation).
Use when:
- Adding user-level features to the header or modal screens.
- Implementing user preferences or profile editing.
- Referencing the three-dots menu structure.

# design-system.md
Purpose: Mobile design system specification ("Soft Pop" theme).
Contains:
- Color palette (brand, surfaces, text, semantic, module accents).
- Typography scale, spacing tokens, border radius, shadow levels.
- Key UI patterns (module header tints, FABs, status chips, sheets).
- Icon library choice and haptics policy.
Use when:
- Implementing or styling mobile UI components.
- Adding new module screens (reference module accent colors).

# security.md
Purpose: Security requirements and implementation guide for production readiness.
Contains:
- Current security posture assessment (what exists vs what's missing).
- Secret management (Azure Key Vault) implementation guide.
- API rate limiting configuration and reasoning.
- Dependency vulnerability scanning tools (Dependabot, pip-audit, npm audit, bandit).
- Security headers, request size limits, audit logging.
- Input validation hardening checklist.
- Account deletion and GDPR compliance requirements.
- Threat model (STRIDE) and pre-production security checklist.
Use when:
- Implementing security hardening features.
- Preparing for production deployment.
- Adding rate limiting or input validation.
- Setting up Key Vault or CI security scanning.

# ci-cd-plan.md
Purpose: CI/CD pipeline design and implementation plan using GitHub Actions.
Contains:
- Trigger strategy (PR validation, deploy on merge, scheduled audits, mobile releases).
- Stage details with reasoning: lint, test, security scan, build, deploy.
- Full workflow YAML files (validate, deploy, audit, mobile-release).
- Environment and secrets configuration.
- GitHub Actions minutes budget estimation.
- Rollback strategy for API, database, and mobile.
- Implementation phases (4-day plan).
Use when:
- Setting up or modifying CI/CD workflows.
- Adding new pipeline stages or tools.
- Debugging deployment failures.
- Understanding the deployment flow from PR to production.

# planning/services-implementation-plan.md
Purpose: Master implementation plan for all production-readiness services (monitoring, security, analytics, DevOps).
Contains:
- Priority-ordered list of all services to implement.
- Azure Application Insights setup (observability).
- Firebase Crashlytics setup (mobile crash reporting).
- Azure Key Vault implementation (secret management).
- API rate limiting configuration with reasoning per endpoint category.
- Firebase Analytics deep integration (events, user properties, funnels).
- CI/CD pipeline overview and cost summary.
- Health check monitoring and alerting rules.
- Deferred items: push notifications, GDPR, custom domain, OTA updates.
- Full cost breakdown (fits within €50/month budget).
Use when:
- Deciding what to implement next for production readiness.
- Understanding cost implications of service choices.
- Implementing monitoring, analytics, or security features.
- Checking integration dependencies between services.
- Making design decisions for v1 mobile phases (11–16).

# infrastructure-setup.md
Purpose: Step-by-step cloud environment setup guide (Firebase + Azure) with Bicep deployment instructions.
Contains:
- Architecture diagram showing all cloud services and their relationships.
- Firebase Auth setup steps (manual, per environment).
- Azure resource provisioning via Bicep (dev and prod environments).
- Post-deployment configuration (Key Vault secrets, connection strings).
- Azure OpenAI setup guide (requires separate approval).
- Dev vs Prod tier comparison table with cost estimates.
- Troubleshooting guide for common deployment issues.
Use when:
- Setting up the cloud environment for the first time.
- Deploying infrastructure changes.
- Understanding how dev and prod environments differ.
- Debugging Azure resource configuration.
- Onboarding a new developer to the infrastructure.

## Agent Guidance
1. Read docs.md first.
2. For product scope, constraints, and decision checks, use planning/hausly-project-master-plan.md as the source of truth.
3. For placement of code and repository layout, use project-structure.md.
4. Use project-tree.html as a visual companion, not as the canonical written policy source.
5. For database schema details, use data-models.md.
6. For API contracts and endpoint behaviour, use api-reference.md.
7. For feature logic and cross-module behaviour, check logics/ directory.