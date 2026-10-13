# AirYatra test strategy (Phase 0 deliverable, master prompt Q.6 row 0)

Status: draft for approval. Inputs: master prompt sections Q.1–Q.6 and S.5, and the Phase 0 audit in `docs/phase0/`. Facts about the current repo carry `file:line`; anything not verifiable from code is marked **ASSUMPTION**.

## 1. Inventory of existing tests

### 1.1 What exists

| Location | Files | Test functions | Style | Target | Areas covered |
|---|---|---|---|---|---|
| `backend/tests/` | 16 (+ `__init__.py`) | 228 | pytest, `requests` over HTTP | `BASE_URL` = `REACT_APP_BACKEND_URL` env or read from `/app/frontend/.env` (e.g. `backend/tests/test_auctions.py:16-17`, `backend/tests/backend_test.py:11-12`) | see 1.2 |
| `backend_test.py` (repo root) | 1 | 45 methods on `AirYatraAPITester` (`:6`, runner `:32`, `main()` `:1403`) | script with its own pass/fail counter, not pytest assertions | default `https://aviation-erp-2.preview.emergentagent.com` (`:7`) | health, register/login, membership, many module smoke checks |
| `pricing_engine_specific_tests.py` (repo root) | 1 | 7 | script (`__main__` `:376`) | same Emergent preview host (`:10`) | pricing engine endpoints |
| `tests/` (repo root) | `__init__.py` only | 0 | — | — | — |
| `test_reports/` | `iteration_*.json`, `pytest/*.xml` | — | Emergent testing-agent output (e.g. `test_reports/iteration_25.json`) | — | historical results, not runnable |
| Front end | 0 | 0 | No Jest/RTL/Playwright/Cypress in `frontend/package.json` (only `"test": "craco test"` `:73`); no `*.test.*`/`*.spec.*` in `frontend/src` | — | none |
| Tooling | `pytest==9.0.2` is in the **runtime** `backend/requirements.txt:101`; no `pytest-asyncio`, `pytest-cov`, coverage config, or CI job that runs tests | | | | |
| Phase 0 audit tests (new) | `tools/audit/test_collection_inventory.py`, `tools/audit/test_route_map.py` | 18 | pure unit tests | none | audit tooling only |

### 1.2 Per-file view of `backend/tests`

| File | Tests | Endpoints exercised (main prefixes) | Notes |
|---|---|---|---|
| `backend_test.py` | 14 | membership | |
| `test_account_lockout.py` | 13 | `/api/auth/*` lockout/unlock | Also connects to Mongo directly with `pymongo.MongoClient(MONGO_URL)` (`:20,26,34`) to reset state |
| `test_admin_documents.py` | 18 | `/api/admin/documents`, `/api/vault/*` | |
| `test_aircraft_and_pricing.py` | 25 | aircraft catalog, pricing | |
| `test_aircraft_catalog_smart.py` | 10 | `/api/aircraft/*` | Imports `database.get_database` for cleanup (`:223-225`) |
| `test_auctions.py` | 25 | auctions / exchange | |
| `test_compliance_monitor.py` | 23 | `/api/compliance/*` | |
| `test_emergency_booking.py` | 14 | `/api/emergency/*` | |
| `test_finance_phase5.py` | 13 | `/api/finance/phase5/*` | |
| `test_hrms.py`, `test_hrms_phase4.py`, `test_hrms_phase5.py`, `test_hrms_phase6.py` | 8 / 7 / 7 / 10 | `/api/hr/*`, `/api/erp/operator` | |
| `test_legal_and_routes.py` | 17 | `/api/legal/*`, `/api/routes/*` | |
| `test_stripe_payments.py` | 8 | `/api/payments/stripe/*` | Uses fixed customer/admin passwords (`:10-12`) |
| `test_vault_object_storage.py` | 16 | `/api/vault/*` | Asserts Emergent Object Storage behaviour (`:94,101`) |

### 1.3 Characteristics and problems
- **All existing tests are live, black-box API checks** against a running deployment and its shared database (no app instance, no fixtures, no isolation). They cannot run in CI without an environment, mutate shared data, and depend on seeded accounts whose passwords are committed (SECURITY_AUDIT S-03).
- No unit tests for business logic (pricing engine `backend/services/pricing_engine.py`, GST, commission, settlement, OTP/TOTP, encryption).
- No coverage measurement, no contract (OpenAPI) snapshot, no data-shape checks, no load tests, no front-end tests, no E2E, no visual regression.
- Payment tests use Stripe test mode through `emergentintegrations`; nothing covers Razorpay, RazorpayX or Cashfree; no webhook-signature tests.

## 2. Gap analysis against the 10 critical journeys (master prompt Q.2)

Legend: ✔ some coverage, ◐ partial/indirect, ✘ none. "Existing" refers to the live HTTP tests above.

