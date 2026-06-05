# Hausly — Companion App for Shared Living

> **Document type:** Brainstorming & Design Plan (not implementation-ready)
> **Status:** Active ideation — all decisions are provisional and open to revision
> **Author:** Lorenzo (developer) + Claude (brainstorming partner)
> **Last updated:** May 2026

---

## 1. Product Vision

### 1.1 Core Concept

Hausly is an all-in-one companion app for people who share a living space. It targets any household configuration — couples, friends, university students, workers in shared flats, families — and provides an integrated suite of modules for organizing shared life: groceries, expenses, meal planning, chores, and household communication.

### 1.2 Key Insight — Why This App Exists

The market has strong single-purpose apps (Splitwise for expenses, AnyList for groceries, Sweepy for chores), but no app treats the household as a unified system. The real value isn't in any individual module — it's in **cross-module intelligence**. A grocery list auto-populated from the meal plan. An expense split that factors in who cooked for whom. A chore rotation that respects who's away. This integration layer is what no single-purpose competitor can offer.

### 1.3 Target Audience

The app must be **general-purpose** across household types:

| Household Type | Characteristics | Key Needs |
|---|---|---|
| **Couples** | 2 people, fluid finances, high trust | Lightweight expense tracking (running balance, not itemized), shared groceries, meal planning |
| **Friends / Flatmates** | 3–6 people, transactional finances, medium trust | Precise expense splitting, chore rotation, clear communication |
| **University Students** | 3–8 people, high turnover, tight budgets | Strict expense tracking, chore enforcement, group management (join/leave flows) |
| **Families** | 2–6 people, hierarchical, mixed ages | Parental admin control, kid-friendly chore mode, meal planning |

During onboarding, the group self-identifies its type. This sets **smart defaults** (which modules are enabled, how strict expense tracking is, notification frequency, UI tone) but everything remains **overridable** by the group admin.

### 1.4 Differentiation — What Makes This Sellable

1. **Integration as the product.** Module crosstalk is the moat. Competitors can't replicate it without rebuilding the whole suite.
2. **AI as an enhancement layer, not a gimmick.** Receipt scanning, meal suggestions, natural language input — practical features, not chatbot theater.
3. **Group-type awareness.** Smart defaults per household type, so the app feels tailored without requiring too much manual configuration.
4. **Customizable module system.** Groups enable only what they need. This prevents overwhelm and creates a natural pricing axis.

---

## 2. Feature Set & Module Hierarchy

### 2.1 Release Roadmap

#### MVP (v1) — The Reason People Download the App

Three modules chosen to cover the highest-frequency pain points **and** demonstrate the cross-module integration thesis from day one. The integration chain — meal plan → grocery list → expense split — is the showpiece of v1.

**1. Shared Grocery List**
- Real-time sync: when one flatmate checks off an item, everyone sees it instantly
- Quantity tracking and unit support
- Duplicate detection (case-insensitive name match within the active list)
- **Personal items:** items can be marked as personal (belonging to a specific user). Personal items appear in the shared list with a visual marker but are excluded from expense generation. Personal items can be set as visible (all members see them) or hidden (only the owner sees them).
- **Shopping session:** a client-side mode where the user checks items as they shop. On "Done" button press:
  1. Checked non-personal items are removed from the list
  2. User is prompted for the receipt total amount
  3. A draft expense is created with the receipt total, items listed as description context, and an equal split across all household members
  4. User reviews and confirms the draft expense (per §2.3)
- **"Clear list" function:** archives the entire current list for reference (separate from shopping session — requires confirmation). Does not trigger expense generation.
- **Integration with Expense Tracker:** shopping session completion flows into an expense entry with a suggested split (user confirms before committing — see §2.3)
- **Integration with Meal Planner:** meal plan entries can push ingredients to the grocery list
- Must work offline with sync-on-reconnect (people shop in stores with poor reception — see §7.4)
- AI grocery suggestions based on past purchases and meal plans deferred to v3

**2. Shared Expense Tracker**
- Core features: log expenses, tag categories, assign payers and participants, support uneven splits
- Recurring expenses: rent, utilities, subscriptions (auto-generated monthly entries)
- Settlement suggestions: "Lorenzo pays Maria €12.30 to settle up" (minimize transaction count)
- Outstanding balance summary on home screen
- **Integration with Grocery List:** grocery purchases auto-suggest expense entries
- **Group-type customization:** couples default to a relaxed running balance; flatmates/students default to itemized tracking. Both configurable.

**3. Meal Planner (Simple — Diary Style)**
- Weekly view with slots for lunch and dinner for each day
- Free-text entry per slot: users write whatever they plan to eat, as if filling in a diary ("Pasta al pomodoro", "Leftovers", "Eating out")
- Headcount per meal: how many people are eating in tonight? Always shown; defaults to household member count. Users adjust in the moment.
- **Slot ownership:** first member to claim a slot owns it. Only the owner (or an admin) can edit or delete that entry. Disputes are resolved offline between flatmates — the app does not mediate.
- If the entry owner leaves the household, their future meal entries are auto-deleted. Past entries are retained as historical record.
- **Text-only entries have no grocery integration** — this is by design. The cross-module chain activates only when a meal entry has ingredients attached (v2+).
- Recipe book and ingredient-based grocery integration: **introduced in v2** (manual entry and saved recipes, no AI)
- AI-assisted ingredient generation and recipe import from URLs: **deferred to v3**

*Note on chores in v1:* The full chore system (per-chore recurrence, rotation, overdue blocking) ships in v1. Fairness scoring and chore trading are v2 features. This keeps v1 scope manageable while the cross-module story (grocery ↔ expense ↔ meal plan) is the primary v1 thesis.

