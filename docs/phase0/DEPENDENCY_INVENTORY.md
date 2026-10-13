# External dependency inventory (Phase 0)

Derived from the code at the current `HEAD` (no runtime access). File references are `path:line` from the repository root. Secret values are never reproduced; where a literal key exists it is shown as its first 4 characters + "…". The **Azure decision** column is a placeholder for Phase 1 (default from master prompt section T in brackets).

## 1. Emergent platform dependencies

### 1.1 Back end

| # | Dependency | Evidence (file:line) | What breaks without it | Azure decision (placeholder) |
|---|---|---|---|---|
| E1 | `emergentintegrations==0.2.0` Python package (private Emergent index) | `backend/requirements.txt:31` | `pip install` fails outside Emergent unless the package is removed or vendored | Remove; replace with adapters [Azure OpenAI + Stripe SDK] |
| E2 | `emergentintegrations.llm.chat.LlmChat` (LLM chat, streaming) | `backend/services/ai_service.py:11-24` (try/except, falls back to mocks), `backend/ai_service.py:9` (duplicate service, mock fallback), `backend/routes/ai_routes.py:203` (streaming chatbot, comment says "OpenAI GPT-5.4 via Emergent", `:199`), `backend/routes/ai_advisor_routes.py:19` (**top-level import: module fails to import, and therefore `server.py` fails to start, if the package is absent**), `backend/routes/finance_phase4_routes.py:225,279` | AI price suggestion, document AI check, chatbot, AI advisors, finance AI queries | Azure OpenAI behind `AIService` interface [default] |
| E3 | `emergentintegrations.payments.stripe.checkout.StripeCheckout` | `backend/routes/stripe_payment_routes.py:12` (top-level import), `:17-19` (`StripeCheckout(api_key=os.environ["STRIPE_API_KEY"], webhook_url=...)`), webhook `:601-607` | Stripe checkout, status polling, webhook | Official `stripe` SDK (already pinned, `backend/requirements.txt:129`, used in `backend/scheduler.py:1229`) — Keep Stripe? **decision needed** |
| E4 | `EMERGENT_LLM_KEY` env var | `backend/config.py:28`, `backend/services/ai_service.py:26`, `backend/services/storage_service.py:9`, `backend/routes/ai_routes.py:239`, `backend/routes/ai_advisor_routes.py:26`, `backend/routes/finance_phase4_routes.py:229,283` | All of E2 and E5 | Delete; Key Vault secret for Azure OpenAI (or managed identity) |
| E5 | **Hard-coded fallback LLM key** `sk-e…` | `backend/services/ai_service.py:26` | n/a (security: see SECURITY_AUDIT S-01) | Remove + rotate |
| E6 | **Emergent Object Storage** REST API `https://integrations.emergentagent.com/objstore/api/v1/storage` (init with `EMERGENT_LLM_KEY`, then `PUT/GET /objects/{path}` with `X-Storage-Key`) using blocking `requests` | `backend/services/storage_service.py:8-40`; caller `backend/routes/document_vault_routes.py:97` (vault uploads, thumbnails); known defect in `test_reports/iteration_25.json:7,41,55` | Document vault file storage | Azure Blob (private container + SAS) behind one storage interface [default] |
| E7 | **Emergent-managed Google OAuth** (backend side): `EMERGENT_GOOGLE_AUTH_URL = https://auth.emergentagent.com/google`, `EMERGENT_CALLBACK_URL`, `verify_emergent_token()` (base64-decodes, no signature), `POST /auth/google/emergent-callback` (two implementations), `use_emergent_auth` setting default `True` | `backend/routes/google_auth_routes.py:27-28,38,42,57-61,102,466-475,489-495,498-610`; `backend/routes/auth_routes.py:1601-1770,1814,1890` | Google sign-in | Direct Google OAuth (code + PKCE + state) — direct path already exists (`google_auth_routes.py:22-24,104-105`, `GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI`) [default] |
| E8 | `EMERGENT_CALLBACK_URL` env var | `backend/routes/google_auth_routes.py:28` | Emergent OAuth redirect | Delete |
| E9 | Stored Emergent artefacts in data: `users.auth_provider = "google_emergent"` / `"emergent_google"`, `users.emergent_session_token` | `backend/routes/auth_routes.py:1666,1685,1721-1722`, `backend/routes/google_auth_routes.py:530,563,568`; read at `auth_routes.py:1814,1890` | Behaviour branches on these values (role selection, password set-up) | **Keep values unchanged** (no data change rule); new adapter must treat both strings as "Google" |
| E10 | `*.emergentagent.com` default URLs | CORS default `https://aviation-erp-2.preview.emergentagent.com` `backend/server.py:177`; `FRONTEND_URL` default same host `backend/services/email_service.py:1762` | Wrong CORS / links in emails if env vars unset | Config/Key Vault, explicit allow-list |
| E11 | Emergent CDN images (`static.prod-images.emergentagent.com/jobs/<job-id>/images/...`) | `backend/routes/aviation_exchange_routes.py:12-15` (4 constants used as listing photos) | Broken images when Emergent deletes the job | Copy to Blob/CDN; ASSUMPTION same URLs may also be stored in `exchange_listings` documents (seeded via `insert_many`) — data stays as is, add redirect or keep URLs |
| E12 | Live tests and scripts targeting the Emergent preview host | `backend_test.py:7`, `pricing_engine_specific_tests.py:10`, `test_result.md:406`, `auth_testing.md:38-57` | Tests point at Emergent | Parameterise `BASE_URL` |
| E13 | Emergent "Object Storage" assertions in tests | `backend/tests/test_vault_object_storage.py:94,101` | Test semantics | Rewrite as contract test for Blob adapter |

