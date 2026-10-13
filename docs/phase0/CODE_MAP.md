# Code map: duplicates, dead code, jobs and API usage (Phase 0)

Static analysis of `HEAD`; nothing was executed against a server. Helper scripts: `tools/audit/route_map.py` (endpoint ↔ front-end call map, raw output [`route_map.json`](route_map.json)) and `tools/audit/collection_inventory.py`. "Dead" means *not imported by anything reachable from `backend/server.py`*; it is safe to delete only after the Phase 3 characterisation tests.

## 1. Duplicate and overlapping modules

### 1.1 Services in two places

| Concern | Copy A | Copy B | Who imports which | Recommendation |
|---|---|---|---|---|
| AI service | `backend/ai_service.py` (192 lines; `settings.emergent_llm_key`, mock fallback, methods `get_price_suggestion`, `verify_document`, `get_route_recommendations`) | `backend/services/ai_service.py` (471 lines; adds chatbot, booking summary, **hard-coded fallback key** `:26`) | A ← `routes/booking_routes.py`, `routes/chatbot_routes.py`, `routes/pilot_document_routes.py` (`from ai_service import ai_service`); B ← `routes/ai_routes.py:8` only. Plus three more direct `LlmChat` users bypassing both: `routes/ai_advisor_routes.py:19`, `routes/ai_routes.py:203`, `routes/finance_phase4_routes.py:225,279` | One `AIService` interface in `services/`, Azure OpenAI adapter, route all 6 callers through it; delete A |
| E-mail | `backend/email_service.py` (68 lines, SendGrid) | `backend/services/email_service.py` (2,024 lines, SMTP via `aiosmtplib`) | A ← `routes/booking_routes.py`, `routes/quote_routes.py`, `routes/maintenance_routes.py`; B ← 14 modules incl. `auth_routes.py`, `scheduler.py`, `services/inquiry_broadcast_service.py`. `services/notification_service.py:63` has a third SendGrid path | One notifier interface; decide provider (DEPENDENCY_INVENTORY §2) |
| Storage | local disk (`server.py:409-422`, KYC, HR, landing routes) | `backend/s3_service.py` (boto3) and `backend/services/storage_service.py` (Emergent) | see DEPENDENCY_INVENTORY E6 and §2 | One storage interface → Azure Blob |
| Payments (Razorpay) | `routes/payment_routes.py` + `services/payment_service.py` (`/api/payments/*`, used by the front end) | `routes/razorpay_routes.py` (`/api/razorpay/*`, own client, webhook) | Front end calls `payment_routes` (see §6); **no front-end call reaches `razorpay_routes`** (only Razorpay's webhook would) | Merge behind one `PaymentGateway` port; keep paths |
| Google OAuth | `routes/auth_routes.py:1601-1770` | `routes/google_auth_routes.py` | Duplicate endpoints, see §1.3 | One OAuth adapter |

### 1.2 Middleware / performance modules

| Module | Lines | Imported by `server.py`? | Imported anywhere? | What it is | Status |
|---|---|---|---|---|---|
| `ultra_performance_middleware.py` | 214 | **Yes** (`server.py:13-19`, added `:190-202`) | server only | In-process response cache for 7 public GET prefixes, token-bucket rate limit (in-memory), timing/security headers, keep-alive headers | **Live**; replace cache/limits with Redis versions |
| `security_middleware.py` | 656 | **Yes** (`server.py:25`; `init_security_middleware` `:470-476`) | also `routes/auth_routes.py`, `routes/kyc_verification_routes.py`, `routes/customer_kyc_routes.py` | slowapi limiter, `AuditLogger`, `SessionManager`, `FileEncryption` (KYC) | **Live** |
| `db_optimization.py` | 146 | **Yes** (`server.py:20`, called `:466`) | server only | `INDEXES` table + `optimize_database()` (uses hard-coded DB `airyatra`, `:129`) | **Live but likely ineffective** (DATA_DICTIONARY §2.6) |
| `middleware.py` | 110 | No (not an ASGI middleware) | **~75 route modules** | Auth dependencies `get_current_user`, `require_roles`, token from header/cookie, revocation check | **Live** (misnamed: it is the auth module) |
| `performance_middleware.py` | 208 | No | **Nothing** | Older `CacheMiddleware`, `RateLimitMiddleware`, `PerformanceHeadersMiddleware` | **Dead** (superseded by `ultra_performance_middleware.py`) |
| `high_performance_cache.py` | 279 | No | **Nothing** | L1 memory + L2 Redis cache (`REDIS_URL`) | **Dead** → Redis is never used at runtime |
| `api_optimization.py` | 176 | No | **Nothing** | Projection/pagination helpers, `batch_fetch` | **Dead** |
| `connection_pool.py` | 83 | No | **Nothing** | Second Motor client + `get_db()` | **Dead** |
| `optimized_mongo.py` | 163 | No | **Nothing** | Third Motor client wrapper (`ReadPreference`), bulk helpers | **Dead** |
| `database.py` | — | Yes (`server.py:9`) | everywhere (`get_database()` ×929) | The real Motor client (`w:1`, `journal:False`) | **Live** |

Evidence for "Nothing": `grep -rlnE "^\s*(from X import|import X\b)" backend --include=*.py` returns only the module itself for each dead module.

### 1.3 Duplicate endpoint definitions (same method + path)

| Method + path | Definitions | Effective handler (first included wins) |
|---|---|---|
| `POST /api/auth/google/emergent-callback` | `routes/auth_routes.py:1610`, `routes/google_auth_routes.py:498` | `auth_routes` (`server.py:208` before `:248`) |
| `GET /api/auth/google/settings` | `routes/auth_routes.py:1761`, `routes/google_auth_routes.py:31` **and** `:477` (twice in the same file) | `auth_routes` |
| `GET /api/chat/conversations` | `routes/chat_routes.py:17`, `routes/pilot_chat_routes.py:21` | `chat_routes` (`server.py:230`) |
| `GET/PUT /api/notifications/preferences` | `routes/notification_routes.py:125,148`, `routes/push_notification_routes.py:199,216` | `notification_routes` |
| `PUT /api/notifications/mark-read/{notification_id}` | `routes/notification_routes.py:38`, `routes/push_notification_routes.py:175` | `notification_routes` |

The shadowed handlers are dead code today; keep paths unchanged when consolidating.

## 2. Route modules and `server.py`
All 126 modules in `backend/routes/` are imported **and** included by `backend/server.py` (128 `include_router` calls, `:208-402`, including `partner_routes.api_router` at `:264`). `content_routes` is imported twice (`:116`, `:343`) but included once (`:344`). No route module is orphaned; the dead code is at module level (§1.2) and handler level (§1.3, §6.2).

## 3. Other dead or broken code noticed
| Item | Evidence | Note |
|---|---|---|
| `bookings` lookup by ObjectId of a UUID | `routes/razorpay_routes.py:318-320`; `routes/command_center_routes.py:107,113,134` | Never matches UUID `id` documents (ASSUMPTION: raises or no-ops) |
| Chat persistence awaits a sync function | `routes/websocket_chat_routes.py:122,157` (`await get_database()`) | TypeError at runtime (ASSUMPTION caught by the loop's error handling) |
| Push notifications stub | `routes/push_notification_routes.py:39-50` | No provider |
| `twilio` package missing from `backend/requirements.txt` | `services/notification_service.py:112,162` import it lazily | SMS/WhatsApp silently disabled |
| `optimize_database()` creates its own client | `db_optimization.py:127-129` | Extra connection pool per start, wrong DB name |
| Backend dev tools in runtime requirements | `backend/requirements.txt:18,35,60,73,101` (`black`, `flake8`, `isort`, `mypy`, `pytest`) | Split runtime/dev requirements (S.2 A06) |

## 4. GitHub workflows (`.github/workflows/`)

None of the workflows builds, tests or deploys this FastAPI + CRA application. Repository facts used below: there is no root `package.json`, no `environment.yml`, no `setup.py`/`pyproject.toml`, and no lockfile in `frontend/`.

| File | Trigger | What it does | Matches the app? | Recommendation |
|---|---|---|---|---|
| `codeql.yml` | push/PR to `main`, schedule | CodeQL for `actions`, `javascript-typescript`, `python` (`:46-51`) | **Partly** (useful template) | Keep, tune paths; becomes the SAST gate (S.5) |
| `deploy.yml` | `workflow_dispatch` | Despite the name, generates **Mongoose/Node** models (`backend/models/*.js`, `:46-776`) and pushes a branch with `contents: write` (`:21-23,819-823`) | **No** (back end is Python/Motor) | Delete |
| `main..github/workflows/deploy.yml` | `workflow_dispatch` (never runs: GitHub only reads `.github/workflows/*` one level deep) | Byte-identical copy of `deploy.yml` (`cmp` reports no difference); path created by a mistyped copy into `.github/workflows/main..github/workflows/` | **No** | Delete the whole `main..github/` directory |
| `node.js.yml` | push/PR to `main` | `npm ci && npm run build && npm test` at repo root, Node 18/20/22 (`:29-31`) | **No** (no root `package.json`; frontend has no lockfile so `npm ci` fails) | Replace with front-end CI in `frontend/` |
| `webpack.yml` | push/PR to `main` | `npx webpack` at root | **No** (CRA/CRACO) | Delete |
| `npm-publish.yml` | release | `npm publish` | **No** (app, not a package) | Delete |
| `python-publish.yml` | release | Build + upload to PyPI | **No** | Delete |
| `python-package-conda.yml` | every push | `conda env update --file environment.yml`, flake8, pytest (`:15-30`) | **No** (no `environment.yml`; would run live HTTP tests) | Delete |
| `pylint.yml` | every push | `pylint $(git ls-files '*.py')` on Python 3.8-3.10 (`:10,22`) | **No** (code needs 3.11+ features/pins; no config; would fail) | Replace with ruff/black/mypy job |
| `jekyll-docker.yml` | push/PR to `main` | Builds a Jekyll site | **No** | Delete |
| `generator-generic-ossf-slsa3-publish.yml` | release, dispatch | SLSA provenance for release artefacts | Not yet (no release artefacts) | Revisit in Phase 1 (signed images) |

## 5. Background jobs (`backend/scheduler.py`)

`AsyncIOScheduler()` (`backend/scheduler.py:14`) is started inside the API process on every startup (`backend/server.py:480` → `start_scheduler()` `scheduler.py:820-968`) and stopped on shutdown (`server.py:488`). With N API replicas every job runs N times. All triggers are `IntervalTrigger` measured from process start (not wall-clock cron), so "monthly"/"Monday" jobs poll and use date checks inside the job. Several jobs guard with a read-then-write "already sent/last run" check, which is **not atomic** and does not prevent duplicates across replicas (ASSUMPTION; Q.2 item 10). Admin endpoints can also trigger or pause jobs in-process (`backend/routes/scheduler_routes.py:33,48`), which only affects the replica that serves the request.

| Job id | Trigger | Function (line) | What it does | Collections touched | Duplicate-run risk |
|---|---|---|---|---|---|
| `auto_reassign_leads` | every 15 min | `auto_reassign_stale_leads` (`:16`) | Reassigns CRM leads not contacted within 1 h, notifies staff, audit log | `crm_leads`, `users`, `notifications`, `audit_logs` | Double reassignment / notifications |
| `send_notifications` | every 5 min | `send_pending_notifications` (`:103`) | Drains `notification_queue` (e-mail/SMS) | `notification_queue` | **Duplicate e-mails/SMS** |
| `cleanup_sessions` | every 1 h | `cleanup_old_sessions` (`:154`) | Deletes `sessions` older than 7 days | `sessions` | Idempotent |
| `daily_reports` | every 24 h | `generate_daily_reports` (`:180`) | Builds a daily stats document | `bookings`, `crm_leads`, `daily_reports` | Duplicate report docs |
| `voucher_expiry_alerts` | every 12 h | `send_voucher_expiry_alerts` (`:243`) | E-mails members whose vouchers expire within 7 days | `reward_redemptions`, `users` | Duplicate e-mails (flag check not atomic) |
| `auction_ending_reminders` | every 10 min | `send_auction_ending_reminders` (`:310`) | E-mails watchers when an auction closes within 60 min | `exchange_auctions`, `exchange_watchlist` | Duplicate e-mails |
| `monthly_board_report` | every 12 h | `send_monthly_board_report` (`:367`) | On the 1st: e-mails investor board report PDF | `ceo_settings` | Duplicate investor e-mails |
| `monthly_payroll_run` | every 12 h | `run_monthly_payroll` (`:412`) | On the 1st: generates previous month payroll, e-mails HR | `hr_settings`, `users` (+ payroll writes) | **Duplicate payroll runs (money)** |
| `attendance_nudge` | every 15 min | `send_attendance_nudges` (`:484`) | 11:00 IST: e-mails staff who have not checked in | `attendance`, `company_holidays`, `hr_settings`, `leaves`, `users` | Duplicate e-mails |
| `erp_weekly_digest` | every 6 h | `send_erp_weekly_digest` (`:550`) | Monday: operator ERP digest e-mail | `aircraft`, `aircraft_documents`, `flight_records`, `hr_settings`, `maintenance_schedules`, `operators`, `users` | Duplicate e-mails |
| `auto_balance_reminders` | every 12 h | `send_auto_balance_reminders` (`:629`) | 3 days before departure: balance payment reminder + payment link | `inquiries`, `payment_transactions`, `users` | Duplicate payment links |
| `pilot_document_expiry` | every 24 h | `check_pilot_document_expiry` (`:971`) | Notifies operators of pilot documents expiring in 30 days | `pilots`, `operators`, `users`, `notifications` | Duplicate notifications |
| `stripe_settlement_sync` | every 24 h | `sync_stripe_settlements` (`:1208`) | Pulls Stripe balance transactions/payouts (`STRIPE_API_KEY`) | `stripe_balance_transactions`, `stripe_settlements`, `settlement_sync_logs` | Duplicate rows unless upserted (ASSUMPTION) |
| `razorpay_settlement_sync` | every 24 h | `sync_razorpay_settlements` (`:1329`) | Pulls Razorpay settlements | `razorpay_settlements`, `settlement_sync_logs` | As above |
| `scheduled_finance_reports` | every 6 h | `process_scheduled_finance_reports` (`:1410`) | Generates/e-mails due finance report PDFs (`generate_finance_report_pdf` `:1572`) | `scheduled_finance_reports` | Duplicate reports |
| `daily_compliance_monitor` | every 24 h | `run_daily_compliance_monitor` (`:1670`) | Hides aircraft with expired insurance/documents/maintenance; writes compliance report | `aircraft_catalog`, `compliance_reports` | Mostly idempotent |

Target (Phase 1/3): one single-replica worker (Container Apps job or worker app) owns the scheduler; the API never starts it; each job takes a Mongo/Redis lease (`job_locks` with TTL) and records runs; wall-clock cron triggers in IST for the calendar jobs.

## 6. API usage: front end vs back end

Method: `tools/audit/route_map.py` parses every `APIRouter(prefix=...)` and decorator in `backend/server.py` + `backend/routes/*.py` (all mounted under `/api`), and scans `frontend/src` for `api.<verb>('/x')` (axios instance with `baseURL = REACT_APP_BACKEND_URL + '/api'`, `frontend/src/services/apiClient.js:9-10`), `fetch/axios(`${API_URL}/api/x`)`, `${API}/x` and WebSocket URLs. Template parts become wildcards; matching ignores the HTTP verb when `fetch` options cannot be read.

| Metric | Value |
|---|---|
| Back-end endpoints (HTTP + WebSocket) | **1,241** in 127 modules (126 route modules + `server.py`) |
| Front-end call sites found | **926** (689 via `api.*`, the rest via `fetch`/`axios` with `${API_URL}` etc.) |
| Call sites whose URL is built in a variable (not resolvable) | 1 |
| Back-end endpoints referenced by at least one call site | **834 (67%)** |
| Back-end endpoints never referenced by the front end | **407 (33%)** |
| Front-end call sites with **no matching back-end route** | **41** (38 real, 3 false positives in comments/base-URL constants) |
| Route modules with **zero** front-end usage | 17 (table below; `server` = `/health` and `/api/performance/stats`) |

### 6.1 Front-end calls that hit no back-end route (broken features)

| Cause | Call sites (file:line under `frontend/src/`) | Back end actually exposes |
|---|---|---|
| **Double `/api` prefix**: component passes `/api/...` to the axios instance whose `baseURL` already ends in `/api` → request goes to `/api/api/...` (404) | `components/admin/SOSDashboard.js:24,25,38,53`; `components/admin/KnowledgeBase.js:37-41,58,68,79`; `components/admin/InsuranceModule.js:24,25,38,54`; `components/admin/DynamicPricing.js:29,30,43,56,68`; `components/admin/RouteOptimization.js:48,60,73` | `/api/sos/admin/...`, `/api/knowledge/...`, `/api/insurance/...`, `/api/pricing/...`, `/api/routes/...` (these five modules therefore show 0 or near-0 usage) |
| **Prefix/name mismatch** | `components/admin/CalendarSync.js:17,18,28` (`/calendar/*`); `components/admin/PredictiveAnalytics.js:15` (`/analytics/predictive/dashboard`); `components/admin/VoiceVideoSupport.js:15` (`/voice-video/dashboard`); `components/admin/TwoFactorAuth.js:26` (`/2fa/setup`); `services/paymentService.js:5,6` (`/payment/create-order`, `/payment/verify`) | `/api/calendar-sync/*`; `/api/analytics-predict/*`; `/api/voice-video/admin/dashboard`; `/api/2fa/setup/totp`; `/api/payments/*` |
| **Endpoint does not exist** | `components/admin/AccountingIntegration.js:16,24` (`/accounting/dashboard`, `/accounting/export/{type}`); `components/admin/CommandCenter.js:81,84` (`/api/admin/approvals?status=...`); `components/admin/DocumentExpiryDashboard.js:49,52` (`/api/maintenance/aircraft-documents/expiring`, `/api/hr/employee-documents/expiring`) | `accounting_routes` has `/providers`, `/connect`, `/chart-of-accounts`, `/export-invoices`, ...; `admin_approval_routes` has `/queue`, `/{id}/approve`, ...; no `aircraft-documents/expiring` or `employee-documents/expiring` route in `maintenance_routes`/`hr_*` |
| False positives | `services/apiClient.js:91` (doc comment), `components/admin/PartnerManagement.js:12` (base URL constant) | n/a |

All of these are reachable from `pages/AdminDashboard.js` (e.g. imports at `:59-61,79,91-92`), so admins see empty or erroring panels. Notably the **admin SOS dashboard cannot load alerts** (Q.2 journey 8) and the customer-side `sos_routes` endpoints are not called by any component either (ASSUMPTION: SOS is triggered elsewhere, e.g. `command_center_routes`' `/command-center/sos-alert/...` used by `components/admin/CommandCenterDashboard.js:62`).

Phase 4 forbids changing API calls; these are recorded as **bugs to fix in Phase 3** with characterisation tests, not as part of the UI refresh.

### 6.2 Endpoint usage by route module

Sorted from least to most used (share of endpoints referenced). The front-end callers column shows up to two files. Full per-endpoint data, including the calling `file:line` for every endpoint, is in [`route_map.json`](route_map.json).

| Route module | Endpoints | Called by FE | Not called | Example FE callers |
|---|---|---|---|---|
| `accounting_routes` | 10 | 0 | 10 |  |
| `ai_reports_routes` | 3 | 0 | 3 |  |
| `ai_sales_routes` | 5 | 0 | 5 |  |
| `calendar_sync_routes` | 10 | 0 | 10 |  |
| `email_routes` | 8 | 0 | 8 |  |
| `fixed_route_pricing_routes` | 10 | 0 | 10 |  |
| `insurance_routes` | 9 | 0 | 9 |  |
| `knowledge_routes` | 11 | 0 | 11 |  |
| `kyc_verification_routes` | 8 | 0 | 8 |  |
| `legal_routes` | 6 | 0 | 6 |  |
| `pincode_live_routes` | 2 | 0 | 2 |  |
| `predictive_analytics_routes` | 7 | 0 | 7 |  |
| `razorpay_routes` | 8 | 0 | 8 |  |
| `route_optimization_routes` | 4 | 0 | 4 |  |
| `server` | 2 | 0 | 2 |  |
| `sos_routes` | 9 | 0 | 9 |  |
| `voice_video_routes` | 8 | 0 | 8 |  |
| `hangar_management_routes` | 10 | 1 | 9 | components/analytics/SmartHangarManagement.js |
| `currency_routes` | 7 | 1 | 6 | components/admin/CurrencyConverter.js |
| `pricing_routes` | 6 | 1 | 5 | components/customer/FlightPriceHistory.js |
| `admin_document_routes` | 4 | 1 | 3 | components/admin/AdminVerificationQueue.js |
| `ai_pricing_routes` | 4 | 1 | 3 | components/admin/AIPricingAdvisor.js |
| `flight_tracking_live_routes` | 8 | 2 | 6 | components/admin/LiveFlightTracking.js |
| `reviews_routes` | 11 | 3 | 8 | components/admin/ReviewsManagement.js |
| `ai_advisor_routes` | 7 | 2 | 5 | components/shared/AIBusinessAdvisor.js |
| `emergency_booking_routes` | 7 | 2 | 5 | components/booking/EmergencyBookingForm.js |
| `command_center_routes` | 10 | 3 | 7 | components/admin/CommandCenterDashboard.js |
| `push_notification_routes` | 10 | 3 | 7 | components/admin/PushNotifications.js, services/supportService.js |
| `field_tracking_routes` | 13 | 4 | 9 | components/admin/LiveTrackingDashboard.js |
| `admin_analytics_routes` | 6 | 2 | 4 | components/analytics/AdminAnalyticsDashboard.js |
| `multileg_booking_routes` | 9 | 3 | 6 | components/admin/MultiLegBooking.js |
| `operations_map_routes` | 3 | 1 | 2 | components/analytics/RealTimeOperationsMap.js |
| `membership_routes` | 11 | 4 | 7 | pages/MembershipPage.js |
| `two_factor_auth_routes` | 8 | 3 | 5 | components/admin/TwoFactorAuth.js |
| `pilot_availability_routes` | 5 | 2 | 3 | components/pilot/PilotMobilePortal.js |
| `aircraft_catalog_routes` | 21 | 9 | 12 | components/aircraft/AircraftCatalog.js, components/aircraft/AircraftComparison.js |
| `customer_kyc_routes` | 7 | 3 | 4 | components/customer/CustomerKYCUpload.js |
| `admin_settlement_routes` | 8 | 4 | 4 | services/adminService.js |
| `ai_routes` | 8 | 4 | 4 | components/shared/AIChatbot.js, services/analyticsService.js |
| `auction_routes` | 14 | 7 | 7 | components/auction/AuctionDashboard.js |
| `chatbot_routes` | 6 | 3 | 3 | components/admin/AIChatbot.js |
| `dgca_compliance_routes` | 10 | 5 | 5 | components/admin/DGCACompliance.js, components/operator/PilotDutyTracker.js |
| `document_vault_routes` | 20 | 10 | 10 | components/admin/AdminVerificationQueue.js, components/aircraft/AircraftDocumentManager.js |
| `finance_treasury_routes` | 14 | 7 | 7 | components/finance/BankReconciliation.js, components/finance/FinanceCommandCenter.js |
| `weather_routes` | 6 | 3 | 3 | components/admin/WeatherDashboard.js |
| `corporate_routes` | 17 | 9 | 8 | pages/CorporateDashboard.js |
| `boarding_pass_routes` | 9 | 5 | 4 | components/admin/BoardingPass.js |
| `inventory_routes` | 9 | 5 | 4 | components/admin/InventoryManagement.js |
| `finance_reconciliation_routes` | 7 | 4 | 3 | components/finance/PaymentReconciliation.js |
| `pilot_mobile_routes` | 19 | 11 | 8 | components/pilot/PilotMobilePortal.js |
| `notification_routes` | 10 | 6 | 4 | services/supportService.js |
| `payment_gateway_routes` | 37 | 23 | 14 | components/finance/ApprovalWorkflow.js, components/finance/BulkSalaryPayment.js |
| `notification_center_routes` | 8 | 5 | 3 | components/admin/PushNotifications.js, components/shared/GlobalNotificationCenter.js |
| `invoice_routes` | 11 | 7 | 4 | components/admin/InvoiceManagement.js |
| `content_routes` | 15 | 10 | 5 | components/landing/InvestorInterestSection.js, components/landing/TestimonialsSlider.js |
| `finance_advanced_routes` | 15 | 10 | 5 | components/finance/BankReconciliation.js, components/finance/ComplianceDashboard.js |
| `partner_routes` | 12 | 8 | 4 | components/admin/PartnerManagement.js |
| `price_breakup_routes` | 10 | 7 | 3 | components/pricing/PriceBreakup.js |
| `loyalty_routes` | 17 | 12 | 5 | components/admin/LoyaltyProgram.js, components/customer/LoyaltyRewards.js |
| `document_verification_routes` | 7 | 5 | 2 | components/admin/DocumentVerification.js |
| `analytics_routes` | 4 | 3 | 1 | services/analyticsService.js |
| `gst_routes` | 16 | 12 | 4 | components/finance/GSTDashboard.js, components/finance/GSTPayments.js |
| `marketing_routes` | 12 | 9 | 3 | components/admin/MarketingCampaigns.js |
| `predictive_maintenance_routes` | 4 | 3 | 1 | components/analytics/PredictiveMaintenance.js |
| `revenue_analytics_routes` | 4 | 3 | 1 | components/operator/OperatorRevenueDashboard.js |
| `favorites_routes` | 9 | 7 | 2 | components/shared/Favorites.js |
| `admin_routes` | 14 | 11 | 3 | components/admin/AdminCommissionSettings.js, services/adminService.js |
| `support_routes` | 10 | 8 | 2 | components/admin/SupportDashboard.js |
| `twilio_routes` | 10 | 8 | 2 | services/integrationsService.js |
| `finance_phase5_routes` | 11 | 9 | 2 | components/finance/AuditTrailDashboard.js, components/finance/ExpenseAnalytics.js |
| `auth_routes` | 40 | 33 | 7 | components/admin/CEODashboard.js, components/admin/LoginShieldDashboard.js |
| `google_auth_routes` | 6 | 5 | 1 | components/auth/GoogleLogin.js, services/authService.js |
| `hr_advanced_routes` | 19 | 16 | 3 | components/employee/EmpExpenses.js, components/hr/AutoSalaryPayment.js |
| `maintenance_routes` | 20 | 17 | 3 | components/admin/DocumentExpiryDashboard.js, components/admin/FleetMaintenance.js |
| `compliance_monitor_routes` | 7 | 6 | 1 | components/admin/ComplianceDashboard.js, components/aircraft/AircraftDocumentManager.js |
| `stripe_payment_routes` | 7 | 6 | 1 | components/customer/CustomerPaymentHistory.js, components/customer/InquiryStatus.js |
| `finance_phase4_routes` | 16 | 14 | 2 | components/finance/AIFinanceAssistant.js, components/finance/AutoReminders.js |
| `landing_infrastructure_routes` | 32 | 28 | 4 | services/landingService.js |
| `admin_payments_routes` | 9 | 8 | 1 | components/admin/AdminPaymentsDashboard.js, components/admin/BookingCalendarView.js |
| `finance_scheduled_routes` | 10 | 9 | 1 | components/finance/ScheduledReportsManager.js |
| `hr_routes` | 22 | 20 | 2 | components/admin/AttendancePayroll.js, components/admin/EmployeeManagement.js |
| `inquiry_broadcast_routes` | 12 | 11 | 1 | services/bookingService.js, services/settingsService.js |
| `document_master_routes` | 16 | 15 | 1 | components/admin/DocumentTypeMaster.js, components/admin/VerificationAPISettings.js |
| `referral_routes` | 16 | 15 | 1 | services/crmService.js, services/referralService.js |
| `operator_routes` | 18 | 17 | 1 | components/operator/CrewSchedulingBoard.js, components/operator/OperatorFleetAnalytics.js |
| `aviation_exchange_routes` | 31 | 30 | 1 | components/admin/AdminAuctions.js, components/admin/AdminInspections.js |
| `admin_approval_routes` | 7 | 7 | 0 | components/admin/CommandCenter.js, services/adminService.js |
| `admin_audit_routes` | 5 | 5 | 0 | services/adminService.js |
| `admin_booking_management_routes` | 6 | 6 | 0 | services/bookingService.js |
| `admin_landing_permission_routes` | 3 | 3 | 0 | services/adminService.js |
| `admin_operator_management_routes` | 10 | 10 | 0 | services/operatorService.js |
| `admin_user_routes` | 12 | 12 | 0 | services/adminService.js |
| `aircraft_document_routes` | 5 | 5 | 0 | services/fleetService.js |
| `booking_routes` | 6 | 6 | 0 | services/bookingService.js |
| `ceo_routes` | 5 | 5 | 0 | components/admin/CEODashboard.js |
| `chat_routes` | 4 | 4 | 0 | components/pilot/PilotChat.js, services/supportService.js |
| `crm_routes` | 17 | 17 | 0 | components/admin/WebhookIntegration.js, services/crmService.js |
| `customer_routes` | 12 | 12 | 0 | components/customer/CustomerBookingStats.js, components/customer/CustomerPaymentHistory.js |
| `document_routes` | 5 | 5 | 0 | services/fleetService.js |
| `feedback_routes` | 5 | 5 | 0 | services/supportService.js |
| `finance_analytics_routes` | 4 | 4 | 0 | components/finance/FinanceAnalyticsDashboard.js |
| `fleet_routes` | 5 | 5 | 0 | services/fleetService.js |
| `flight_record_routes` | 3 | 3 | 0 | components/operator/OperatorERP.js, services/fleetService.js |
| `fuel_record_routes` | 3 | 3 | 0 | components/operator/OperatorERP.js, services/fleetService.js |
| `hr_employee_routes` | 15 | 15 | 0 | components/admin/AttendancePayroll.js, components/admin/EmployeeManagement.js |
| `journey_routes` | 8 | 8 | 0 | services/bookingService.js |
| `landing_permission_routes` | 4 | 4 | 0 | services/landingService.js |
| `live_tracking_routes` | 4 | 4 | 0 | services/fleetService.js |
| `operator_erp_routes` | 9 | 9 | 0 | components/operator/OperatorERP.js |
| `payment_routes` | 5 | 5 | 0 | services/paymentService.js |
| `pilot_chat_routes` | 5 | 5 | 0 | components/pilot/PilotChat.js, services/supportService.js |
| `pilot_document_routes` | 5 | 5 | 0 | services/fleetService.js |
| `pincode_routes` | 4 | 4 | 0 | services/landingService.js |
| `pricing_engine_routes` | 18 | 18 | 0 | services/settingsService.js |
| `quote_routes` | 2 | 2 | 0 | services/bookingService.js |
| `regional_manager_routes` | 8 | 8 | 0 | services/operatorService.js |
| `reports_routes` | 13 | 13 | 0 | services/analyticsService.js |
| `route_intelligence_routes` | 3 | 3 | 0 | components/analytics/RouteIntelligence.js |
| `scheduler_routes` | 4 | 4 | 0 | components/admin/SchedulerStatus.js |
| `search_routes` | 1 | 1 | 0 | components/shared/GlobalSearch.js |
| `settings_routes` | 26 | 26 | 0 | components/admin/APIKeysSettings.js, components/admin/CallRecordingSettings.js |
| `settlement_automation_routes` | 5 | 5 | 0 | services/adminService.js |
| `tally_routes` | 11 | 11 | 0 | services/integrationsService.js |
| `verification_gst_pan_routes` | 4 | 4 | 0 | components/admin/APIKeysSettings.js, services/authService.js |
| `verification_routes` | 4 | 4 | 0 | services/authService.js |
| `websocket_chat_routes` | 1 | 1 | 0 | components/shared/InAppChat.js |
| `zoho_routes` | 14 | 14 | 0 | services/integrationsService.js |

<details><summary>Back-end endpoints never referenced by the front end, by module</summary>

- **accounting_routes** (10): `GET /api/accounting/providers`, `POST /api/accounting/connect`, `GET /api/accounting/chart-of-accounts`, `POST /api/accounting/export-invoices`, `POST /api/accounting/expense`, `GET /api/accounting/expenses`, `POST /api/accounting/ledger-entry`, `GET /api/accounting/trial-balance`, `GET /api/accounting/profit-loss`, `GET /api/accounting/gst-report`
- **admin_analytics_routes** (4): `GET /api/analytics/admin/export/bookings`, `GET /api/analytics/admin/export/customers`, `GET /api/analytics/admin/export/fleet`, `GET /api/analytics/admin/export/finance`
- **admin_document_routes** (3): `GET /api/admin/document-vault/stats`, `POST /api/admin/document-vault/bulk-verify`, `GET /api/admin/document-vault/operator/{operator_id}`
- **admin_payments_routes** (1): `GET /api/admin/payments/transactions`
- **admin_routes** (3): `POST /api/admin/seed-landing-points`, `POST /api/admin/seed-operators`, `PUT /api/admin/operators/{operator_id}/location`
- **admin_settlement_routes** (4): `POST /api/admin/settlements/automation/run-weekly`, `POST /api/admin/settlements/automation/calculate`, `POST /api/admin/settlements/automation/create-manual`, `GET /api/admin/settlements/automation/pending`
- **ai_advisor_routes** (5): `POST /api/ai-advisor/chat/stream`, `POST /api/ai-advisor/generate-marketing`, `GET /api/ai-advisor/history`, `GET /api/ai-advisor/sessions`, `DELETE /api/ai-advisor/session/{session_id}`
- **ai_pricing_routes** (3): `GET /api/ai-pricing/route-analytics/{origin}/{destination}`, `GET /api/ai-pricing/popular-routes`, `POST /api/ai-pricing/bulk-suggest`
- **ai_reports_routes** (3): `POST /api/ai-reports/generate`, `GET /api/ai-reports/templates`, `GET /api/ai-reports/history`
- **ai_routes** (4): `GET /api/ai/health`, `POST /api/ai/chat`, `GET /api/ai/chat/history/{conversation_id}`, `GET /api/ai/chat/conversations`
- **ai_sales_routes** (5): `GET /api/ai-sales/state-recommendations`, `GET /api/ai-sales/corporate-recommendations`, `GET /api/ai-sales/marketing-campaigns`, `GET /api/ai-sales/competitor-analysis`, `GET /api/ai-sales/sales-forecast`
- **aircraft_catalog_routes** (12): `GET /api/aircraft/booking-types`, `PUT /api/aircraft/{aircraft_id}/documents`, `PUT /api/aircraft/{aircraft_id}/photos`, `POST /api/aircraft/{aircraft_id}/crew`, `PUT /api/aircraft/{aircraft_id}/availability`, `DELETE /api/aircraft/{aircraft_id}/permanent`, `GET /api/aircraft/public/search`, `GET /api/aircraft/public/{aircraft_id}`, `GET /api/aircraft/admin/verification-queue`, `PUT /api/aircraft/admin/{aircraft_id}/verify`, `GET /api/aircraft/admin/stats`, `GET /api/aircraft/admin/expiring-documents`
- **analytics_routes** (1): `GET /api/analytics/booking-purpose`
- **auction_routes** (7): `GET /api/auctions/customer/history`, `GET /api/auctions/{auction_id}`, `POST /api/auctions/{auction_id}/cancel`, `GET /api/auctions/operator/my-quotes`, `GET /api/auctions/admin/all`, `GET /api/auctions/admin/stats`, `POST /api/auctions/system/expire-auctions`
- **auth_routes** (7): `GET /api/auth/lockout-status`, `GET /api/auth/admin/locked-accounts`, `POST /api/auth/admin/unlock-account/{email}`, `POST /api/auth/logout`, `GET /api/auth/login-shield/user-risk-history/{user_id}`, `POST /api/auth/2fa/verify`, `GET /api/auth/check-role-selection`
- **aviation_exchange_routes** (1): `GET /api/exchange/image/{image_id}`
- **boarding_pass_routes** (4): `POST /api/boarding-pass/generate`, `GET /api/boarding-pass/{pass_id}`, `PUT /api/boarding-pass/{pass_id}`, `GET /api/boarding-pass/admin/dashboard`
- **calendar_sync_routes** (10): `GET /api/calendar-sync/providers`, `POST /api/calendar-sync/connect`, `GET /api/calendar-sync/connections`, `DELETE /api/calendar-sync/disconnect/{provider}`, `POST /api/calendar-sync/add-event`, `GET /api/calendar-sync/events`, `GET /api/calendar-sync/download-ics/{booking_id}`, `GET /api/calendar-sync/settings`, `PUT /api/calendar-sync/settings`, `POST /api/calendar-sync/sync-all`
- **chatbot_routes** (3): `GET /api/chatbot/history/{session_id}`, `GET /api/chatbot/faq/{topic}`, `GET /api/chatbot/admin/stats`
- **command_center_routes** (7): `GET /api/command-center/live-flights`, `GET /api/command-center/pending-approvals`, `POST /api/command-center/sos-alert`, `POST /api/command-center/ai-warning`, `GET /api/command-center/system-health`, `GET /api/command-center/activity-feed`, `GET /api/command-center/operator-status`
- **compliance_monitor_routes** (1): `GET /api/compliance/operator/{operator_id}/score`
- **content_routes** (5): `GET /api/content/investor-interests`, `PUT /api/content/investor-interest/{interest_id}`, `DELETE /api/content/testimonials/{testimonial_id}`, `PUT /api/content/fleet/{aircraft_id}`, `DELETE /api/content/fleet/{aircraft_id}`
- **corporate_routes** (8): `POST /api/corporate/account/{corporate_id}/approve`, `PUT /api/corporate/employee/{employee_code}`, `DELETE /api/corporate/employee/{employee_code}`, `POST /api/corporate/budget/department`, `POST /api/corporate/booking/request-approval`, `GET /api/corporate/policy/{corporate_id}`, `PUT /api/corporate/policy/{corporate_id}`, `GET /api/corporate/list`
- **currency_routes** (6): `GET /api/currency/supported`, `POST /api/currency/convert`, `POST /api/currency/display-price`, `GET /api/currency/preference`, `PUT /api/currency/preference`, `POST /api/currency/booking-price/{booking_id}`
- **customer_kyc_routes** (4): `GET /api/customer/kyc-documents/admin/all`, `GET /api/customer/kyc-documents/download/{doc_id}`, `POST /api/customer/kyc-documents/{doc_id}/verify`, `DELETE /api/customer/kyc-documents/admin/{doc_id}`
- **dgca_compliance_routes** (5): `POST /api/dgca/duty-log`, `POST /api/dgca/rest-log`, `GET /api/dgca/pilot/{pilot_id}/can-fly`, `GET /api/dgca/pilot/{pilot_id}/duty-history`, `POST /api/dgca/report`
- **document_master_routes** (1): `GET /api/admin/documents/verification-logs`
- **document_vault_routes** (10): `GET /api/vault/image/{file_id}`, `GET /api/vault/thumbnail/{file_id}`, `GET /api/vault/photos/{owner_id}`, `POST /api/vault/document/{document_id}/new-version`, `POST /api/vault/share`, `GET /api/vault/shared/{share_link}`, `DELETE /api/vault/share/{share_link}`, `POST /api/vault/folder`, `GET /api/vault/expired/{owner_id}`, `POST /api/vault/bulk-action`
- **document_verification_routes** (2): `POST /api/document-verify/submit`, `GET /api/document-verify/entity/{entity_type}/{entity_id}`
- **email_routes** (8): `GET /api/email/templates`, `POST /api/email/test`, `POST /api/email/send`, `POST /api/email/trigger/inquiry/{inquiry_id}`, `POST /api/email/trigger/booking/{booking_id}`, `GET /api/email/status`, `POST /api/email/booking/{booking_id}/send-confirmation`, `GET /api/email/booking/{booking_id}/receipt`
- **emergency_booking_routes** (5): `POST /api/emergency/respond`, `POST /api/emergency/{emergency_id}/select-operator`, `GET /api/emergency/my-requests`, `GET /api/emergency/operator/pending`, `GET /api/emergency/queue`
- **favorites_routes** (2): `PUT /api/favorites/reorder`, `PUT /api/favorites/{favorite_id}`
- **field_tracking_routes** (9): `POST /api/field-tracking/location/update`, `GET /api/field-tracking/location/current`, `GET /api/field-tracking/location/history/{employee_id}`, `POST /api/field-tracking/visits/{visit_id}/check-in`, `POST /api/field-tracking/visits/{visit_id}/check-out`, `POST /api/field-tracking/visits/{visit_id}/photo`, `GET /api/field-tracking/daily-summary/{employee_id}`, `POST /api/field-tracking/geofence`, `GET /api/field-tracking/geofences`
- **finance_advanced_routes** (5): `GET /api/finance/advanced/reconciliation/entries`, `GET /api/finance/advanced/reconciliation/summary`, `POST /api/finance/advanced/vendor-payment/initiate`, `POST /api/finance/advanced/vendor-payment/approve`, `GET /api/finance/advanced/vendor-payment/pending`
- **finance_phase4_routes** (2): `GET /api/finance/phase4/bills/{bill_id}`, `PUT /api/finance/phase4/bills/{bill_id}/tags`
- **finance_phase5_routes** (2): `POST /api/finance/phase5/audit/log`, `GET /api/finance/phase5/invoice/list`
- **finance_reconciliation_routes** (3): `POST /api/finance/reconciliation/auto-match`, `POST /api/finance/reconciliation/manual-match`, `POST /api/finance/reconciliation/dispute`
- **finance_scheduled_routes** (1): `GET /api/finance/scheduled/settlement-sync/data`
- **finance_treasury_routes** (7): `GET /api/finance/bank-accounts/{account_id}`, `PUT /api/finance/bank-accounts/{account_id}`, `DELETE /api/finance/bank-accounts/{account_id}`, `POST /api/finance/cash/entry`, `GET /api/finance/cash/balance`, `GET /api/finance/cash/entries`, `GET /api/finance/summary/monthly`
- **fixed_route_pricing_routes** (10): `POST /api/routes/fixed`, `GET /api/routes/fixed/my-routes`, `PUT /api/routes/fixed/{route_id}`, `DELETE /api/routes/fixed/{route_id}`, `GET /api/routes/search`, `GET /api/routes/fixed/{route_id}`, `GET /api/routes/admin/all`, `POST /api/routes/admin/verify/{route_id}`, `PUT /api/routes/admin/pricing-settings`, `GET /api/routes/admin/pricing-settings`
- **flight_tracking_live_routes** (6): `POST /api/flight-live/start`, `POST /api/flight-live/update`, `GET /api/flight-live/booking/{booking_id}`, `GET /api/flight-live/active`, `GET /api/flight-live/history/{booking_id}`, `WEBSOCKET /api/flight-live/ws/{flight_id}`
- **google_auth_routes** (1): `GET /api/auth/google/callback`
- **gst_routes** (4): `GET /api/gst/config`, `POST /api/gst/config`, `GET /api/gst/returns/{return_id}`, `POST /api/gst/vendors/reconcile-gstr2a`
- **hangar_management_routes** (9): `GET /api/hangar/list`, `POST /api/hangar/create`, `GET /api/hangar/slots`, `POST /api/hangar/slots/book`, `DELETE /api/hangar/slots/{booking_id}`, `GET /api/hangar/inventory`, `POST /api/hangar/inventory/add`, `PUT /api/hangar/inventory/{item_id}/stock`, `GET /api/hangar/occupancy`
- **hr_advanced_routes** (3): `GET /api/hr/targets/my`, `GET /api/hr/salary/bank-details/{employee_id}`, `PUT /api/hr/salary/payment/{payment_id}/complete`
- **hr_routes** (2): `GET /api/hr/incentive-calculation/{employee_id}`, `GET /api/hr/employee-salary/{employee_id}`
- **inquiry_broadcast_routes** (1): `POST /api/inquiry-broadcast/admin/expire-old`
- **insurance_routes** (9): `GET /api/insurance/plans`, `POST /api/insurance/purchase`, `GET /api/insurance/my-policies`, `GET /api/insurance/policy/{policy_id}`, `POST /api/insurance/claims`, `GET /api/insurance/claims/my`, `GET /api/insurance/admin/dashboard`, `GET /api/insurance/admin/claims`, `PUT /api/insurance/admin/claims/{claim_id}`
- **inventory_routes** (4): `POST /api/inventory/slots/bulk-create`, `POST /api/inventory/slots/{slot_id}/book`, `POST /api/inventory/waitlist/add`, `GET /api/inventory/waitlist/{slot_id}`
- **invoice_routes** (4): `GET /api/invoices/{invoice_id}`, `POST /api/invoices/{invoice_id}/payment`, `POST /api/invoices/refund`, `GET /api/invoices/reports/gst`
- **knowledge_routes** (11): `GET /api/knowledge/categories`, `GET /api/knowledge/articles`, `GET /api/knowledge/articles/{article_id}`, `GET /api/knowledge/faqs`, `GET /api/knowledge/videos`, `GET /api/knowledge/search`, `POST /api/knowledge/feedback/{article_id}`, `POST /api/knowledge/admin/articles`, `POST /api/knowledge/admin/faqs`, `POST /api/knowledge/admin/videos`, `GET /api/knowledge/admin/stats`
- **kyc_verification_routes** (8): `POST /api/kyc/verify/aadhaar`, `POST /api/kyc/verify/pan`, `POST /api/kyc/verify/dl`, `POST /api/kyc/verify/passport`, `POST /api/kyc/verify/bank`, `POST /api/kyc/verify/generic`, `POST /api/kyc/auto-verify/{kyc_doc_id}`, `GET /api/kyc/history`
- **landing_infrastructure_routes** (4): `GET /api/landing/documents/{landing_point_id}`, `POST /api/landing/documents`, `PUT /api/landing/documents/{document_id}/verify`, `DELETE /api/landing/documents/{document_id}`
- **legal_routes** (6): `GET /api/legal/terms-and-conditions`, `GET /api/legal/cancellation-policy`, `GET /api/legal/privacy-policy`, `GET /api/legal/consents`, `POST /api/legal/consents/record`, `GET /api/legal/consents/verify/{booking_id}`
- **loyalty_routes** (5): `POST /api/loyalty/redeem`, `POST /api/loyalty/admin/points/adjust`, `POST /api/loyalty/earn/{booking_id}`, `POST /api/loyalty/admin/rewards`, `POST /api/loyalty/admin/vouchers/send-expiry-alerts`
- **maintenance_routes** (3): `PUT /api/maintenance/parts/{part_id}/stock`, `GET /api/maintenance/aircraft/{aircraft_id}/history`, `GET /api/maintenance/pilot-documents/alerts-history`
- **marketing_routes** (3): `GET /api/marketing/campaigns/{campaign_id}`, `POST /api/marketing/promo-codes/validate`, `POST /api/marketing/notifications/{notif_id}/send`
- **membership_routes** (7): `GET /api/membership/tier/{tier}`, `POST /api/membership/cancel/{user_id}`, `POST /api/membership/record-benefit-usage`, `GET /api/membership/calculate-discount`, `GET /api/membership/leaderboard`, `GET /api/membership/statistics`, `GET /api/membership/expiring-soon`
- **multileg_booking_routes** (6): `GET /api/multileg/{booking_id}`, `POST /api/multileg/{booking_id}/group-members`, `POST /api/multileg/quick-round-trip`, `POST /api/multileg/templates`, `GET /api/multileg/templates/my`, `GET /api/multileg/admin/all`
- **notification_center_routes** (3): `POST /api/notifications/create`, `GET /api/notifications/all`, `GET /api/notifications/stats`
- **notification_routes** (4): `GET /api/notifications/my`, `PUT /api/notifications/mark-read/{notification_id}`, `POST /api/notifications/send-email`, `POST /api/notifications/send-whatsapp`
- **operations_map_routes** (2): `GET /api/operations/map/flight/{flight_id}`, `GET /api/operations/map/weather/{location}`
- **operator_routes** (1): `POST /api/operator/aircraft/{registration}/update-maintenance`
- **partner_routes** (4): `GET /api/partner/v1/ping`, `GET /api/partner/v1/aircraft`, `POST /api/partner/v1/bookings`, `GET /api/partner/v1/bookings/{booking_id}`
- **payment_gateway_routes** (14): `POST /api/payments/salary/bulk-transfer`, `POST /api/payments/salary/transfer/{transaction_id}/complete`, `POST /api/payments/salary/transfer/{transaction_id}/reverse`, `POST /api/payments/vendor/bill/bulk-payment`, `POST /api/payments/vendor/payment/{transaction_id}/complete`, `GET /api/payments/tds/summary`, `GET /api/payments/reconciliation/pending`, `GET /api/payments/batches`, `POST /api/payments/gateways/config`, `POST /api/payments/approval/create`, `POST /api/payments/salary/multi-gateway/transfer`, `GET /api/payments/salary/auto-run/{run_id}`, `POST /api/payments/employee/bank-details`, `GET /api/payments/employee/{employee_id}/bank-details`
- **pilot_availability_routes** (3): `POST /api/pilot/availability/bulk-set`, `DELETE /api/pilot/availability/clear/{date}`, `GET /api/pilot/availability/all-pilots`
- **pilot_mobile_routes** (8): `GET /api/pilot/documents`, `GET /api/pilot/flight-logs`, `POST /api/pilot/documents/upload`, `GET /api/pilot/documents/{doc_id}/download`, `GET /api/pilot/preflight/history`, `DELETE /api/pilot/documents/{doc_id}`, `GET /api/pilot/weather/{location}`, `GET /api/pilot/weather/route/{origin}/{destination}`
- **pincode_live_routes** (2): `GET /api/pincode-live/lookup/{pincode}`, `GET /api/pincode-live/search`
- **predictive_analytics_routes** (7): `POST /api/analytics-predict/demand-forecast`, `POST /api/analytics-predict/revenue-forecast`, `GET /api/analytics-predict/churn-risk/{customer_id}`, `GET /api/analytics-predict/churn-risk-batch`, `GET /api/analytics-predict/seasonal-trends`, `GET /api/analytics-predict/route-performance`, `GET /api/analytics-predict/dashboard`
- **predictive_maintenance_routes** (1): `POST /api/maintenance/ai/schedule-recommendation`
- **price_breakup_routes** (3): `GET /api/pricing/lock/{lock_id}/validate`, `GET /api/pricing/admin/settings`, `PUT /api/pricing/admin/settings`
- **pricing_routes** (5): `POST /api/pricing/calculate`, `GET /api/pricing/config`, `POST /api/pricing/config`, `POST /api/pricing/festivals`, `GET /api/pricing/analysis`
- **push_notification_routes** (7): `POST /api/notifications/register-device`, `DELETE /api/notifications/unregister-device/{device_token}`, `GET /api/notifications/my-notifications`, `PUT /api/notifications/mark-read/{notification_id}`, `PUT /api/notifications/mark-all-read`, `GET /api/notifications/admin/dashboard`, `GET /api/notifications/admin/history`
- **razorpay_routes** (8): `POST /api/razorpay/create-order`, `POST /api/razorpay/verify-payment`, `POST /api/razorpay/webhook`, `POST /api/razorpay/refund`, `GET /api/razorpay/order/{order_id}`, `GET /api/razorpay/payment/{payment_id}`, `GET /api/razorpay/orders`, `GET /api/razorpay/stats`
- **referral_routes** (1): `POST /api/referral/wallet/credit`
- **revenue_analytics_routes** (1): `GET /api/analytics/revenue/summary`
- **reviews_routes** (8): `POST /api/reviews/`, `GET /api/reviews/my`, `GET /api/reviews/pending`, `POST /api/reviews/{review_id}/helpful`, `POST /api/reviews/{review_id}/report`, `GET /api/reviews/operator/{operator_id}`, `GET /api/reviews/operator/my/reviews`, `POST /api/reviews/operator/{review_id}/respond`
- **route_optimization_routes** (4): `POST /api/routes/optimize`, `POST /api/routes/multi-stop`, `GET /api/routes/locations`, `GET /api/routes/distance`
- **server** (2): `GET /health`, `GET /api/performance/stats`
- **sos_routes** (9): `POST /api/sos/alert`, `POST /api/sos/alert/{alert_id}/location`, `GET /api/sos/my-alerts`, `POST /api/sos/alert/{alert_id}/cancel`, `GET /api/sos/admin/active`, `GET /api/sos/admin/dashboard`, `GET /api/sos/admin/alert/{alert_id}`, `PUT /api/sos/admin/alert/{alert_id}`, `GET /api/sos/emergency-contacts`
- **stripe_payment_routes** (1): `POST /api/webhook/stripe`
- **support_routes** (2): `POST /api/support/tickets`, `GET /api/support/tickets/my`
- **twilio_routes** (2): `POST /api/twilio/webhook/call-status`, `POST /api/twilio/webhook/recording`
- **two_factor_auth_routes** (5): `POST /api/2fa/setup/totp`, `POST /api/2fa/verify/totp`, `GET /api/2fa/backup-codes`, `POST /api/2fa/regenerate-backup-codes`, `GET /api/2fa/admin/stats`
- **voice_video_routes** (8): `POST /api/voice-video/initiate`, `POST /api/voice-video/respond`, `POST /api/voice-video/end`, `GET /api/voice-video/active`, `GET /api/voice-video/history`, `GET /api/voice-video/stats`, `WEBSOCKET /api/voice-video/ws/{call_id}`, `GET /api/voice-video/admin/dashboard`
- **weather_routes** (3): `GET /api/weather/forecast`, `GET /api/weather/admin/config`, `POST /api/weather/admin/test`

</details>