**Chore System (v1 — Per-Chore Recurrence Model)**
- Each chore is an independent entity with its own recurrence and assignees
- Any member can create a chore (must include themselves as an assignee)
- Chores can be one-off or recurring (every N days/weeks/months)
- Multiple assignees can share a chore: either rotating or all-do-it
- Rotation: each occurrence assigns to the next person in the ordered list
- Anyone can mark any chore as done (credit to completer, not assignee)
- Overdue assignments block future generation until resolved (done, postponed, or cancelled)
- Any member can delete any chore
- Consent is implicit; anyone-can-delete is the safety valve
- On member leave: auto-removed from assignee lists, future assignments deleted, rotation recomputes

#### v2 — Retention & Stickiness

**Chore Management (full)**
- Fairness scoring: visible metric showing who's pulling their weight over time (based on completed_by data from v1)
- Chore trading: flatmates can swap assigned occurrences
- "Skip me this week" manual away flag — temporarily skips member in rotation for a set period
- Gentle nudge notifications (tone matters — not aggressive)

**Pinboard (Household Notice Board)**
- Virtual pinboard metaphor — not a chat, doesn't compete with WhatsApp
- Timestamped notes visible to all members
- Photo attachments (broken appliance, WiFi password, parking rules)
- **Notes are permanent by default.** Temporary notes (e.g. "I'll be home late Thursday") can opt into an expiry duration set at creation time. No silent auto-archival of permanent notes.
- Ability to pin important notes (persist prominently, no expiry)
- No threads, no reactions, no read receipts — intentionally minimal

**Meal Planner — Recipe Book (v2, manual)**

The recipe layer ships in v2 as a manual, no-AI feature. It introduces the full cross-module chain: recipe → meal entry → grocery list → expense split.

*Recipe ownership and storage:*
- Recipes are **user-level**, not household-level. Each user has their own personal recipe book.
- Any member can view and save a copy of another member's recipe to their own book. Saving creates an **independent fork** — the saver can edit freely without affecting the original author's version.
- Recipes travel with the user: when they leave a household, their recipe book stays theirs.

*Recipe structure:*
- Recipe name
- Base serving count (set at creation, e.g. "serves 4") — displayed prominently so users can scale manually
- Ingredient list: name, optional quantity, optional unit. Quantities without a numeric value (e.g. "olive oil", "salt to taste") are added to the grocery list as-is without scaling.
- Free-text notes/instructions (optional — Hausly is not a cooking app, just a planning one)
- In-app quantity scaling (adjust serving count → quantities recalculate proportionally) — added in v2 alongside recipe creation

*Linking to meal entries:*
- A meal diary entry can remain text-only OR be linked to a saved recipe
- When linked to a recipe, a toggle appears on the entry: "Add ingredients to grocery list"
- The toggle is invisible on text-only entries — no clutter for households that don't use recipes
- Toggling on pushes all recipe ingredients to the household grocery list, scaled to the meal entry's headcount
- Partial filtering (e.g. "I already have garlic") is handled in the grocery list itself, not here

*Weekly shopping list generation:*
- A "generate shopping list" action covers the full week's meal plan: consolidates all ingredient pushes across all meal entries into one pass, merging duplicate items and summing quantities where possible
- The user reviews the consolidated list before it is added to the grocery list

*Starter recipes:*
- A small set of pre-populated example recipes is shown on first use of the recipe book (editable and deletable)
- These reduce the cold-start friction of an empty recipe book and let users experience the grocery integration immediately
- The starter set will become more personalised and powerful with AI integration in v3

#### v3 — Differentiation & Premium

**Meal Planner — Recipe Layer (AI-assisted)**
- AI ingredient proposal: user types a recipe name → AI suggests a plausible ingredient list as a draft in the normal recipe editor. The user edits and confirms — the AI is not authoritative, recipes vary. This is a proposal, not a prescription.
- Recipe import from URL: user pastes a recipe website URL → AI extracts and parses the ingredient list into the recipe editor as a draft for review and confirmation
- AI meal suggestions: generate a weekly meal plan from constraints (dietary preferences, available ingredients, headcount per day) — produces diary entries the user can accept, edit, or replace
- Starter recipe personalisation: AI suggests a tailored starter set based on group type, dietary preferences, and usage patterns rather than a fixed default list

**AI-Powered Features**
- Smart receipt scanning: photograph receipt → OCR → item extraction → expense entry with suggested split
- AI computer vision for grocery session: scan items visually to auto-check them from the list (experimental, v3+)
- Meal suggestions: generate weekly meal plan from constraints (available ingredients, dietary prefs, headcount per day)
- Natural language grocery input: "We need milk, eggs, and that pasta sauce Maria liked" → AI parses intent, resolves references against history, adds items to grocery list
- AI grocery suggestions: smart additions based on past purchases, current meal plan, and seasonal patterns
- Fairness analysis: surface spending/chore imbalances with gentle, actionable insights (extreme tonal care required)

**Analytics Dashboard**
- Outstanding balances at a glance
- Spending trends over time by category
- Chore completion rates and fairness metrics per member
- Household "health" score synthesising expense fairness, chore completion, participation — must be playful, not punitive. Needs user testing before shipping.

### 2.2 Features Explicitly Deferred or Dismissed

