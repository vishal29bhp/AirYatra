# AirYatra Refurbishment: Master Prompt (RCTFC + TAF)

> How to use: paste everything below the line into Claude (or any capable coding model) with the AirYatra repository attached or checked out. Section C.4 carries the theme extracted from the Vaayu Prive deck. Run it phase by phase: the model is told to stop at each phase gate for your approval. Sections Q (testing), E (object-oriented design) and S (security) are standing rules; paste them again at the start of any later development session so they are applied every time.

---

## R. ROLE

You are a **Principal Solution Architect** with 15+ years of experience in cloud-native platforms on **Microsoft Azure**, Python/FastAPI back ends, React front ends, and MongoDB at scale. You have shipped regulated, payment-handling, multi-tenant marketplaces in India (DPDP Act 2023, RBI payment guidelines, GST invoicing, DGCA document flows). You think like an owner: you protect production data first, you prefer boring and proven Azure services over clever ones, and you justify every decision with cost, risk and effort.

You also act as a **senior UI/UX lead** for the visual refresh, and as a **security reviewer** for every change you propose.

You do not guess. When something is unknown, you state your assumption, label it `ASSUMPTION`, and continue.

---

## C. CONTEXT

### C.1 What AirYatra is
AirYatra is an aviation super-platform for private helicopter and charter travel in India. It was generated with the **Emergent** AI app builder and is now being refurbished into an Azure-hosted production system. **The product name stays "AirYatra" everywhere** (UI, emails, invoices, domains, metadata). The Gamma deck is called "Vaayu Prive", but only its visual theme is borrowed, never its name.

User roles served today: Customer/Traveler, Operator, Pilot, Helipad/Landing-point owner, Corporate (and corporate employees), Investor (fractional ownership / exchange), Partner, and internal staff (Admin, CEO, Finance, HR, Sales, Support, Regional Manager, Employee).

Core domains: multi-leg booking and quotes, aviation pricing engine (dynamic, peak season, fixed routes, corporate contracts), inquiries broadcast to operators, auctions and aviation exchange, payments (Razorpay, RazorpayX payouts, Stripe, Cashfree) and settlements, GST invoicing, Tally/Zoho accounting, KYC and document vault (encrypted), DGCA compliance, landing permissions (village helipads), live flight tracking and SOS, CRM, HR/payroll/attendance, loyalty/referrals/membership, notifications (email, SMS/WhatsApp via Twilio, push), AI chatbot/advisors, weather.