| # | Journey | Unit | Integration | E2E | Regression | Existing evidence | Key gaps and known defects to pin first |
|---|---|---|---|---|---|---|---|
| 1 | Register, login, Google login, 2FA, lockout/unlock | ✘ | ◐ | ✘ | ✘ | `test_account_lockout.py` (lockout/unlock); `backend_test.py` register/login | Google/Emergent callback auth bypass (SECURITY S-02) needs a failing negative test; TOTP setup/verify; OTP expiry/reuse; rate limits (S-14); token revocation |
| 2 | Search/quote → booking (single, multi-leg) → payment (Razorpay, Stripe, Cashfree) → webhook → GST invoice → boarding pass | ✘ | ◐ (Stripe only) | ✘ | ✘ | `test_stripe_payments.py`, `test_aircraft_and_pricing.py`, `pricing_engine_specific_tests.py` | Razorpay verify mock path and IDOR (S-05), unsigned webhook (S-04), booking lookup by ObjectId bug (`razorpay_routes.py:318-320`), Cashfree pay-in not implemented, GST invoice maths, boarding pass; golden pricing table |
| 3 | Inquiry broadcast → operator quote → customer acceptance | ✘ | ✘ | ✘ | ✘ | none | `inquiry_broadcast_service.py`, `quote_routes.py` |
| 4 | Cancellation and refund per policy | ✘ | ✘ | ✘ | ✘ | none | Refund maths, Razorpay refund (`razorpay_routes.py:446`), double-refund race |
| 5 | KYC/document upload, encryption, download, expiry alerts | ✘ | ◐ | ✘ | ✘ | `test_admin_documents.py`, `test_vault_object_storage.py`, `test_compliance_monitor.py` | Encryption key handling (S-09), upload validation (S-16), public uploads (S-12), mocked KYC (S-21), decrypt existing `.enc` files |
| 6 | Operator settlement and RazorpayX payout | ✘ | ✘ | ✘ | ✘ | none | `services/settlement_service.py`, `payment_gateway_service.py`; no payout webhooks exist |
| 7 | Village landing permission → multi-level approval | ✘ | ✘ | ✘ | ✘ | none | `landing_infrastructure_routes.py`, `admin_landing_permission_routes.py`, `services/approval_workflow.py` |
| 8 | SOS alert → admin dashboard → notification | ✘ | ✘ | ✘ | ✘ | none | Admin SOS dashboard calls `/api/api/sos/...` and never loads (CODE_MAP §6.1) |
| 9 | Role-based access, negative tests per role | ✘ | ◐ | ✘ | ✘ | scattered 401/403 asserts | Matrix of 17 roles × 1,241 endpoints; WebSocket auth (S-18); mass assignment (S-15) |
| 10 | Scheduler jobs run exactly once with multiple replicas | ✘ | ✘ | ✘ | ✘ | none | 16 interval jobs inside the API process (CODE_MAP §5) |

**Conclusion:** no journey meets Q.2 today. Phase 3 starts each module with characterisation tests (pin current behaviour, including the defects listed, marked `xfail(strict=True)` with a ticket when the behaviour is a known bug) before refactoring.

## 3. Strategy per test level (Q.1)