| Feature | Status | Reasoning |
|---|---|---|
| Full shared calendar | **Dismissed** | Most people already use Google/Apple Calendar. Massive effort, low differentiation. If ever needed: lightweight "who's home when" overlay syncing via CalDAV/Google Calendar API. |
| Move-in/move-out flow | **Replaced** | Too narrow — only applies to student-style cycling. Replaced by generic group invitation/exit flow (§3). |
| Household chat | **Dismissed** | Competes with WhatsApp/Telegram and loses. Pinboard covers the communication need without recreating messaging. |
| Predictive grocery ordering | **Deferred to v4+** | Data requirements enormous; prediction accuracy for small households will be poor. Revisit once large-scale usage data exists. |
| AI chatbot assistant | **Dismissed** | Users don't want to converse with the app. Well-designed direct manipulation UI > chatbot interface for utility apps. |
| Recipe book — manual (v1) | **Deferred to v2** | v1 meal planning is diary-style free text only. Manual recipe creation and saved recipe book introduced in v2. |
| Recipe book — AI-assisted (v2) | **Deferred to v3** | AI ingredient generation and URL import are v3 premium features. |
| Payment integration (in-app) | **Deferred** | Settlement stays external (bank transfer, cash, Revolut). Stripe Connect is the natural future path if built (Option C monetization). |
| Web app | **Deferred / possibly unnecessary** | Mobile-first priority. Revisit only if user research reveals a strong laptop use case. |

### 2.3 Cross-Cutting Design Principles

**All financial mutations are user-confirmed, never automatic.**
Every AI-suggested split, auto-generated recurring expense, and grocery→expense integration produces a draft that the user reviews and explicitly confirms before committing. No silent writes to financial data. This is a UX constraint that applies across all modules and all versions.

**Smart defaults, not smart visibility.**
Sub-features within a module are always present when the module is enabled — they are not hidden or disabled based on household size or inferred context. Instead, group type and size set sensible default values that users override in the moment. This keeps the settings surface clean and avoids fragile inference rules that break on edge cases. The app cannot model every real-world situation; in-person agreement handles what the app cannot.

Example: headcount in the meal planner is always shown and always defaults to the current household member count. A couple planning dinner for guests adjusts it manually. No rule needed.

### 2.4 Module Customization System

- During onboarding, groups select which modules to enable
- Module suggestions based on group type (smart defaults), fully overridable by admin
- Modules can be toggled on/off at any time by group admins
- Tiered pricing axis: more modules = higher tier
- New modules appear as "available to enable" — gentle in-app upsell surface
- Module on/off is the only manual toggle exposed at settings level — no sub-feature toggles

---

## 3. Group Lifecycle & User Management

### 3.1 Group Creation & Onboarding

1. Creator signs up (OAuth — Google/Apple sign-in)
2. Creator names the household and selects group type (couple / friends / students / family / custom)
3. App suggests module configuration based on group type; creator can override → pricing tier determined by active modules
4. Creator receives a shareable invite link + short alphanumeric invite code

### 3.2 Joining a Group

- Enter invite code → preview screen shows household name and member count → confirm to join
- **Join flow:** `GET /invites/{code}/preview` returns household name + member count (unauthenticated). On confirm: `POST /households/join { invite_code }` creates membership. Server resolves household from code.
- **Zero context required:** no tutorial wall, no onboarding quiz. First screen shows the grocery list or expense summary — immediately legible.
- Roles: **admin** (full control: manage members, modules, settings) vs **member** (uses modules, cannot change group settings)
- Inviter can pre-assign a role before sending the link
- **Single household constraint (v1):** a user can only belong to one household at a time. Joining a new household requires leaving the current one first (guided leave flow). The data model supports many-to-many for future multi-household support, but v1 enforces single membership at the application level.

### 3.3 Leaving a Group

Leaving is an **explicit user action**, not a passive event. The system does not need to "detect" that someone is leaving. "Leave Group" is a button in settings that triggers a **blocking guided flow** before the leave is finalised. The user remains fully in the group until the final confirmation step.

**Flow for a member leaving voluntarily:**
1. Member navigates to Settings → presses "Leave Group"
2. App intercepts and begins the guided flow (member is still in the group throughout)
3. Step 1 — Expenses: surface all unsettled balances. Options per balance: "Settle now" (marks as resolved, prompts external payment reminder) or "Mark as forgiven" (writes off the amount)
4. Step 2 — Chores: surface any chore assignments due. Options: reassign to another member, or mark as unassigned
5. Step 3 — Confirmation: "You're about to leave [Household Name]. This cannot be undone." → confirm
6. On confirm: membership removed server-side, access to new data revoked immediately
7. Historical data (past expenses, past chore completions) retains the member's name permanently — it is an accurate record

**Admin-initiated removal:**
When an admin removes another member, the same guided flow is presented to the admin before the removal is committed. The admin resolves the departing member's outstanding items on their behalf.

**Edge cases:**
- **Admin leaving:** before leaving, the admin must either transfer admin role to another member or confirm that the household will have no admin (in which case the longest-standing member is auto-promoted). Critically: the admin must also transfer the subscription to another member before leaving (see §6.1).
- **Last person leaving:** household data is archived. New households start fresh.
- **Uninstall / account deletion without going through the flow:** a server-side cleanup job flags the household as having unresolved balances and surfaces it to remaining members on their next app open.

### 3.4 Inactive Members

- An inactive member's data persists; they can return at any time without data loss
- Active members are not penalised by another member's inactivity
- For chores: anyone can mark any chore as done. Credit goes to whoever marks it, not the originally assigned person. A "completed by [name]" tag is added to the log entry for transparency.
- A manual "skip me this week" away flag (v2) lets members remove themselves from chore rotation for a defined period — covers holidays, illness, etc.
- Automatic inactivity detection is not implemented — over-engineered for the current scope.

---

## 4. Architecture & Technical Stack

### 4.1 Guiding Constraints

- **Budget:** €50/month Azure credits (through Avanade). Minimize additional out-of-pocket spend.
- **Team size:** solo developer (side project with business ambitions)
- **Time to market:** 3–4 months to MVP, then iterate on user feedback. Favour shipping over perfection.

### 4.2 Stack Decision Summary

All layers were evaluated comparatively before choosing. Rationale is preserved here so future sessions start from a decided baseline.

**Client**