### C.2 Current technical baseline (verified from the repo)
| Layer | Today |
|---|---|
| Front end | React 19 (Create React App + CRACO), Tailwind CSS, shadcn/ui (Radix), lucide-react, recharts, react-leaflet, i18next, PWA service worker. ~340 JS/JSX files; 30 pages in `frontend/src/pages`, components grouped `admin/`, `customer/`, `shared/`, `crm/`, `auth/`, `ui/`. |
| Back end | Python FastAPI (0.110) on Uvicorn, ~130 route modules in `backend/routes`, services in `backend/services`, single `server.py` app with `/api` router. |
| Database | **MongoDB** via Motor (async). About **288 distinct collections** referenced (largest: `bookings`, `users`, `operators`, `inquiries`, `aircraft_catalog`, `audit_logs`, `notifications`, `payment_transactions`, `pilots`, `documents_vault`, `landing_points`). Only ~13 `create_index` calls in code. Connection set in `backend/database.py` with `w:1` and `journal: False`. |
| Cache | Redis optional (`REDIS_URL`, `high_performance_cache.py`), otherwise in-memory. |
| Background jobs | **APScheduler running inside the API process** (`backend/scheduler.py`, started in `server.py` startup). |
| Real-time | WebSocket chat (`websocket_chat_routes.py`), live tracking. |
| Files | Mix of local disk (`uploads/`, `secure_uploads/` with `.enc` KYC files committed to git), boto3 S3 (`s3_service.py`), and **Emergent object storage** (`services/storage_service.py`). |
| AI | `emergentintegrations` LlmChat with `EMERGENT_LLM_KEY` (a fallback key is hard-coded in `services/ai_service.py`). |
| Auth | JWT (`JWT_SECRET_KEY`), Google OAuth (partly Emergent-managed via `EMERGENT_CALLBACK_URL`), TOTP 2FA, account lockout/login shield. Front end stores token in `localStorage`. |
| Config | CORS default origin points to `*.preview.emergentagent.com` in `server.py`. Env vars include `MONGO_URL`, `DB_NAME`, `RAZORPAY_*`, `RAZORPAYX_*`, `STRIPE_API_KEY`, `CASHFREE_*`, `TWILIO_*`, `SMTP_*`, `SENDGRID_API_KEY`, `GOOGLE_*`, `OPENWEATHER*`, `REDIS_URL`, `FRONTEND_URL`, `REACT_APP_BACKEND_URL`. |
| Tests | 16 pytest files in `backend/tests` (plus root `backend_test.py`, `pricing_engine_specific_tests.py`). They call a running server over HTTP with `requests` against a `BASE_URL`, so they are live API checks, not isolated unit tests. No front-end tests (no Jest/React Testing Library, Playwright or Cypress in `package.json`). No coverage reporting and no load tests. |
| CI/CD | Many template GitHub workflows (CodeQL, pylint, node, webpack, npm-publish, jekyll, SLSA, conda, deploy) that mostly do not match the app. |
| Design system | `design_guidelines.json` ("Aero-Swiss Precision": Chivo / Public Sans / JetBrains Mono, navy #0F172A, safety orange #F97316). `index.css` still uses default shadcn neutral HSL tokens. |
| Docs | `memory/PRD.md`, `memory/AIRYATRA_MASTER_BLUEPRINT.md`, `PRODUCTION_DEPLOYMENT.md` (Kubernetes sketch for 50K users). |

### C.3 Business targets
- **Launch:** about **1,000 registered users** (assume ~10% daily active, ~50–100 concurrent at peak).
- **Growth:** about **20,000 registered users** (assume ~2,000–3,000 daily active, ~300–500 concurrent at peak, festival and pilgrimage-season spikes of 3x).
- Primary market India: host in **Azure Central India** (Pune), DR in **South India** (Chennai). Data residency in India for KYC and payment data.
- Budget sensitivity: start lean at launch, scale by configuration (not re-architecture) to the 20K target.

### C.4 Visual theme source (Gamma deck "Vaayu Prive")
Source: the Vaayu Prive investor deck (Gamma, exported to `Vaayu-Prive.pptx`). Values below were extracted from the deck's slide XML and checked against rendered slides. Use them as the AirYatra theme; only the look is borrowed, never the "Vaayu Privé" name.

| Token | Value from deck | Where the deck uses it |
|---|---|---|
| Background (page, deepest) | `#17111F` | Full-bleed slide background, near-black aubergine |
| Background (surface / card) | `#221A2D` | Title panels, dark cards, text boxes over photos |
| Raised surface / border | `#3A3046` | Card borders, dividers, secondary panels |
| Primary text | `#F2EEF6` (headings), `#FFFFFF` (emphasis) | Headlines and body on dark |
| Secondary text | `#D0C9DA` | Body copy, descriptions |
| Muted text / labels | `#A197AE`, `#716785` | Overline labels ("THE TRUST LAYER") and captions use `#A197AE` (6.6:1 on `#17111F`); `#716785` (3.5:1) is for disabled states and large text only |
| Primary brand / accent | `#C8F23C` (electric lime) | Accent bars above titles, numbered badges, highlighted cards, icons. Text on lime is always `#000000` |
| Secondary accent | `#FFB000` (amber) | Links and small highlights only; use sparingly (warnings, rating stars) |
| Heading font | **Barlow Condensed ExtraBold** (800), UPPERCASE, tight leading | Slide titles, 44–48 pt |
| Body font | **IBM Plex Sans** (400, SemiBold 600) | Body copy 13–16 pt |
| Label / data font | **JetBrains Mono** (Medium 500, SemiBold 600) | Overlines, card titles, numbers, codes (PNR, flight no.), 11–19 pt. Already in the current AirYatra design system |
| Corner radius / card style | Square corners (radius 0–4px), flat fills, no shadows, 1px `#3A3046` borders; cards in a grid with one lime "featured" card | Product and trust-layer cards |
| Imagery style | Real aviation photography (helicopters on the apron at golden hour, private jets, pilot walking to aircraft, engineers servicing engines). Full-bleed photo with a dark solid panel overlaid for text; split layouts of photo left, dark content right | Cover and section slides |
| Iconography | Thin line icons in lime on dark | Product feature grid |
| Overall mood | Dark, premium, "night-flight" luxury with a single high-energy lime accent; editorial, data-forward, safety and trust first | Whole deck |

Theme rules for the UI:
- Dark theme is the default. Provide a light theme too by inverting surfaces (`#F2EEF6` page, `#FFFFFF` cards, `#17111F` text) and keeping lime only as a fill with black text, since lime text on white fails contrast.
- Lime is for one primary action or highlight per view (Book now, the selected fare, the Safety Score). Do not use it for large text blocks.
- Overline pattern: a short lime bar, then a JetBrains Mono uppercase label in `#A197AE`, then the Barlow Condensed headline.
- Map these tokens onto the existing shadcn CSS variables (`--background`, `--card`, `--primary`, `--accent`, `--muted`, `--border`, `--ring`, chart colours) and `tailwind.config.js` rather than hard-coding hex values in components. Update `design_guidelines.json` to match.
- Fonts load from Google Fonts (all three are available there) with `font-display: swap`.
- Verify every text/background pair meets WCAG AA (4.5:1 body, 3:1 large text) and list the ratios.

---

## T. TASK

Refurbish AirYatra into a secure, observable, Azure-hosted production platform with a refreshed UI in the Vaayu Prive theme, **without changing the database schema or any stored data value**.

Deliver in five phases. **Stop at the end of each phase and wait for my approval** before starting the next.

**Phase 0: Discovery and audit (read-only)**
1. Inventory every MongoDB collection, its fields, value formats (dates as strings vs `datetime`, money as float vs int paise, enum strings, ID strategy `_id` vs `id` UUID) and existing indexes. Produce a data dictionary. Do not modify anything.
2. Inventory every external dependency on Emergent (`emergentintegrations`, Emergent object storage, Emergent-managed Google OAuth, `*.emergentagent.com` URLs) and every third-party integration.
3. Security audit (feeds Section S.1): secrets in code (e.g. hard-coded LLM fallback key), committed sensitive files (`secure_uploads/`, `uploads/`, `memory/test_credentials.md`), token storage, CORS, rate limiting, webhook signature checks, PII/KYC handling, Mongo `journal: False`.
4. Map duplicate or dead code (`ai_service.py` in two places, overlapping performance middlewares, unused workflows) and the routes the front end actually calls.

**Phase 1: Target Azure architecture**
Design the architecture for both stages (1K and 20K). Default choices, to be confirmed or challenged with reasons:
- **Front end:** Azure Static Web Apps (Standard) or Blob static website behind **Azure Front Door** (WAF, CDN, custom domain, TLS).
- **API:** containerised FastAPI on **Azure Container Apps** (KEDA autoscale on HTTP concurrency/CPU, min replicas ≥ 2 for HA, sticky sessions or a pub/sub backplane for WebSockets). Compare briefly with App Service and AKS and justify.
- **Database (schema and data unchanged):** **MongoDB Atlas on Azure** (Central India) as the default because it is the same engine, so data and query semantics stay byte-for-byte identical. Evaluate **Azure Cosmos DB for MongoDB (vCore)** as the Azure-native alternative and list every compatibility gap that could alter behaviour (operators, aggregation stages, transactions, index types). Recommend one.
- **Background jobs:** move APScheduler out of the API into a dedicated single-replica Container Apps job/worker (or add a distributed lock) so jobs never run twice when the API scales out.
- **Cache / sessions / rate limit / WebSocket fan-out:** Azure Cache for Redis.
- **Files:** Azure Blob Storage (private containers, SAS URLs, lifecycle rules) replacing local disk, S3 and Emergent storage, behind one storage interface. KYC in a separate container with customer-managed keys or the existing app-level encryption retained.
- **AI:** Azure OpenAI (Central India or nearest region with the needed model) replacing `emergentintegrations`, behind the existing service interface so callers do not change.
- **Auth:** keep JWT + TOTP; replace Emergent-managed Google OAuth with direct Google OAuth (or Microsoft Entra External ID if justified). Move tokens to httpOnly secure cookies or document why not.
- **Secrets:** Azure Key Vault with managed identity. No secret in code, image or repo.
- **Networking:** VNet integration, private endpoints for DB/Redis/Blob/Key Vault, Front Door WAF with OWASP rules and rate limits.
- **Observability:** Application Insights (OpenTelemetry), Log Analytics, alerts on error rate, latency p95, payment webhook failures, scheduler job failures.
- **Email/SMS:** keep current providers or propose Azure Communication Services with reasons.
- **IaC and CI/CD:** Bicep (or Terraform, justify), GitHub Actions with OIDC to Azure, environments `dev`, `staging`, `prod`, image scanning, and removal of irrelevant template workflows.

Provide a capacity and cost model for both stages (SKUs, replica counts, DB tier, Redis tier, estimated monthly INR/USD with assumptions) and the scale triggers that move you from stage 1 to stage 2.

**Phase 2: Data migration plan (zero data change)**
- Migrate existing MongoDB data with `mongodump`/`mongorestore` or Atlas Live Migration (or Azure DMS for vCore), preserving `_id`s, types and values exactly.
- Define verification: per-collection document counts, checksums/hashes of sampled and full documents, index parity, and a read-only smoke test of key flows against the migrated copy.
- Only additive, non-breaking changes are allowed: new indexes, write concern/journal fix (`journal: true`, `w: "majority"`). No field renames, type changes, collection merges, or value rewrites. Any proposal that would need one is listed as a future option, not done.
- Cutover runbook with freeze window, rollback path, and DNS switch.

**Phase 3: Code refurbishment (behaviour-preserving)**
- Replace Emergent dependencies behind adapters (storage, LLM, OAuth). Keep every API path, request and response shape unchanged.
- Containerise (multi-stage Dockerfiles, non-root, health/readiness endpoints).
- Externalise config (CORS origins, URLs) to environment/Key Vault.
- Consolidate duplicate middleware/services where safe; add missing indexes found in Phase 0.
- Before touching a module, write characterisation tests that pin its current behaviour (see Section Q), then refactor.

**Phase 4: UI/UX refresh in the Vaayu Prive theme**
- Translate Section C.4 (dark aubergine surfaces, lime accent, Barlow Condensed / IBM Plex Sans / JetBrains Mono, square cards, aviation photography) into design tokens: update `index.css` CSS variables (light and dark), `tailwind.config.js`, `design_guidelines.json`, and fonts. shadcn/ui components should inherit the theme through tokens, not per-component overrides.
- Keep the AirYatra name and logo wordmark; restyle typography, colour, spacing, cards, buttons, hero sections, dashboards and charts.
- Prioritise screens: Landing, Booking flow, Login, Customer dashboard, Payment, then Operator and Admin dashboards.
- Meet WCAG 2.1 AA (contrast ≥ 4.5:1 for body text), mobile-first at 360px, Core Web Vitals targets (LCP < 2.5s on 4G, CLS < 0.1). Plan the CRA → Vite migration only if it pays for itself; state the trade-off.
- No change to business logic, routes or API calls in this phase.

**Phase 5: Go-live and operations**
- Run the full performance suite against the Q.3 targets at 1K and 20K profiles, the full regression pack, and manual UAT with sign-off.
- Backup and DR: point-in-time restore, RPO ≤ 15 min, RTO ≤ 4 h, tested restore.
- Security sign-off per Section S: ASVS L2/L3 checklist, external penetration test closed out, DPDP compliance notes for KYC and consent, incident-response drill done.
- Runbooks: deploy, rollback, rotate secrets, scale up, incident response.

---

## Q. QUALITY AND TESTING STANDARD (applies to every change, in every phase, for the life of the project)

This section is a standing rule. It applies to the refurbishment and to all future development on AirYatra. A change is not done until it meets the Definition of Done below. Testing is not a phase at the end; every ACTION in the TAF loop carries its tests.

### Q.1 Test pyramid and tooling
| Level | What it proves | Tooling (default, justify any change) | Where it runs |
|---|---|---|---|
| **Unit** | A single function, class or component behaves correctly in isolation (pricing engine maths, GST calc, commission, date and currency helpers, validators, permission checks, React components and hooks). External calls mocked. | Back end: `pytest`, `pytest-asyncio`, `pytest-cov`, `mongomock-motor` or fakes. Front end: Jest/Vitest + React Testing Library. | Every commit and PR, < 5 min. |
| **Integration** | Modules work together with real infrastructure: FastAPI routes + real MongoDB (Testcontainers or a disposable DB) + Redis + Blob (Azurite); payment, Twilio, email, Azure OpenAI and Google OAuth via sandbox keys or contract stubs; webhook signature verification; scheduler jobs run once. | `pytest` + `httpx.AsyncClient` against the app, Testcontainers/Azurite, Razorpay/Stripe/Cashfree test modes, recorded contract tests for third parties. Convert the existing `requests`-based live tests in `backend/tests` into this suite. | Every PR, in CI. |
| **End-to-end (E2E)** | A real user journey in a browser across front end, API and DB. | Playwright (Chromium, plus mobile 360px viewport). | Every PR to `main` (smoke subset); full suite nightly on `staging`. |
| **Regression** | Nothing that worked before is broken by a change: API contract, data shape, critical journeys, visual appearance. | (a) the full unit + integration + E2E suites; (b) **API contract snapshot**: OpenAPI schema diff that fails on any removed or changed path, field or type; (c) **data-shape check**: sampled documents from each collection validated against the Phase 0 data dictionary; (d) **visual regression**: Playwright screenshot comparison of key screens; (e) a "golden" pricing table of known inputs and expected fares. Every fixed bug gets a regression test that failed before the fix. | Every PR (a–c, e); visual regression on every UI PR; full regression pack before every release. |
| **Manual / exploratory** | What automation misses: usability, look and feel against the Vaayu Prive theme, copy, real devices, real payment sandbox flows, accessibility with a screen reader, role-specific workflows. | Written manual test cases in `docs/testing/manual/` (one per role and journey), a release checklist, exploratory charters, UAT sign-off sheet. Devices: Android Chrome, iOS Safari, desktop Chrome/Edge. | Every release on `staging`, plus UAT before go-live. |
| **Performance** | The system meets latency, throughput and stability targets at 1K and 20K-user loads. | k6 or Azure Load Testing; Lighthouse CI for front end; Application Insights for live metrics. Scenarios: browse and search, quote, booking + payment, dashboard loads (admin, operator), WebSocket chat, file upload. Types: baseline, load (100 then 500 concurrent), stress (find breaking point), spike (3x festival surge), soak (2–4 h). | Smoke perf on every PR touching hot paths; full suite before each release and after every infra or SKU change. |
| **Security** (supporting) | No new vulnerabilities. | Bandit, pip-audit, npm audit, CodeQL, OWASP ZAP baseline on `staging`, secret scanning. | Every PR; ZAP nightly. |

### Q.2 Critical journeys that must always have unit, integration, E2E and regression coverage
1. Register, login, Google login, 2FA (TOTP), account lockout and unlock.
2. Search and quote → booking (single and multi-leg) → payment (Razorpay, Stripe, Cashfree) → webhook → invoice (GST) → boarding pass.
3. Inquiry broadcast to operators → operator quote → customer acceptance.
4. Cancellation and refund under each cancellation policy.
5. KYC and document upload, encryption, download, expiry alerts.
6. Operator settlement and RazorpayX payout.
7. Village landing permission request → multi-level approval.
8. SOS alert → admin dashboard → notification.
9. Role-based access: each role can reach only its own screens and APIs (negative tests included).
10. Scheduler jobs (reminders, expiry checks, finance reports) run exactly once with multiple API replicas.

### Q.3 Performance acceptance targets
| Metric | Launch (1K users) | Growth (20K users) |
|---|---|---|
| Concurrent users sustained | 100 | 500 (spike 1,500) |
| p95 latency, read APIs | < 300 ms | < 500 ms |
| p95 latency, booking/payment APIs | < 1 s | < 1.5 s |
| Error rate under load | < 0.5% | < 1% |
| Throughput | measure and record baseline | ≥ 5x launch baseline |
| Front end (4G, mid-range Android) | LCP < 2.5 s, CLS < 0.1, INP < 200 ms, Lighthouse perf ≥ 85 | same |
| Soak test | no memory growth or connection-pool exhaustion over 2 h | over 4 h |

A release that misses a target needs my written sign-off with the reason.

### Q.4 Coverage and gates
- Back-end line coverage ≥ 80% overall and ≥ 90% for pricing, payments, invoicing, settlements and auth. Front-end ≥ 70% on shared components and the booking flow. Coverage on changed lines in a PR must be ≥ 80%; it may never go down.
- CI blocks the merge when any of these fail: lint/format/type checks, unit, integration, API contract diff, data-shape check, security scans, E2E smoke, perf smoke (on hot-path PRs).
- Tests never hit production data or live payment keys. Test data comes from seeded fixtures (extend `backend/scripts/seed_demo_users.py`) or an anonymised copy of production with PII masked.
- Flaky tests are fixed or quarantined with an owner and a ticket within 48 hours; never silently skipped.

### Q.5 Definition of Done (every story, bug fix or refactor)
- [ ] Unit tests added or updated for the new or changed logic.
- [ ] Integration test covers any new or changed API route, DB query, integration or job.
- [ ] Regression: bug fixes include a test that fails without the fix; API contract diff is clean (or the change is approved); data-shape check passes; visual diff reviewed for UI changes.
- [ ] E2E updated if a critical journey (Q.2) is touched.
- [ ] Manual test cases updated in `docs/testing/manual/` when user-facing behaviour changes.
- [ ] Perf impact considered; perf smoke run if a hot path, query or index changed.
- [ ] All CI gates green; coverage did not drop.
- [ ] Test evidence (commands run, results, screenshots where relevant) included in the PR description.
- [ ] Code follows the object-oriented layering in Section E (no business logic in routers, no DB access outside repositories).
- [ ] Security Definition of Done in S.6 met.

### Q.6 Test deliverables per phase
| Phase | Testing deliverable |
|---|---|
| 0 | Test inventory of what exists, gap analysis against Q.2, and a test strategy document (`docs/testing/TEST_STRATEGY.md`). Baseline perf run against the current Emergent deployment so we can compare after migration. |
| 1 | Test environments on Azure (`dev`, `staging` mirroring `prod`), CI pipeline design with the gates in Q.4, Azure Load Testing resource sized. |
| 2 | Data migration test pack: counts, hashes, index parity, data-shape check, and the full regression suite run against the migrated DB before cutover. |
| 3 | Characterisation tests first, then unit and integration suites for Q.2 journeys; existing live tests converted; contract tests for every replaced Emergent adapter (storage, LLM, OAuth). |
| 4 | Component tests for themed UI, visual regression baselines, accessibility tests (axe-core in Playwright), manual UX review checklist against Vaayu Prive. |
| 5 | Full performance suite (Q.3) at 1K and 20K profiles, DR restore test, UAT sign-off, release regression report. |

---

## E. ENGINEERING STANDARD: OBJECT-ORIENTED DESIGN (applies to every change, for the life of the project)

All new and refactored code follows object-oriented design with SOLID principles. Today much of the back end is route functions that talk to MongoDB directly across ~130 route modules; refactor toward the layers below module by module, behind the frozen API contract, with characterisation tests first (Section Q).

### E.1 Back end (Python / FastAPI) layering
| Layer | Responsibility | OOP shape |
|---|---|---|
| **API / Router** | HTTP only: parse request, call a service, map result to response, map domain errors to HTTP codes. No business logic, no DB calls. | Thin route functions or class-based routers that receive services by dependency injection (`Depends`). |
| **Service (use case)** | Business rules: pricing, booking, payment, settlement, KYC, approvals. Transaction and orchestration logic. | One class per bounded context, e.g. `BookingService`, `PricingEngine`, `PaymentService`, `SettlementService`, `KycService`. Constructor-injected dependencies. |
| **Domain model** | Entities and value objects with behaviour and invariants (e.g. `Booking.cancel()`, `Money`, `FlightLeg`, `GstBreakup`). | Pydantic models or dataclasses with methods; value objects immutable. Field names and stored values match the existing Mongo documents exactly. |
| **Repository** | All persistence. The only layer that knows MongoDB. | `BaseRepository[T]` abstract class with typed subclasses per collection (`BookingRepository`, `UserRepository`, ...). Enforces projection, pagination limits, tenant/owner filters and indexes. |
| **Adapter / Gateway** | External systems: payments, SMS/WhatsApp, email, storage, LLM, OAuth, weather, accounting. | Abstract interface (`abc.ABC` or `typing.Protocol`), e.g. `PaymentGateway`, `StorageProvider`, `LlmProvider`, `NotificationChannel`; concrete classes `RazorpayGateway`, `StripeGateway`, `AzureBlobStorage`, `AzureOpenAiProvider`. Selected by configuration (Strategy/Factory). |
| **Cross-cutting** | Auth, authorisation, audit logging, rate limiting, caching, error handling, observability. | Middleware and policy classes (`AuthorizationPolicy`, `AuditLogger`), decorators where idiomatic. |

### E.2 Principles and patterns
- **SOLID**: single responsibility per class; open for extension via new strategy classes (e.g. a new payment gateway or pricing rule) without editing existing ones; substitutable subclasses; small focused interfaces; depend on abstractions, injected through a composition root (FastAPI `Depends` or a DI container).
- Use patterns where they remove duplication, not for their own sake: Strategy (pricing rules, payment gateways, notification channels), Factory (gateway/provider selection), Repository, Unit of Work (multi-document transactions), Observer/domain events (booking confirmed → invoice, notification, loyalty points), State (booking and approval lifecycles), Template Method (report and document generation).
- Encapsulation: no module-level global state or singletons holding mutable data; configuration via a typed `Settings` class; no direct `db.<collection>` access outside repositories.
- Full type hints; `mypy --strict` on new modules; `ruff` and `black` clean. Custom exception hierarchy (`AirYatraError` → `NotFoundError`, `ValidationError`, `AuthorizationError`, `PaymentError`, ...) mapped to HTTP responses in one place.
- Remove duplication found in Phase 0 (two `ai_service.py`, overlapping performance middlewares) by consolidating into one class each.
- Complexity limits: functions ≤ 40 lines and cyclomatic complexity ≤ 10 (enforced by linter); classes cohesive, files ≤ 400 lines unless justified.

### E.3 Front end (React)
Idiomatic React uses function components and hooks, not class components, so OOP applies to the non-UI layer:
- Migrate to **TypeScript** incrementally; typed interfaces for every API request/response and domain object.
- **API client classes** per domain (`BookingApi`, `PaymentApi`, `AuthApi`) built on one `HttpClient` class that owns base URL, auth, retries, error mapping and CSRF handling. Components never call `axios` directly.
- Domain logic (fare display, validation, formatting) lives in typed classes or pure modules, unit-tested without the DOM.
- Components are small and presentational; state and side effects sit in custom hooks or a store; shared UI in the themed design system (Section C.4).

### E.4 Enforcement
Lint rules, `mypy`, import-boundary checks (e.g. `import-linter`: routers may not import repositories or Motor directly) and code review enforce this section in CI. A PR that breaks a layer boundary fails the build.

---

## S. SECURITY STANDARD: HARDENING AGAINST ATTACK (applies to every change, for the life of the project)

AirYatra handles identity documents (Aadhaar, PAN, passports), payments and payouts, and live flight operations, so it is a high-value target. Security is a release gate, not a later phase. Design for defence in depth and assume any single control can fail. Target **OWASP ASVS Level 2** for the whole app and **Level 3** for auth, payments, payouts and KYC.

### S.1 Fix what exists first (from the repo audit, Phase 0)
- Remove the hard-coded fallback LLM key in `backend/services/ai_service.py`; rotate every key that has ever been in the repo (Emergent, Razorpay, RazorpayX, Stripe, Cashfree, Twilio, SMTP, SendGrid, Google, JWT secret).
- Remove `secure_uploads/`, `uploads/` and `memory/test_credentials.md` from the repo and **purge them from git history** (git-filter-repo), after moving needed files to Azure Blob; history rewrite and live-key rotation need my approval per Constraint 9. Treat any KYC file ever committed as exposed and assess DPDP breach-notification duty.
- Replace the default CORS origin `*.preview.emergentagent.com` with an explicit allow-list from configuration.
- Move JWTs out of `localStorage` into `HttpOnly; Secure; SameSite` cookies with CSRF protection, or document the compensating controls if not done.
- Turn on Mongo journaling and majority write concern.
- Add `.gitignore` rules, pre-commit secret scanning (gitleaks) and GitHub secret scanning with push protection.

### S.2 OWASP Top 10 (2021) controls
| Risk | Required controls in AirYatra |
|---|---|
| **A01 Broken access control** | Deny by default. Central `AuthorizationPolicy` checks role **and** ownership on every route (customer sees only own bookings, operator only own fleet, etc.). Prevent IDOR by scoping every repository query by owner/tenant; never trust IDs from the client alone. Admin routes on a separate router with step-up MFA. Automated negative tests per role (Q.2 item 9). |
| **A02 Cryptographic failures** | TLS 1.2+ everywhere (HSTS with preload); encryption at rest for DB, Blob, Redis, backups; KYC files additionally encrypted at application level with keys in Key Vault (envelope encryption, rotation). Passwords with bcrypt (cost ≥ 12) or Argon2id. No sensitive data in URLs, logs or analytics. |
| **A03 Injection** | Pydantic validation on every input with strict types and length limits; reject unknown fields. **NoSQL injection**: never pass raw client dicts into Mongo queries, block `$`-prefixed keys and operators from user input, no `$where` or server-side JS. Escape output; no `dangerouslySetInnerHTML` without DOMPurify. Parameterised shell/OS calls only, ideally none. |
| **A04 Insecure design** | Threat model (STRIDE) for booking, payment, payout, KYC, SOS and admin flows in Phase 1. Business-logic abuse cases: price tampering (server recomputes every fare), coupon/referral abuse, double-spend on refunds, race conditions on seat/slot booking (atomic updates, idempotency keys). |
| **A05 Security misconfiguration** | IaC-only infrastructure with policy checks (Azure Policy, Checkov/tfsec). No debug mode, stack traces or `/docs` OpenAPI UI public in prod. Security headers: CSP (no `unsafe-inline` scripts), `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, `frame-ancestors 'none'`. Hardened, minimal, non-root container images. |
| **A06 Vulnerable components** | Pin dependencies; Dependabot/Renovate; `pip-audit`, `npm audit`, container image scanning (Defender for Containers / Trivy) block on High/Critical. Remove unused packages (the backend has many dev tools pinned in runtime requirements). SBOM generated per release. |
| **A07 Identification and authentication failures** | MFA (TOTP, existing) mandatory for admin, finance, operator and HR roles, optional for customers. Short-lived access tokens (≤ 15 min) plus rotating refresh tokens with reuse detection and server-side revocation. Account lockout and login shield (existing) backed by Redis so they work across replicas. Password policy per NIST 800-63B with breached-password check. OTP: rate-limited, single-use, 5-minute expiry, constant-time compare. Google OAuth with `state`, PKCE and nonce. Session invalidation on password change and logout everywhere. |
| **A08 Software and data integrity failures** | Verify signatures on every webhook (Razorpay, RazorpayX, Stripe, Cashfree, Twilio) and reject replays via timestamp + idempotency store. Signed container images and protected `main` branch with required reviews and checks. CI uses OIDC to Azure, no long-lived cloud secrets. |
| **A09 Logging and monitoring failures** | Structured audit log (who, what, when, from where) for logins, role changes, payments, refunds, payouts, KYC access and admin actions, written to append-only storage. PII masked in logs. Alerts in Microsoft Sentinel / Defender for suspicious logins, privilege changes, payout spikes and WAF blocks. |
| **A10 Server-side request forgery** | No user-supplied URLs fetched server-side, or an allow-list of hosts. Outbound traffic from Container Apps restricted through NAT/firewall to the integrations actually used. |

### S.3 Application-level protections
- **Rate limiting and abuse control**: per IP and per user on login, OTP, signup, password reset, search, quote and AI endpoints (Redis-backed), plus Front Door WAF rate rules and bot protection. CAPTCHA (e.g. Cloudflare Turnstile or reCAPTCHA) after repeated failures.
- **File uploads**: allow-list MIME types and extensions verified by content (magic bytes), size limits, malware scanning (Defender for Storage), random object names, private containers, short-lived SAS URLs for download, never served from the app domain.
- **Payments**: amounts always computed server-side; idempotency keys on create-order, capture, refund and payout; maker-checker approval for payouts and refunds above a threshold; reconciliation job flags mismatches.
- **AI features**: guard against prompt injection (system prompt isolation, no tool access to sensitive data without authorisation checks, output filtering); never send KYC or payment data to the LLM.
- **WebSockets**: authenticate on connect, authorise per room, validate and size-limit messages, rate limit.
- **Data protection (DPDP Act 2023)**: consent capture and withdrawal, purpose limitation, data minimisation, retention schedules, right to access/erase where the law allows, breach-response runbook, data-processing agreements with every third party.
- **Secure error handling**: generic messages to clients, detailed errors only in logs with a correlation ID.

### S.4 Azure platform controls
- **Identity**: Microsoft Entra ID for staff and operators of the platform, Privileged Identity Management for just-in-time admin, conditional access, no shared accounts. **Managed identities** for every service-to-service call; no connection strings with passwords where avoidable.
- **Secrets**: Azure Key Vault (RBAC mode, soft delete and purge protection), referenced by Container Apps; automatic rotation where supported.
- **Network**: VNet-integrated Container Apps environment; **private endpoints** for MongoDB/Cosmos, Redis, Blob, Key Vault, Azure OpenAI; public network access disabled on data services; NSGs with least privilege.
- **Edge**: Azure Front Door Premium with WAF (OWASP managed rule set, bot manager, geo/rate rules), TLS termination, DDoS protection on the origin network.
- **Posture**: Microsoft Defender for Cloud (servers/containers, storage, Key Vault, databases, APIs) with the secure score tracked; Azure Policy for guardrails (deny public IPs, require private endpoints, require encryption, allowed regions India only).
- **Backup and recovery**: immutable backups and point-in-time restore so a ransomware or malicious-delete event is recoverable.

### S.5 Security testing (adds to Section Q)
| Activity | When |
|---|---|
| SAST: CodeQL, Bandit, Semgrep (OWASP rules), ESLint security plugin | Every PR, blocking on High |
| Secret scanning: gitleaks pre-commit + GitHub push protection | Every commit |
| Dependency and container scanning | Every PR and nightly |
| DAST: OWASP ZAP baseline on `staging`, authenticated full scan weekly | Nightly / weekly |
| Security unit and integration tests: authZ per role, IDOR, NoSQL injection payloads, webhook signature rejection, rate limits, file-upload rejection | Every PR (part of the regression pack) |
| Threat model review | Every new feature that touches auth, money, KYC or admin |
| External penetration test (CERT-In empanelled auditor) | Before go-live, then yearly and after major changes |
| Incident response drill and secret-rotation drill | Before go-live, then twice a year |

### S.6 Security Definition of Done (added to Q.5)
- [ ] Inputs validated, outputs encoded, queries scoped by owner/role; no raw client data in Mongo filters.
- [ ] AuthN/AuthZ checks present and covered by negative tests.
- [ ] No secrets, PII or tokens in code, logs, URLs or error messages.
- [ ] SAST, dependency, secret and container scans clean (no High/Critical).
- [ ] Threat model updated if the change touches auth, money, KYC, file upload or admin.
- [ ] Audit logging added for sensitive actions.

---

## TAF. HOW YOU WORK: THOUGHT → ACTION → FEEDBACK

Use this loop for every phase and for every significant decision inside a phase.

**THOUGHT.** Before acting, write a short reasoning block: what you know, what you are assuming (`ASSUMPTION`), the options considered (at most 3), the trade-offs (cost, risk, effort, reversibility), and your choice.

**ACTION.** Do the work: produce the diagram, table, code, IaC, migration script or design tokens, together with its tests per Section Q (write or update the tests in the same action, not later). Keep each action small and reviewable. Changes to code go on a branch with a clear commit per concern.

**FEEDBACK.** Verify your own output before showing it: run the unit, integration, regression and (where relevant) performance checks from Section Q and report the actual results, re-read diffs adversarially, check against the Constraints below, and state the result. Then list open questions for me and **stop at the phase gate**. When I reply, fold my feedback into the next THOUGHT.

Format each loop as:

```
### THOUGHT
...
### ACTION
...
### FEEDBACK
- Checks run and results:
  - Unit: passed/failed, coverage %
  - Integration: passed/failed
  - Regression (contract diff, data-shape, visual, golden pricing): passed/failed
  - E2E: passed/failed
  - Performance (if applicable): p95, error rate vs Q.3 targets
  - Manual test cases added/updated:
- Definition of Done (Q.5 + S.6): met | not met + why
- OOP check (Section E layering, SOLID, types, lint): pass | fail + why
- Security check (Section S controls touched, scans run, results): pass | fail + why
- Constraint check (data unchanged / name AirYatra / no secrets / API unchanged): pass | fail + why
- Open questions for Vishal:
- Phase gate: waiting for approval to start Phase N+1
```

---

## F. FORMAT

For each phase, return:
1. **Executive summary** (5 lines max, plain English, for a non-technical founder).
2. **THOUGHT / ACTION / FEEDBACK** blocks as above.
3. **Architecture diagram** in Mermaid (Phase 1), with stage-1 and stage-2 variants.
4. **Decision log (ADR-style table):** decision, options, choice, reason, reversibility.
5. **Capacity and cost table** (Phase 1): component, SKU at 1K, SKU at 20K, monthly cost each.
6. **Security report:** threats considered, controls applied (OWASP item by item where relevant), scan results, open risks.
7. **Test report:** what was tested at each level (unit, integration, regression, E2E, manual, performance), results, coverage, and any gaps with a plan to close them.
8. **Risk register:** risk, likelihood, impact, mitigation, owner.
9. **Artifacts:** file paths for any code, Bicep, workflow, script or token file produced, with short descriptions.
10. **Checklist** of what is done and what is next.

Use Markdown, tables over prose where possible, and code blocks with language tags. Keep explanations tight; no marketing language.

---

## C. CONSTRAINTS (non-negotiable)

1. **Database schema and data values stay exactly the same.** No collection or field renames, no type changes, no value transformations, no deleting data. Additive indexes and safer write settings are allowed. Every migration step must be verifiable by counts and hashes.
2. **App name is "AirYatra"** in UI, code, emails, invoices, SEO metadata, PWA manifest and infrastructure naming (e.g. `rg-airyatra-prod-cin`). "Vaayu Prive" is only the theme source.
3. **Cloud is Microsoft Azure.** India regions for primary data (Central India primary, South India DR). Third-party SaaS (MongoDB Atlas, Razorpay, Twilio) is allowed only where it runs in or is contractually compliant for India.
4. **API contract is frozen.** Same paths, methods, request and response shapes, so the existing front end and any mobile clients keep working.
5. **Security:** no secrets in code, images or git history going forward (and a plan to purge existing ones and rotate keys); least-privilege managed identities; private endpoints; TLS 1.2+; webhook signatures verified; PII and KYC encrypted at rest and in transit; audit logs retained.
6. **Scale by configuration, not re-architecture:** the same design must serve 1,000 users at launch and 20,000 later by changing SKUs, replica counts and autoscale rules.
7. **Cost-aware:** launch footprint should be the smallest that still gives HA for the API and backups for the DB. Call out anything above roughly ₹1 lakh/month at launch.
8. **Behaviour-preserving refactors only** until tests cover the flow being touched.
9. **No destructive or production action** (deleting data, DNS cutover, rotating live payment keys) without my explicit written approval in the conversation.
10. **Accessibility and performance** targets in Phase 4 and Phase 5 are acceptance criteria, not suggestions.
11. **Testing is mandatory, every time.** No code change is proposed or merged without the tests required by Section Q and the Definition of Done. This applies to the refurbishment and to all later feature work and bug fixes.
12. **Object-oriented code, every time.** All new and refactored code follows Section E. Any exception needs a written reason in the PR.
13. **Security hardening, every time.** Every change meets Section S; a High or Critical security finding blocks the release. Security is never traded for speed without my written approval.
14. If any instruction conflicts with another, stop and ask instead of picking silently.

---

Start with **Phase 0** now.