### 1.2 Front end

| # | Dependency | Evidence | Azure decision (placeholder) |
|---|---|---|---|
| F1 | Emergent auth redirect `https://auth.emergentagent.com/?redirect=...` | `frontend/src/components/auth/GoogleLogin.js:254-256` | Replace with Google Identity Services / backend `/auth/google/login` |
| F2 | Session exchange `https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data` then `POST ${backendUrl}/api/auth/google/emergent-callback` | `frontend/src/components/auth/GoogleLogin.js:40-106` (`EmergentAuthCallback`), routed at `frontend/src/App.js:61,115` | Remove with E7 |
| F3 | `use_emergent_auth` default `true` in UI state | `frontend/src/components/auth/GoogleLogin.js:220,233` | Remove |
| F4 | Emergent scripts in the page shell: `https://assets.emergent.sh/scripts/emergent-main.js` (always), `debug-monitor.js` + `cdn.tailwindcss.com` (when framed) | `frontend/public/index.html:36,37-50` | Remove (third-party script on every page) |
| F5 | PostHog analytics initialised with a project key `phc_…` (Emergent's project, ASSUMPTION) to `https://us.i.posthog.com` | `frontend/public/index.html:79-143` | Remove or replace with Application Insights (US data transfer + DPDP) |
| F6 | `frontend/plugins/visual-edits/*` (Babel metadata plugin + dev-server `/edit-file` endpoint that writes source files and runs `git commit` as `support@emergent.sh`; CORS allows `*.emergent.sh` and `*.emergentagent.com`) | `frontend/plugins/visual-edits/dev-server-setup.js:41-47,60-110,466-477`; enabled for every non-production CRA run `frontend/craco.config.js:7-22,74-79` | Delete plugin and CRACO hooks |
| F7 | `frontend/plugins/health-check/*` (webpack health plugin, opt-in `ENABLE_HEALTH_CHECK`) | `frontend/craco.config.js:11,26-33`, `frontend/plugins/health-check/health-endpoints.js`, `webpack-health-plugin.js` | Delete (container health checks replace it) |

### 1.3 Repository / platform files

| Path | Content | Decision |
|---|---|---|
| `.emergent/emergent.yml` | Emergent job id and base image `fastapi_react_mongo_shadcn_base_image_cloud_arm` | Delete |
| `.emergent/cron/*` | Pod-local cron that polls `https://ea.int.apis.emergentagent.com` (`.emergent/cron/webhook-crons:6,8`) and dispatches webhooks (`dispatch_webhook.sh`, reads a `WEBHOOK_CRON_SECRET` at `:50`) | Delete; scheduling moves to the worker (CODE_MAP §5) |
| `.emergent/markers/*`, `summary.txt`, `system_deps.txt` | Bootstrap/restore markers; `cron` system package | Delete |
| `.gitconfig` | Commit identity `emergent-agent-e1` / `github@emergent.sh` (`.gitconfig:2-3`) | Delete from repo |
| `memory/*.md`, `test_result.md`, `test_reports/*`, `auth_testing.md` | Emergent agent working notes, include credentials (SECURITY_AUDIT S-03) | Move out of repo / purge |
| Hard-coded container paths `/app/uploads`, `/app/secure_uploads`, `/app/backend/.env` | `backend/server.py:409-422`, `backend/routes/customer_kyc_routes.py:32`, `backend/routes/hr_employee_routes.py:153,397`, `backend/routes/hr_advanced_routes.py:375`, `backend/routes/landing_infrastructure_routes.py:856,1174`; tests read `/app/frontend/.env` | Replace with Blob adapter; config paths |

## 2. Third-party integrations

| Integration | Purpose | Code (file:line) | Env vars / config | Notes and risks | Azure decision (placeholder) |
|---|---|---|---|---|---|
| **Razorpay** (payments) | Orders, checkout verify, refunds, webhook, settlement sync | `backend/services/payment_service.py:11-33,101-158`, `backend/routes/payment_routes.py:64-92,104-150`, `backend/routes/razorpay_routes.py:13,21-28,78-127,149-235,241-330,446`, `backend/routes/customer_routes.py:197`, `backend/scheduler.py:1329-1409`; front end `window.Razorpay` in `frontend/src/components/customer/PaymentCheckout.js:119` | `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `RAZORPAY_RECEIPT_PREFIX`, `RAZORPAY_WEBSITE`; also overridable from Mongo `api_keys_settings` (`payment_service.py:22`) | Two parallel Razorpay stacks (`/api/payments/*` and `/api/razorpay/*`); mock verification when keys missing (S-05); webhook signature optional (S-04). ASSUMPTION: checkout.js is not loaded anywhere in `frontend/` (no `checkout.razorpay.com` reference) | Keep Razorpay; secrets in Key Vault |
| **RazorpayX** (payouts) | Operator/vendor payouts | `backend/services/payment_gateway_service.py:75-257` (`https://api.razorpay.com/v1`) | `RAZORPAYX_KEY_ID`, `RAZORPAYX_KEY_SECRET`, `RAZORPAYX_ACCOUNT_NUMBER` (`:79-81`) | No payout webhook route exists | Keep; Key Vault |
| **Cashfree** (payouts) | Alternative payout gateway | `backend/services/payment_gateway_service.py:259-...` (`payout-api.cashfree.com`, sandbox `payout-gamma.cashfree.com`) | `CASHFREE_CLIENT_ID`, `CASHFREE_CLIENT_SECRET`, `CASHFREE_SANDBOX` (`:263-265`) | No Cashfree webhook route exists (master prompt Q.2 item 2 lists Cashfree payments: only payouts are implemented) | Keep or drop — **decision** |
| **Stripe** | Card checkout (via Emergent wrapper), settlement sync (official SDK) | `backend/routes/stripe_payment_routes.py:12-19,601-607`, `backend/scheduler.py:1208-1328` (`import stripe` `:1229`) | `STRIPE_API_KEY` (`stripe_payment_routes.py:19`, `scheduler.py:1222`); no webhook-secret variable | Webhook verification delegated to `emergentintegrations` (ASSUMPTION, S-06) | Keep or drop — **decision**; official SDK + `STRIPE_WEBHOOK_SECRET` |
| **Twilio** | SMS/WhatsApp notifications, call recording, voice | `backend/services/notification_service.py:10-33,112,162`, `backend/routes/twilio_routes.py:12-256` | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, `TWILIO_WHATSAPP_NUMBER`; also Mongo `api_keys_settings` and `twilio_config` (stores `auth_token`, `twilio_routes.py:16-17,103-107`) | **`twilio` package is not in `backend/requirements.txt`**, so the lazy import fails and SMS silently no-ops (ASSUMPTION). Webhooks unsigned (S-07) | Keep Twilio or Azure Communication Services — **decision** |
| **SendGrid** | Email (legacy path) | `backend/email_service.py:1-10` (used by `booking_routes`, `quote_routes`, `maintenance_routes`), `backend/services/notification_service.py:9,63-64` | `SENDGRID_API_KEY`, `SENDER_EMAIL` (`backend/config.py:26-27`) | Two email stacks | Pick one — **decision** (ACS Email or keep) |
| **SMTP (Gmail by default)** | Main transactional email (14 importers) | `backend/services/email_service.py:17,25-30,1408` | `SMTP_HOST` (default `smtp.gmail.com`), `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME` | A Gmail app password for the sending account is committed in `memory/test_credentials.md` (S-03) | ACS Email or keep SMTP via Key Vault — **decision** |
| **Google OAuth (direct)** | Sign-in (code flow) + People API (birthday/phone) | `backend/routes/google_auth_routes.py:7-9,22-24,104-105` (+ `accounts.google.com`, `oauth2.googleapis.com/token`, `people.googleapis.com`, `www.googleapis.com/oauth2/v3/userinfo`) | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`; settings doc `settings{type:"google_auth"}` | No `state` or PKCE parameter anywhere in the file (grep for `state`/`code_challenge` finds nothing) | Keep (replaces E7) |
| **OpenWeatherMap** | Weather for routes | `backend/routes/weather_routes.py:14`, `backend/services/weather_service.py:11` | **Two names:** `OPENWEATHER_API_KEY` and `OPENWEATHERMAP_API_KEY` | Inconsistent variable names | Keep; one name |
| **AWS S3 (boto3)** | Pre-signed upload/download for aircraft, pilot, landing documents | `backend/s3_service.py:1-76`; used by `routes/aircraft_document_routes.py:31-145`, `pilot_document_routes.py`, `landing_permission_routes.py`, `landing_infrastructure_routes.py`, `document_routes.py` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` (default `ap-south-1`), `S3_BUCKET_NAME` (default `airyatra-documents`) (`backend/config.py:20-23`) | Third storage backend alongside local disk and Emergent | Azure Blob [default] |
| **Local disk** | KYC (encrypted), selfies, expense docs, profile photos, landing/village documents | `backend/server.py:409-422` (public mount `/api/uploads`), `backend/routes/customer_kyc_routes.py:32-33`, `hr_employee_routes.py:153,397`, `hr_advanced_routes.py:375`, `landing_infrastructure_routes.py:856,1174` | `FILE_ENCRYPTION_KEY` (`backend/security_middleware.py:424-426`) | Not shared across replicas | Azure Blob [default] |
| **Redis** | Intended L2 cache | `backend/high_performance_cache.py:22,98` | `REDIS_URL` | **Not used at runtime**: `high_performance_cache.py` is imported by nothing; rate limits/caches are in-process dicts (`ultra_performance_middleware.py:19,60`) and slowapi default memory storage (`security_middleware.py:76`) | Azure Cache for Redis [default] |
| **MongoDB** | Primary DB (Motor) | `backend/database.py`, `backend/config.py:14-15` | `MONGO_URL`, `DB_NAME` (default `airyatra_db`); `db_optimization.py:127-129` hard-codes DB `airyatra` | `w:1`, `journal:False` (S-10) | Atlas on Azure / Cosmos vCore — Phase 1 |
| **Tally Prime** | Accounting export (XML/vouchers queue) | `backend/routes/tally_routes.py:18` (`server_url` default `http://localhost:9000`), config in Mongo `tally_config` | none (DB config) | No outbound HTTP found; ASSUMPTION export-only | Keep — **decision** |
| **Zoho Books** | Accounting sync | `backend/routes/zoho_routes.py:17-18,59,82-90` (OAuth URL `accounts.zoho.com`) | none (DB `zoho_config` stores `client_secret`, `refresh_token`) | Secrets stored in Mongo; ASSUMPTION sync partly mocked (no `zohoapis` calls found) | Keep — **decision** |
| **IP geolocation** (`ip-api.com`, free tier, **plain HTTP**) | Login shield / device info | `backend/services/ip_geolocation_service.py:4,51` | none | HTTP (no TLS), free tier is non-commercial and 45 req/min | Replace with paid HTTPS provider or Front Door geo headers — **decision** |
| **Surepass** KYC APIs (Aadhaar, PAN, GST, DL, passport, bank, company) | Document verification config | `backend/routes/document_master_routes.py` (URLs `api.surepass.io/...`, keys in `verification_apis` collection `:200,220`) | DB-stored keys | KYC routes actually return **mock** results (`backend/routes/kyc_verification_routes.py:4,104,130-188`) | Decide provider before go-live |
| **GST/PAN verification** (configurable provider) | GSTIN/PAN checks | `backend/routes/verification_gst_pan_routes.py:168-182,290-300` | Mongo `api_keys_settings` | | Keep — **decision** |
| **India Post pincode API**, **data.gov.in** | Pincode lookup | `backend/routes/pincode_routes.py` / `backend/routes/pincode_live_routes.py:36` (`api.postalpincode.in`, `api.data.gov.in/resource/...`) | none (ASSUMPTION a data.gov.in `api-key` is supplied at call time; none found in code) | | Keep |
| **exchangerate-api.com** | Forex rates | `backend/routes/finance_phase5_routes.py:638` | none | `currency_routes.py:11` uses static rates | Keep |
| **DGCA verify** (`dgca.gov.in/api/verify`) | Pilot/aircraft check | `backend/routes/document_master_routes.py:530` | none | ASSUMPTION placeholder URL | Confirm |
| **Partner webhooks** (outbound, HMAC-signed with partner API key) | Notify B2B partners | `backend/routes/partner_routes.py:45-60,124-135` | per-partner `webhook_url`, `api_key` | Admin-set arbitrary URLs → SSRF surface (S-17) | Keep; egress allow-list |
| **WhatsApp deep links** (`wa.me`) | Share links | `backend/routes/admin_payments_routes.py:702` | none | | Keep |
| **Push notifications** | Stub ("integrate with FCM/APNs") | `backend/routes/push_notification_routes.py:39-50` | none | Not implemented | Decide (ACS / Notification Hubs / FCM) |
| **PostHog** | Product analytics (front end) | `frontend/public/index.html:79-143` | hard-coded project key | See F5 | Remove or replace |
| **OpenStreetMap tiles** | Maps (react-leaflet) | `frontend/src/components/operator/LiveTrackingMap.js:221`, `frontend/src/components/booking/MultiCityRouteMap.js:184` | none | OSM tile usage policy forbids heavy commercial use | Azure Maps or paid tiles — **decision** |
| **Google Fonts**, **cdnjs**, **Unsplash** images | Fonts, assets | `frontend/public/index.html`, various components (11 Unsplash URLs) | none | | Self-host / Blob CDN |
| Exotel, Zapier, Make, RapidAPI | Mentioned in UI copy/config screens only | `frontend/src` (links) | n/a | ASSUMPTION not integrated server side | n/a |

## 3. Complete environment-variable list (back end)

| Variable | Read at | Integration |
|---|---|---|
| `MONGO_URL`, `DB_NAME` | `backend/config.py:14-15` (+ `db_optimization.py:127`, `optimized_mongo.py:53-54`, `connection_pool.py:40-41`, `scripts/seed_*.py`) | MongoDB |
| `JWT_SECRET_KEY` (required), `JWT_ALGORITHM` (HS256), `ACCESS_TOKEN_EXPIRE_MINUTES` (default 10080) | `backend/config.py:17-19` | Auth |
| `COOKIE_SECURE`, `COOKIE_SAMESITE` | `backend/routes/auth_routes.py:22-23` | Auth cookie |
| `CORS_ORIGINS` | `backend/server.py:177` | CORS |
| `FRONTEND_URL` | `backend/services/email_service.py:1762`, `backend/routes/google_auth_routes.py:183,190` | Links |
| `FILE_ENCRYPTION_KEY` | `backend/security_middleware.py:424-426` (multi-line `os.environ.get`) | KYC encryption |
| `EMERGENT_LLM_KEY`, `EMERGENT_CALLBACK_URL` | see E4, E8 | Emergent |
| `RAZORPAY_*`, `RAZORPAYX_*`, `CASHFREE_*`, `STRIPE_API_KEY` | see section 2 | Payments |
| `TWILIO_*`, `SENDGRID_API_KEY`, `SENDER_EMAIL`, `SMTP_*` | see section 2 | Messaging |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | `backend/routes/google_auth_routes.py:22-24` | Google |
| `OPENWEATHER_API_KEY`, `OPENWEATHERMAP_API_KEY` | `weather_routes.py:14`, `services/weather_service.py:11` | Weather |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET_NAME` | `backend/config.py:20-23` | S3 |
| `REDIS_URL` | `backend/high_performance_cache.py:98` (dead module) | Redis |
| Front end: `REACT_APP_BACKEND_URL` (75 uses), `ENABLE_HEALTH_CHECK`, `NODE_ENV` | `frontend/src/**`, `frontend/craco.config.js` | |

Secrets that live **in MongoDB** rather than env (must be migrated to Key Vault or at least encrypted, Phase 1 decision): `api_keys_settings` (Razorpay, Twilio, GST/PAN API keys; `backend/routes/settings_routes.py:393-401`), `twilio_config`, `zoho_config`, `tally_config`, `verification_apis` (`document_master_routes.py:200`), `partners.api_key`.