| Option | Verdict | Key reason |
|---|---|---|
| **React Native + Expo** | ✅ Chosen | Largest ecosystem, Expo removes DevOps burden, TypeScript transfers to other projects, market standard for consumer mobile |
| Flutter | Viable fallback | Dart ≈ C# (lower learning curve), excellent UI renderer — use if TypeScript/RN friction is prohibitive |
| .NET MAUI | Rejected | Immature ecosystem, known tooling instability for consumer apps (confirmed by prior Chore Companion experience) |
| PWA | Rejected | iOS hostile — background sync unreliable, push notification gaps, non-obvious install |

**Backend**

| Option | Verdict | Key reason |
|---|---|---|
| **FastAPI (Python)** | ✅ Chosen | Best-in-class Python AI ecosystem; familiar from Mapei work; minimal boilerplate; modern async |
| ASP.NET Core | Strong alternative | C# type safety excellent, SignalR native — but AI tooling ecosystem lags Python meaningfully |
| NestJS (TypeScript) | Considered | Full-stack TS sharing appealing in theory; decorator overhead adds ceremony for a solo developer |
| Express.js | Rejected | Too minimal — rebuilds structure that FastAPI provides for free |

**Database**

| Option | Verdict | Key reason |
|---|---|---|
| **PostgreSQL on Azure Flexible Server** | ✅ Chosen | Correct relational model, RLS multi-tenancy, covered by Azure credits, Alembic migrations |
| Cosmos DB | Rejected | Document model fights the relational domain; unpredictable RU-based pricing; no joins |
| Firebase Firestore | Rejected | Same document model problem; complex expense/chore queries painful; outside Azure credits |
| Supabase (Postgres SaaS) | Considered | Identical model + built-in RLS + built-in Realtime — would win if Azure credits didn't cover equivalent |

**Real-time**

| Option | Verdict | Key reason |
|---|---|---|
| **Azure SignalR Service** | ✅ Chosen | Managed, zero ops, covered by credits, automatic scaling |
| Socket.io (self-hosted) | Valid alternative | Free in Container App, but horizontal scaling needs Redis backplane — comparable cost at scale with added ops |
| Supabase Realtime | Not applicable | Only worthwhile if using Supabase for DB |
| Firebase RTDB | Rejected | Splits the database layer unnecessarily |

### 4.3 Client — React Native + Expo

- **Framework:** React Native with Expo managed workflow
- **Language:** TypeScript
- **State management:** Zustand or Jotai (lightweight, modern)
- **Server state:** TanStack Query (React Query) for caching and sync
- **Offline support:** expo-sqlite for local-first data layer
  - Grocery list: `pending_operations` queue for offline mutations. On reconnect: upsert (case-insensitive dedup). Additions win over deletions.
  - Shopping session: stored locally, completed on reconnect.
  - CRDT-based merge for the grocery list (Yjs or Automerge) deferred to v1.1 — the concurrent offline edit conflict is rare enough in a household context for v1.
- **Push notifications:** Expo Notifications (backed by FCM for Android, APNs for iOS)

### 4.4 Backend — FastAPI on Azure Container Apps

- **Framework:** FastAPI (Python, async)
- **ORM:** SQLAlchemy or SQLModel + Alembic for migrations
- **Hosting:** Azure Container Apps
  - Chosen over Azure Functions: persistent WebSocket connections needed for real-time
  - Scale-to-zero keeps costs low during off-peak
  - Container-based deployment (familiar from Mapei work)
- **API design:** RESTful for CRUD operations + WebSocket endpoints for real-time features

### 4.5 Database — Azure Database for PostgreSQL (Flexible Server)

- **Tier:** Burstable B1ms (~€13–15/month)
- **Model:** Relational (household memberships, expense splits, chore assignments are fundamentally relational)
- **Multi-tenancy:** shared database with `household_id` foreign key on every table; Row-Level Security (RLS) policies for tenant isolation. NOT schema-per-household.

**Core entities (preliminary):**

```
Household
HouseholdSettings     (1:1 with Household — default_currency, enabled_modules, notification_level)
User
HouseholdMembership   (many-to-many, includes role: admin/member — v1 enforces single active membership)
Expense
ExpenseSplit          (per-participant share of an expense)
Chore                 (per-chore definition: name, recurrence, rotation)
ChoreAssignee         (ordered list of members for a chore)
ChoreAssignment       (generated instance: due_date, status, completed_by)
GroceryList
GroceryItem           (includes is_personal, personal_for_user_id, personal_visibility)
MealPlanEntry         (day, slot: lunch/dinner, text, headcount, owner_user_id, linked_recipe_id nullable)
Recipe                (user-level: owner_user_id, name, base_servings — v2)
RecipeIngredient      (recipe_id, name, quantity nullable, unit nullable — v2)
PinboardNote
```

Note on Recipe ownership: recipes belong to a user (`owner_user_id`), not a household. When another user saves a copy, a new Recipe row is created with their `owner_user_id` — a full fork, not a reference. The `linked_recipe_id` on `MealPlanEntry` references the saving user's own copy.

### 4.6 Real-Time — Azure SignalR Service

- **Purpose:** live grocery list updates, expense notifications, chore completions, meal plan changes, pinboard updates
- **Tiers:** Free (20 concurrent / 20K msg/day) for development; Standard (~€13/month, 1K concurrent) for production
- **Protocol:** WebSocket (bidirectional)

### 4.7 Storage — Azure Blob Storage

- Receipt photos, recipe images (v3), profile pictures, pinboard photo attachments
- Cost negligible at early scale (cents/month)

### 4.8 AI — Azure OpenAI