| Level | Scope for AirYatra | Tooling | Where / when it runs | First deliverables |
|---|---|---|---|---|
| **Unit** | Pricing engine (`services/pricing_engine.py`, `pricing_models.py`), GST/commission/settlement maths, money rounding (float rupees ↔ int paise at gateway edge, DATA_DICTIONARY §2.3), date helpers (ISO string vs BSON Date, §2.2), validators, permission checks, OTP/TOTP, encryption wrapper, React components and hooks | Back end: `pytest`, `pytest-asyncio`, `pytest-cov`, `mongomock-motor` or repository fakes, `freezegun`, `hypothesis` for money/date properties. Front end: Jest (CRA built-in via `craco test`) or Vitest after any Vite move + React Testing Library + MSW | Every commit/PR, < 5 min, GitHub Actions | Golden pricing table; GST and refund calculators; role checker |
| **Integration** | FastAPI app in-process (`httpx.AsyncClient` with `ASGITransport`) + real MongoDB (Testcontainers `mongo:7` or the chosen Atlas/Cosmos-compatible image) + Redis + Azurite (Blob); payment providers in sandbox or recorded contracts; webhook signature verification; each scheduler job run once against seeded data | `pytest`, `testcontainers`, `respx`/`vcrpy` for third-party contracts, Razorpay/Stripe test keys from CI secrets, Twilio test credentials | Every PR in CI (Docker service containers) | Convert the 228 live tests into in-process tests with fixtures (seed via extended `backend/scripts/seed_demo_users.py`, passwords from env); contract tests for each replaced Emergent adapter (storage, LLM, OAuth) |
| **End-to-end** | Browser journeys of Q.2 across front end, API and DB | Playwright (Chromium desktop + 360 px mobile viewport), axe-core | Smoke subset on every PR to `main` against an ephemeral or `dev` environment; full suite nightly on `staging` | Login (password + TOTP), booking + Razorpay test payment, operator quote, admin SOS dashboard |
| **Regression** | (a) all suites; (b) OpenAPI contract snapshot of 1,241 endpoints (fail on removed/changed path, field, type); (c) data-shape check: sampled documents per collection validated against the Phase 0 data dictionary (`collection_inventory.json` → JSON Schema per collection, tolerant of the documented mixed formats); (d) Playwright visual snapshots; (e) golden pricing table | `schemathesis`/`openapi-diff` (or a pytest snapshot of `app.openapi()`), JSON Schema validator, Playwright `toHaveScreenshot` | Every PR (a–c, e); visual on UI PRs; full pack before release | Baseline `openapi.json` from the current app; per-collection schemas generated from the inventory |
| **Manual / exploratory** | Usability, Vaayu Prive theme review, real devices, payment sandbox flows, screen reader, role workflows | Test cases in `docs/testing/manual/` (one per role × journey), release checklist, UAT sign-off sheet | Every release on `staging`; UAT before go-live | Charters for the 10 journeys |
| **Performance** | Browse/search, quote, booking + payment, admin/operator dashboards, WebSocket chat, file upload; baseline, load (100 → 500 concurrent), stress, spike (3×), soak (2–4 h) against Q.3 targets | k6 (scripts in repo) or Azure Load Testing; Lighthouse CI; Application Insights | Smoke perf on PRs touching hot paths; full suite before each release and after infra/SKU changes | Scenario scripts + data generators; see §5 for the baseline |
| **Security** (S.5) | SAST, secrets, dependencies, DAST, security unit/integration tests (authZ per role, IDOR, NoSQL injection payloads, webhook signature rejection, rate limits, upload rejection) | CodeQL (existing template), Bandit, Semgrep, ESLint security plugin, gitleaks, pip-audit, npm audit, Trivy, OWASP ZAP | Every PR (blocking on High); ZAP nightly/weekly | Failing tests for S-02, S-04, S-05, S-07, S-15, S-18 first |

### Test data rules (Q.4)
- Never hit production data or live keys. Seeded fixtures (extend `backend/scripts/seed_demo_users.py` to read passwords from env) or an anonymised production copy with PII masked (Aadhaar/PAN/phone/e-mail).
- Fixtures must reproduce the real value formats (UUID `id` strings, ISO strings **and** BSON Dates where the dictionary says mixed, float rupees, enum strings outside the Pydantic enums) so tests do not "fix" data shapes silently.

## 4. Coverage and gates (Q.4)

| Gate | Threshold / rule | Tool |
|---|---|---|
| Back-end line coverage | ≥ 80 % overall; ≥ 90 % for pricing, payments, invoicing, settlements, auth | `pytest-cov` + `coverage.py` fail-under per package |
| Front-end coverage | ≥ 70 % on shared components and booking flow | Jest/Vitest coverage thresholds |
| Diff coverage | ≥ 80 % on changed lines; never decreases | `diff-cover` |
| Merge blockers | lint/format/type (ruff, black, mypy, ESLint), unit, integration, API contract diff, data-shape check, security scans, E2E smoke, perf smoke on hot-path PRs | GitHub Actions required checks + branch protection |
| Flaky tests | Fixed or quarantined with owner + ticket within 48 h, never silently skipped | `pytest-rerunfailures` only in quarantine job |

Baseline today: 0 % measured (no coverage tooling). Expect coverage to ramp module by module in Phase 3; the gate applies to changed lines from the first Phase 3 PR.

## 5. Baseline performance run (pending)

Q.6 asks for a baseline perf run against the current Emergent deployment. **Not done: this environment has no access to the Emergent deployment** (and the audit must stay read-only). To run it when access is granted:
1. Get written approval and a time window; agree on read-mostly scenarios (no real payments, no e-mails/SMS; use a test tenant/accounts created for the run).
2. k6 scripts for: anonymous browse (`/api/landing/points`, `/api/aircraft/public`, search), authenticated customer dashboard, quote request, admin dashboard; 10 → 50 → 100 virtual users, 10 min each; record p50/p95/p99, error rate, throughput.
3. Store results under `docs/testing/perf/baseline-<date>/` as the comparison point for Phase 5.
Note: in-process caches and rate limits (CODE_MAP §1.2) mean single-replica numbers will not scale linearly; record replica count with the results.

## 6. Order of work
1. Phase 1: CI skeleton with the gates above (empty suites allowed), Testcontainers images, Azure test environments, Azure Load Testing resource sizing.
2. Phase 2: migration test pack (counts, hashes, index parity, data-shape check, regression suite on the migrated DB).
3. Phase 3: per module, characterisation tests → refactor → unit/integration to the coverage gate; security regression tests for every SECURITY_AUDIT finding; converted live tests; adapter contract tests.
4. Phase 4: component, visual and accessibility tests.
5. Phase 5: full Q.3 performance suite at 1K and 20K profiles, DR restore test, UAT sign-off.
