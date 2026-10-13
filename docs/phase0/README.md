# Phase 0: Discovery and audit

**Summary.**
1. AirYatra is one large FastAPI app (126 route modules, 1,241 endpoints) over MongoDB with 285 collections, written by the Emergent builder and still tied to Emergent for AI, file storage and Google sign-in.
2. Data conventions are consistent enough to migrate as-is (UUID `id` strings, rupees as floats), but dates are a mix of ISO strings and real dates, and the app database probably has none of the indexes the code declares.
3. Several security problems are serious enough to fix before anything else: anyone can log in as any user through the Emergent Google callback, payments can be marked paid without a real payment, and passwords, an LLM key and KYC files are committed to git.
4. About a third of the back-end endpoints are never called by the front end, 38 front-end calls go to URLs that do not exist, and five performance/DB helper modules are dead code; the GitHub workflows do not build or test this app.
5. Existing tests are 280 live HTTP checks against a shared server; there are no unit, front-end, E2E, coverage or load tests yet, and the baseline performance run is pending access to the Emergent deployment.

All work in this phase was read-only: no existing file, database, branch or cloud resource was changed.

## Documents

| Document | Content |
|---|---|
| [DATA_DICTIONARY.md](DATA_DICTIONARY.md) | Collections, fields, value formats, enums, ID strategy, indexes (derived from code) |
| [collection_inventory.json](collection_inventory.json) | Raw static-analysis output behind the data dictionary |
| [DEPENDENCY_INVENTORY.md](DEPENDENCY_INVENTORY.md) | Every Emergent dependency and third-party integration, env vars, Azure decision placeholders |
| [SECURITY_AUDIT.md](SECURITY_AUDIT.md) | 27 findings with severity, evidence and fixes (feeds master prompt S.1) |
| [CODE_MAP.md](CODE_MAP.md) | Duplicate/dead code, workflows, scheduler jobs, front-end vs back-end API usage |
| [route_map.json](route_map.json) | Raw endpoint ↔ front-end call map |
| [../testing/TEST_STRATEGY.md](../testing/TEST_STRATEGY.md) | Test inventory, gap analysis against the 10 critical journeys, strategy, gates |

Tools (stdlib only, re-runnable; tests: `python3 -m pytest tools/audit -q`):
`tools/audit/collection_inventory.py`, `tools/audit/render_data_dictionary.py`, `tools/audit/route_map.py`.

## Top 10 findings

| # | Finding | Severity | Where |
|---|---|---|---|
| 1 | Emergent Google callbacks trust the browser's e-mail claim and return a JWT (with existing roles, 2FA skipped) for any account, including admins | Critical | SECURITY_AUDIT S-02 (`backend/routes/auth_routes.py:1610`, `backend/routes/google_auth_routes.py:466,498`) |
| 2 | Payment verify returns success in mock mode and marks any `booking_id` paid; Razorpay webhook processes unsigned events | Critical | S-05, S-04 (`backend/services/payment_service.py:148-159`, `backend/routes/razorpay_routes.py:250-260`) |
| 3 | Secrets in the repo: fallback LLM key (also unlocks Emergent storage), Gmail app password and staff passwords | Critical | S-01, S-03 (`backend/services/ai_service.py:26`, `memory/test_credentials.md`) |
| 4 | Encrypted Aadhaar files and staff selfies/receipts committed to git; KYC key falls back to a random per-process key | Critical / High | S-08, S-09 |
| 5 | Personal documents served from an unauthenticated static mount `/api/uploads`; WebSockets accept anyone | High | S-12, S-18 |
| 6 | MongoDB runs with `w:1, journal:false`; the 57 declared indexes are created on a hard-coded `airyatra` DB, not `DB_NAME` | High | S-10; DATA_DICTIONARY §2.6 (`backend/database.py:22-23`, `backend/db_optimization.py:129`) |
| 7 | Dates stored as ISO strings at 854 sites and BSON Dates at 207, mixed inside 11 collections; money in float rupees with paise only at the gateway edge | Data (preserve as-is) | DATA_DICTIONARY §2.2–2.3 |
| 8 | Emergent lock-in: `emergentintegrations` (LLM + Stripe), Emergent object storage, Emergent OAuth, Emergent scripts/PostHog in `index.html`, `.emergent/` cron | Migration blocker | DEPENDENCY_INVENTORY §1 |
| 9 | 16 APScheduler jobs run inside every API replica (payroll, payment reminders, investor e-mails would duplicate); rate limits and caches are in-process; Redis is never used | High (scale-out blocker) | CODE_MAP §5, §1.2; S-14 |
| 10 | 33 % of endpoints unused by the UI, 38 broken front-end calls (e.g. admin SOS dashboard requests `/api/api/sos/...`), duplicate services/middlewares, and 10 of the 11 workflow files do not match the app | Medium | CODE_MAP §1, §4, §6 |