- **Model:** GPT-4o-mini for all structured tasks (receipt OCR, meal generation, NLP input parsing, ingredient extraction from URLs)
- **Cost estimate:** ~€0.01–0.03 per receipt scan, ~€0.02–0.05 per meal plan generation
- **Provider abstraction:** AI calls are encapsulated behind a single `AIService` class in the backend. All provider-specific SDK calls live inside this class. The active provider is configured via environment variable. Swapping providers (e.g. from Azure OpenAI to Anthropic) means updating the `AIService` implementation and the env var — no changes elsewhere in the codebase. No external abstraction library (e.g. LiteLLM) is used.
- **Rate limiting:** AI features are premium-tier only. Free tier = manual entry. Paid tier = smart OCR, meal suggestions, NLP input, ingredient extraction.

### 4.9 Auth — Firebase Auth

- **Chosen:** Firebase Auth
- Free tier covers the app's scale for a long time
- Native Google/Apple sign-in support
- Mature React Native SDK, well-documented JWT verification for FastAPI backends
- **Why not Azure AD B2C:** XML-based policy configuration, poor DX for consumer apps, over-engineered for this use case
- **Why not Supabase Auth standalone:** documentation assumes full Supabase stack; less community precedent in non-Supabase backends
- **Invite system:** shareable link + short alphanumeric code. Flow: auth → code/link validation → household membership created server-side.

### 4.10 Estimated Monthly Azure Spend

| Service | Tier | Est. Cost |
|---|---|---|
| Azure Database for PostgreSQL (Flexible) | Burstable B1ms | ~€15 |
| Azure Container Apps | Consumption (scale-to-zero) | ~€0–5 |
| Azure SignalR Service | Standard (1 unit) | ~€13 |
| Azure Blob Storage | Hot tier, minimal usage | ~€1 |
| Azure OpenAI (GPT-4o-mini) | Pay-per-token | ~€5–15 |
| **Total** | | **~€34–49** |

Fits within €50/month Azure credit. Firebase Auth is free-tier, adding no cost.

---

## 5. AI Integration Strategy

### 5.1 Philosophy

AI is a **practical enhancement layer**, not the product identity. The app is "a household companion that uses AI to reduce friction," not "an AI-powered household app." This positioning matters:
- Most households won't pay a premium for AI features alone
- AI costs scale linearly with usage (token costs)
- The core value — integrated household management — must stand without AI

AI features are the premium differentiator: the reason to upgrade from free to paid.

### 5.2 Planned AI Features

| Version | Feature | Description | AI Cost/Use | Priority |
|---|---|---|---|---|
| v3 | **Receipt scanning** | Photo → OCR → item extraction → expense entry with split suggestion | €0.01–0.03 | High (flagship) |
| v3 | **Ingredient extraction** | Paste a recipe URL → AI extracts and parses ingredient list as a draft in the recipe editor for user review and confirmation. Type a recipe name → AI proposes a plausible ingredient list as a draft. AI is not authoritative — output is always a proposal the user edits. | €0.01–0.02 | High |
| v3 | **Meal suggestions** | Generate weekly meal plan from constraints (ingredients available, dietary prefs, headcount per day) | €0.02–0.05 | Medium |
| v3 | **Natural language grocery input** | "We need milk and that sauce Maria liked" → parsed into structured items with history-aware reference resolution | €0.005–0.01 | High (UX) |
| v3 | **Grocery suggestions** | Smart additions based on past purchases, current meal plan, seasonal patterns | €0.005–0.01 | Medium |
| v3 | **Fairness analysis** | Surface spending/chore imbalances with gentle, actionable insights | Negligible | Low (tonal risk) |

### 5.3 AI Features Explicitly Avoided

- **AI chatbot / household assistant:** direct manipulation UI is always better for utility tasks
- **Predictive grocery ordering:** insufficient data at household scale for reliable predictions — v4+ only
- **AI chore scheduling without preferences:** humans set preferences; AI optimises within constraints only
- **Automatic financial mutations:** AI suggestions are always drafts requiring user confirmation (see §2.3)

### 5.4 Cost Management

- Free tier: manual entry only, no AI features
- Paid tier: AI features with rate limits (e.g. 30 receipt scans/month, 4 meal plan generations/month, 20 ingredient extractions/month)
- Cache common outputs (popular meal suggestions, common ingredient lists) to reduce redundant API calls
- Always use cheapest sufficient model — GPT-4o-mini for structured tasks, not GPT-4o

---

## 6. Monetization & Business Model

### 6.1 Pricing Model — Freemium, Per-Household

**Billing model: Option A — household owner pays.**
The admin/creator pays a single subscription that applies to all household members. Members join for free. Cost-sharing with flatmates happens externally (cash, bank transfer, or via Hausly's own expense tracker).

- This is how most shared subscriptions work in practice (Netflix, Spotify Family) — users are conditioned to it
- Zero friction for joining members
- No payment infrastructure complexity at launch

Risk: churn concentrates on the paying admin. Mitigation: **subscription transfer is required** when the admin leaves the group (§3.3 leaving flow). The admin cannot complete the leave flow without either transferring the subscription or cancelling it.

**Future path — Option C:** if the "admin bears all risk" problem proves significant in practice, build an in-app contribution request (Stripe Connect): admin pays, optionally sends a payment request to each member for their share. Members can pay in-app or mark as settled externally. This adds payment infrastructure but removes the social awkwardness. Deferred until there is user evidence that it's needed.

**Tier structure:**

- **Free tier:**
  - 1 household, up to 4 members
  - Core modules: grocery list, expense tracker, simplified chore list, meal planner (diary-style, no AI)
  - No AI features
  - Basic module features only

- **Paid tier (price TBD — market research required):**
  - Unlimited members
  - All modules (full chores, pinboard, meal planner with recipe layer)
  - AI features (receipt scanning, ingredient extraction, meal suggestions, NLP input)
  - Analytics dashboard
  - Priority support

- **Future tier:** families (parental controls, kid profiles), power users (API access) — not designed yet

### 6.2 Growth & Distribution

- App Store + Google Play (mandatory for launch)
- Viral loop: the app inherently requires inviting flatmates to function. Every new household creates N invite opportunities. Invite → join flow must be under 30 seconds.
- Web app: deferred, possibly unnecessary — mobile-first throughout

---

## 7. Scalability Considerations

Scalability is a consideration, not a priority. Optimise for speed to market in early stages. Make architectural choices that allow scaling when needed without over-engineering upfront.

### 7.1 Real-Time Connections

At 10,000 households × 3 members average = 30,000 potential concurrent connections. Azure SignalR Standard (1 unit) handles 1,000 concurrent. Scale units linearly as needed (~€13 per 1K additional concurrent connections).

### 7.2 AI Token Costs

Grow linearly with usage. Mitigations: rate limits per household per month, cache common outputs, cheapest sufficient model, monitor and adjust tier limits. AI is premium-only — free tier generates no AI costs.

### 7.3 Database

PostgreSQL Flexible Server scales vertically for a long time before needing horizontal approaches. Read replicas if analytics queries become a bottleneck. PgBouncer connection pooling (built into Flexible Server) essential as concurrent users grow.

### 7.4 Offline Sync

- **Grocery list editing (add/remove/update):** mutations are queued locally in a `pending_operations` queue (stored in expo-sqlite). On connectivity restoration, queued operations are **upserted** to the server: existing items are matched by case-insensitive name and skipped; new items are added. Additions always win over deletions — if an item exists server-side on reconnect, it is not deleted by a queued offline deletion (low-stakes: worst case an item reappears).
- **Shopping session while offline:** checked items and the "Done" action are stored locally. A message informs the user that the operation will complete on connectivity restoration. On reconnect: items are marked as bought server-side, the draft expense is created, and the flow continues normally.
- **Expense tracker:** no offline creation in any version. Financial data confirms server-side only.
- **Conflict resolution:** upsert-based for grocery (not last-write-wins). Timestamp-based last-write-wins for meal planner entries only.
- **CRDT-based merge** for the grocery list (Yjs or Automerge) deferred to v1.1. The concurrent offline edit conflict is rare enough in a household context that upsert logic is sufficient for v1.

---

## 8. Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| **Over-implementation / feature bloat** | High | Module system with group-level customization. Ship MVP with 3 modules (grocery, expense, meal planner + simplified chores). Add incrementally. |
| **Building mediocre versions of 5 good apps** | High | Each module must be ≥70% as good as the best dedicated alternative. Strong emphasis on integration as the differentiator — that's what dedicated apps cannot match. |
| **Cross-module story not felt in v1** | High | Explicitly addressed in MVP design: grocery ↔ expense ↔ meal plan integration chain is the v1 showpiece. |
| **One flatmate doesn't adopt** | High | Graceful degradation. The app should remain useful for 3 out of 4 active users. Anyone can mark chores done. Expense tracker works with manual entry. |
| **Solo developer bandwidth** | Medium | Strict scope discipline. Managed services (Firebase Auth, Azure managed DB, SignalR) minimise ops work. Last-write-wins in v1 defers CRDT complexity. |
| **AI cost overrun** | Medium | Rate limiting, caching, GPT-4o-mini only, AI is premium-only. |
| **React Native learning curve** | Medium | Expo simplifies significantly. TypeScript is transferable. Flutter is the explicit fallback. |
| **Competition from Splitwise adding features** | Low–Medium | Splitwise has been stagnant for years. Speed and integration depth are the moat. |
| **Flatmate turnover breaks data continuity** | Low | Clean guided leave flow with expense settlement. Historical data persists. Archive on full turnover. |
| **GDPR non-compliance at launch** | Medium | GDPR data export (JSON/CSV) is a pre-public-launch requirement — not optional for an EU developer with an EU audience. Build before any marketing or public user acquisition, not after. |

---

## 9. Open Questions

### 9.1 Resolved

| # | Question | Resolution |
|---|---|---|
| 1 | **App name** | **Hausly.** Language-neutral, evokes "Haus" (home), clean and brandable. Trademark + domain availability check needed before committing. |
| 2 | **Notification strategy** | Group-level defaults, user-level overrides (in that priority order), configurable in settings. Default: medium aggressivity. Modules have independent notification settings (e.g. instant grocery pings, daily chore digest). Dedicated design session needed before implementation. |
| 3 | **Data portability / GDPR** | Yes — export household data as structured JSON or CSV. GDPR mandatory for EU. Implement as background task. Pre-public-launch requirement, not post-launch backlog. |
| 4 | **Payment integration** | Deferred. External settlement only for now. Stripe Connect is the natural future path (Option C). |
| 5 | **Household "health" score** | Proceed with caution. Tone must be playful, not punitive. Needs user testing before shipping. A future AI agent could generate contextual insights more gracefully than a mechanical score. |
| 6 | **Web app** | Deferred, possibly unnecessary. Mobile-first. Revisit only if user research reveals a strong laptop use case. |
| 7 | **Localization** | English first. i18n-ready codebase from day one (externalise all strings). Multi-language in a future release. |
| 8 | **Sub-feature toggles** | Resolved via §2.3: no sub-feature toggles. Smart defaults, not smart visibility. Group type sets defaults; users override in the moment. |
| 9 | **Monetization model** | Option A (household owner pays, single flat per-household subscription). Specific price TBD pending market research — see §9.2. Option C (in-app contribution requests) as a planned future feature if user evidence supports it. |
| 10 | **Leaving flow mechanics** | Resolved via §3.3: explicit blocking guided flow. User stays in group until final confirmation. No ambiguous in-between state. |
| 11 | **Inactive members in chore module** | Anyone can mark any chore as done. Credit to the completer, not the assignee. "Completed by [name]" tag for transparency. Manual "skip me this week" away flag in v2. |
| 12 | **Auth provider** | Firebase Auth. Locked. |
| 13 | **AI abstraction** | `AIService` class in backend. Provider configured by environment variable. No external abstraction library. |
| 14 | **Offline sync strategy** | Upsert-based for grocery (pending_operations queue). Additions win over deletions. Shopping session completes on reconnect. CRDT deferred to v1.1. |
| 15 | **Meal planning scope (v1)** | Diary-style free text per day (lunch/dinner slots). First-come-first-served slot ownership (only owner/admin can edit/delete). Headcount always shown, defaults to member count. Text-only entries have no grocery integration by design. Recipe book and ingredient layer introduced in v2 (manual). AI-assisted features in v3. |
| 16 | **Recipe data source** | User-created recipes only — no third-party API, no community platform. Recipes are user-level (not household-level); saving another user's recipe creates an independent fork. URL import and AI ingredient generation are v3 features. Community sharing deferred indefinitely. |
| 17 | **Recipe ownership model** | User-level, not household-level. Recipes travel with the user across households. Fork-on-save: saving a copy creates a fully independent version — edits to the original do not affect saved copies and vice versa. |
| 18 | **In-app recipe scaling** | Serving count set at creation time and displayed prominently. In-app quantity scaling (adjust serving count → quantities recalculate) included in v2 alongside recipe creation. |
| 19 | **Partial ingredient filtering** | Handled in the grocery list, not the meal planner. Recipe push adds all ingredients; the user deselects what they already have in the grocery list. No deselection step in the meal planner itself. |
| 20 | **Meal slot conflict resolution** | First-come-first-served. Slot belongs to whoever claims it. Only owner or admin can edit/delete. No voting, no alternative proposals. Disputes resolved offline. |
| 21 | **Grocery→expense trigger** | Shopping session "Done" button. User checks items during session, clicks Done, enters receipt total. Draft expense created with items as description context. |
| 22 | **Personal grocery items** | Items can be flagged as personal with visible/hidden setting. Personal items are excluded from expense generation. Visible personal items show to all members with a marker. |
| 23 | **Multi-household membership** | Forbidden in v1. Data model is many-to-many but application enforces one active household per user. Joining a new household requires leaving current one. |
| 24 | **Household settings storage** | Separate `HouseholdSettings` table (1:1 with Household). Contains `default_currency`, `enabled_modules`, `notification_level`. Created atomically with Household. |
| 25 | **Chore model (v1)** | Per-chore recurrence. Any member creates chores (must self-assign). Recurring with rotation or one-off. Overdue blocks generation. Any member can delete. Auto-cleanup on member leave. |
| 26 | **Invite join mechanism** | Code-only endpoint. Server resolves household from invite code. Preview step shows household name + member count before confirming join. |
| 27 | **Recurring expense generation** | Daily cron job. Generates draft when `next_occurrence_date <= today`. Pauses generation after 3 unconfirmed drafts (staleness cap). |

### 9.2 Still Open

1. **Pricing validation:** no market research done yet on willingness to pay. The paid tier price is intentionally **TBD** — to be set after user research, not before. Comparables to size the question: Splitwise Plus ~€3/month per user, Cozi Gold ~€30/year per family. The structural choice (per-household, single flat rate) is decided; the number is not.

2. **Onboarding solo value:** the app's value requires multiple household members. What is the experience for a user who has downloaded Hausly but hasn't yet convinced their flatmates to join? Is the grocery list useful as a personal list first? Is the expense tracker useful with manual entries before others join? Solo value before household adoption is an important retention question.

3. **Notification system design:** notification triggers, payload structure, user preference storage, and delivery mechanism need a dedicated design session before implementation.

---

## 10. Decision Log

| Decision | Rationale | Date |
|---|---|---|
| Integration > individual module quality | No single-purpose competitor can match cross-module intelligence | May 2026 |
| Dismissed full calendar module | Most people use Google/Apple Calendar; "who's home" overlay if ever needed | May 2026 |
| Dismissed household chat | Competes with WhatsApp and loses; pinboard covers the need | May 2026 |
| Group-type self-identification at onboarding | Enables smart defaults without building separate apps per audience | May 2026 |
| Per-household pricing (not per-user) | Per-user pricing disincentivises inviting flatmates, killing the core loop | May 2026 |
| Azure stack (leveraging €50/month credits) | Credits eliminate cost advantage of alternatives like Supabase | May 2026 |
| FastAPI + Container Apps (not Functions) | Persistent WebSocket connections needed; Functions is awkward for this | May 2026 |
| PostgreSQL (not Cosmos DB) | Relational domain; Postgres + RLS handles multi-tenancy cleanly | May 2026 |
| Firebase Auth (not Azure AD B2C) | B2C over-engineered for consumer apps; Firebase has better DX and React Native SDK | May 2026 |
| Azure SignalR (not self-hosted Socket.io) | Managed, zero ops, covered by credits; Socket.io needs Redis backplane at scale anyway | May 2026 |
| React Native + Expo (client) | Single codebase, largest ecosystem, Expo reduces DevOps; worth TypeScript investment | May 2026 |
| AI as premium enhancement, not product identity | Core value must stand without AI; AI features justify paid tier | May 2026 |
| MVP scope: grocery + expense + meal planner + simplified chores | Demonstrates cross-module chain (meal → grocery → expense) from day one | May 2026 |
| Meal planner v1: diary-style free text only | Avoids recipe data source problem; integration value still present; recipe layer deferred to v3 | May 2026 |
| Context-aware defaults, not sub-feature visibility rules | Prevents settings maze; avoids fragile inference rules; in-person handles edge cases | May 2026 |
| App name: Hausly | Language-neutral, evokes home, clean and brandable; pending trademark + domain check | May 2026 |
| Notification: group-level → user-level customisation | Two-layer override; defaults to medium aggressivity; module-level independent settings | May 2026 |
| GDPR data export: yes, pre-launch requirement | Legal obligation for EU market; JSON/CSV background task | May 2026 |
| Payment integration: deferred (Option A now, Option C future) | No payment infrastructure at launch; Stripe Connect as future path | May 2026 |
| Web app: deferred / possibly unnecessary | Mobile-first; revisit only if user research justifies it | May 2026 |
| Localization: English first, i18n-ready codebase | Broader market; externalise strings from day one | May 2026 |
| Leaving flow: blocking guided UI, no in-between state | User stays in group until confirmed; clean data model; handles expenses, chores, subscription transfer | May 2026 |
| Inactive member chore handling: anyone can mark done | Practical, maps to real household behaviour; fairness log records who actually completed | May 2026 |
| Offline sync: last-write-wins v1, CRDT grocery list v1.1 | Ships on schedule; grocery conflict scenario rare enough in households to defer | May 2026 |
| AI abstraction: AIService class + env var, no external lib | Simple, transparent, no added dependency; provider swap is an implementation detail | May 2026 |
| All financial mutations: user-confirmed, never automatic | Builds trust; any AI or auto-generated financial entry is a draft until user confirms | May 2026 |
| Pinboard TTL: permanent by default, opt-in expiry per note | Permanent-by-default prevents silent loss of important notes (WiFi passwords, house rules) | May 2026 |
| Recipe book: user-level ownership, not household-level | Recipes are personal knowledge; user retains them across households; fork-on-save model | May 2026 |
| Recipe save = fork, not reference | Saver can edit freely without affecting original; no silent propagation of changes | May 2026 |
| Recipe layer: v2 manual, v3 AI-assisted | Splits the problem: delivery value in v2 without AI dependency; AI features layer on top in v3 | May 2026 |
| In-app recipe scaling: included in v2 | Numeric quantities required for scaling; included at recipe creation time to keep the data model clean from the start | May 2026 |
| Partial ingredient filtering: grocery list responsibility | Keeps meal planner simple; curation of what to buy belongs in the list, not the planner | May 2026 |
| Grocery list toggle on meal entries: only visible when recipe is linked | Text-only entries show no toggle — no clutter, natural education about the recipe feature | May 2026 |
| AI ingredient generation: proposal only, not authoritative | Recipes vary by household and tradition; AI output pre-fills the editor as a starting point, user confirms | May 2026 |
| Starter recipes: pre-populated, editable, personalised by AI in v3 | Reduces cold-start friction; lets users experience grocery integration immediately; AI personalisation deferred | May 2026 |
| Paid tier price: TBD, not assumed | Specific price will be set after user research on willingness to pay, not before. Only the structural choice (per-household, single flat rate) is decided. Replaces the prior €5/month placeholder. | May 2026 |
| Dev infrastructure: cheapest/free tier first for every Azure resource | Conserves the €50/month Avanade credit during development. Production-grade tiers only on explicit, logged decision. Applies to SignalR (Free), Container Apps (consumption / scale-to-zero), Postgres (Burstable B1ms — smallest available, no free tier exists), Blob Storage (hot, minimal usage), Azure OpenAI (pay-per-token with strict rate limits). | May 2026 |
| Meal planner: first-come-first-served slot ownership | No voting/proposal system. Slot belongs to whoever claims it first. Only owner or admin can edit/delete. Disputes resolved offline. | Jun 2026 |
| Chore model: per-chore recurrence | Each chore has own interval/assignees/rotation. Replaces calendar-block model. Implicit consent, anyone-can-delete. Overdue blocks next occurrence. | Jun 2026 |
| Single household per user in v1 | Multi-household adds UX complexity (switcher). Data model keeps many-to-many; application enforces single active membership. | Jun 2026 |
| Offline sync: upsert-based for grocery, pending_operations queue | Replaces last-write-wins. Additions win over deletions. Shopping session completes on reconnect. | Jun 2026 |
| Grocery session: client-side state, receipt-total input | No server-side session entity. User enters receipt total on "Done"; items are listed as context in the expense draft. | Jun 2026 |
| Personal grocery items: is_personal flag with visible/hidden option | Personal items excluded from expense generation. Visibility configurable per item. | Jun 2026 |
| HouseholdSettings: separate 1:1 table | Keeps Household entity clean (identity + subscription). Settings holds enabled_modules, default_currency, notification_level. | Jun 2026 |
| Invite join: code-only endpoint + preview step | Server resolves household from code. Preview shows name + member count before joining. | Jun 2026 |
| Recurring expense: daily cron job with staleness cap | Generates drafts when next_occurrence_date <= today. Pauses after 3 unconfirmed drafts. | Jun 2026 |

---

## 11. Feature Ideas (Unscheduled)

Ideas that have been discussed but are not committed to any version. They require further design and user validation before scheduling.

| Idea | Description | Notes |
|---|---|---|
| Meal slot voting / proposals | Members propose alternative meals for a slot; household votes on preferred option | Adds complexity to meal planner. Current model (first-come-first-served + offline discussion) is simpler. Revisit if user feedback requests it. |
| AI computer vision for grocery | Use device camera to identify items and auto-check them from the list | Experimental. Requires on-device ML or fast API round-trip. UX unclear (barcode scan? visual recognition?). v3+ at earliest. |
| Photo proof on chores | Optional photo when marking a chore as done | Accountability vs surveillance tension. Different household types react differently. Tonal consideration needed. |
| Notification fallback for inactive members | Email/SMS nudge for members who stop using the app | Adds infrastructure cost. Needs user evidence before building. |
| Grocery item price history | Track per-item prices over time for budgeting insights | Useful for analytics but heavy data entry burden. Consider only with receipt OCR (v3). |

---

*This document is a living brainstorming artifact. It captures decisions and reasoning to date but is not an implementation specification. All architectural choices, feature definitions, and business model details are subject to revision as the project evolves.*
