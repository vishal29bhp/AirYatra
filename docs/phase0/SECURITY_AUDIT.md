# Security audit (Phase 0, read-only)

Scope: static review of the repository at `HEAD` (back end, front end, repo hygiene, CI). No running system, database, cloud account or git-history rewrite was touched. Severity uses impact × exploitability for an internet-facing deployment: **Critical** = remote compromise of accounts, money or KYC data with little effort; **High** = serious exposure or a control that is missing on a sensitive path; **Medium** = defence-in-depth gap or a risk that needs another weakness; **Low** = hygiene. Secret values are redacted to the first 4 characters + "…". Items marked **ASSUMPTION** need confirmation on a running environment.

Feeds master prompt section S.1 (fix what exists first). Remediation needing history rewrite or key rotation needs owner approval (Constraint 9).

## Summary

| ID | Severity | Finding | Primary evidence |
|---|---|---|---|
| S-01 | Critical | Hard-coded fallback LLM key | `backend/services/ai_service.py:26` |
| S-02 | Critical | Authentication bypass: Emergent Google callbacks trust client-supplied identity and issue a JWT for any existing e-mail (admin included), skipping OTP/TOTP | `backend/routes/auth_routes.py:1610-1760`, `backend/routes/google_auth_routes.py:80-105,466-475,498-610` |
| S-03 | Critical | Credentials committed: SMTP app password, admin/finance/test passwords, seed passwords | `memory/test_credentials.md`, `backend/scripts/seed_demo_users.py:28-36`, `auth_testing.md`, tests |
| S-04 | Critical | Razorpay webhook accepts unsigned events (check skipped when header or secret missing) | `backend/routes/razorpay_routes.py:241-330` |
| S-05 | Critical | Payment verification returns "verified" in mock mode and marks any `booking_id` paid; no ownership/amount binding | `backend/services/payment_service.py:101-158`, `backend/routes/payment_routes.py:104-150` |
| S-06 | High | Stripe webhook verification delegated to `emergentintegrations`; no webhook secret configured | `backend/routes/stripe_payment_routes.py:17-19,601-607` |
| S-07 | High | Unauthenticated, unsigned Twilio and CRM-lead webhooks | `backend/routes/twilio_routes.py:216-253`, `backend/routes/crm_routes.py:171-200` |
| S-08 | Critical | KYC and personal files committed to git | `secure_uploads/kyc/*.enc` (2), `uploads/**` (9) |
| S-09 | High | KYC encryption key falls back to a random per-process key; static salt; algorithm mislabelled | `backend/security_middleware.py:415-450`, `backend/routes/customer_kyc_routes.py:5,20` |
| S-10 | High | MongoDB `w:1` + `journal: False` | `backend/database.py:22-23` |
| S-11 | High | 7-day JWTs stored in `localStorage`, combined with an XSS sink | `backend/config.py:19`, `frontend/src/services/apiClient.js:30`, `frontend/src/pages/BlogPage.js:360` |
| S-12 | High | Public, unauthenticated static mount serves staff selfies, profile photos, expense receipts and landing/village permission documents | `backend/server.py:409-422` |
| S-13 | Medium | CORS default points to an Emergent preview host | `backend/server.py:177-185` |
| S-14 | High | Rate limiting is in-process only, exempts `/api/auth/login` in the global limiter, shares one bucket per proxy IP, and covers only 5 endpoints | `backend/ultra_performance_middleware.py:60-110,152-180`, `backend/security_middleware.py:40-76` |
| S-15 | High | NoSQL mass-assignment (raw `dict` bodies into `$set`) and unescaped `$regex` | 12 sites (table below); 70 of 71 `$regex` uses |
| S-16 | Medium | Upload validation: no content (magic-byte) checks, no size limit in 6 of 13 upload modules, no malware scan | section S-16 |
| S-17 | Medium | Server-side requests to admin/DB-configured URLs (SSRF surface) | `backend/routes/partner_routes.py:45-60,124-135`, `verification_gst_pan_routes.py:168-182` |
| S-18 | High | WebSockets without authentication or authorisation | `backend/routes/websocket_chat_routes.py:65-130`, `flight_tracking_live_routes.py:244-270`, `voice_video_routes.py:250-266` |
| S-19 | Medium | OpenAPI `/docs` enabled; unauthenticated performance stats | `backend/server.py:165-169,443-455` |
| S-20 | Medium | Third-party secrets stored in plain text in MongoDB | `backend/routes/settings_routes.py:393-401`, `twilio_routes.py:103-107`, `zoho_routes.py:17-18` |
| S-21 | Medium | KYC verification endpoints always return mocked success | `backend/routes/kyc_verification_routes.py:4,104,130-188` |
| S-22 | Medium | Missing CSP/HSTS/Referrer-Policy; third-party scripts on every page | `backend/ultra_performance_middleware.py:183-195`, `frontend/public/index.html:36-50,79-143` |
| S-23 | Medium | Exception text returned to clients; `print()` logging | 17 `detail=str(e)` sites; 87 `print(` |
| S-24 | Medium | Google OAuth direct flow without `state`/PKCE | `backend/routes/google_auth_routes.py` |
| S-25 | Low | Dev tooling and plain-HTTP geolocation | `frontend/plugins/visual-edits/dev-server-setup.js:60-110,466-477`, `backend/services/ip_geolocation_service.py:51` |
| S-26 | Low / OK | Password hashing, OTP, token revocation (positive findings, minor gaps) | `backend/auth.py:8`, `backend/services/otp_service.py:30,159`, `backend/middleware.py:71-78` |
| S-27 | Low | Repo/CI hygiene: no secret scanning, `.gitignore` ineffective for tracked files, write-capable template workflow | `.gitignore`, `.github/workflows/deploy.yml` |

## Findings

### S-01 Critical: hard-coded fallback LLM key
- **Evidence:** `backend/services/ai_service.py:26` `EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "sk-e…")`. The same key also authorises Emergent Object Storage (`backend/services/storage_service.py:9,19`), so it grants read/write to stored vault documents as well as LLM spend.
- **Fix:** delete the default (fail closed), rotate the key with Emergent now, purge from history with git-filter-repo (owner approval), move to Key Vault; add gitleaks pre-commit + GitHub push protection.

### S-02 Critical: authentication bypass through the Emergent OAuth callbacks
- **Evidence:**
  - `POST /api/auth/google/emergent-callback` (`backend/routes/auth_routes.py:1610-1760`) reads `request.emergent_user.email` from the request body, finds or creates the user (`:1650-1700`), takes that user's **existing roles** (`:1672`) and returns a JWT plus cookie (`:1706-1745`). There is no server-side call to Emergent to validate `session_token`. Google users have OTP/TOTP disabled (`:1689-1690`; `memory/test_credentials.md` "Google users skip OTP/TOTP verification").
  - A second handler on the same path exists in `backend/routes/google_auth_routes.py:498-610` (shadowed because `auth_routes` is included first, `backend/server.py:208,248`); it has the same trust model.
  - `GET /api/auth/google/callback?token=...` (`google_auth_routes.py:80-105`) accepts `verify_emergent_token()` which only base64-decodes JSON (`:466-475`), no signature.
- **Impact:** anyone can obtain an admin/finance/operator token by POSTing `{"emergent_user":{"email":"<known staff e-mail>"},"session_token":"x"}`. Staff e-mail addresses are in the repo (S-03).
- **Fix (immediate, before any other work if the Emergent deployment is live):** disable both emergent-callback routes and the `token=` branch; implement direct Google OAuth (authorisation code + PKCE + `state` + ID-token verification with `google.oauth2.id_token`, already imported `google_auth_routes.py:7-8`); never accept identity claims from the browser; require MFA for staff roles even with SSO. Add negative tests (Q.2 journey 1 and 9).

### S-03 Critical: credentials committed to the repository
- **Evidence:**
  - `memory/test_credentials.md` (tracked, although listed in `.gitignore`): table of admin, operator, pilot, finance, test-admin (no 2FA), loyalty, employee and emergency test accounts with passwords (`Admi…`, `Oper…`, `Fina…`, `Test…` …); **Gmail SMTP account and its app password** (`ianp…`); a Stripe test key reference (`sk_t…`, also `memory/PRD.md:99`).
  - `backend/scripts/seed_demo_users.py:28-36`: 9 seeded staff/demo accounts with fixed passwords (`Admi…`, `Fina…`, `HR@1…`, `Sale…`, …).
  - Test files with live credentials for the shared environment: `backend_test.py:86,110,203,560,581`, `backend/tests/test_stripe_payments.py:10-12`, `backend/tests/test_account_lockout.py`, `backend/tests/test_hrms*.py`; `auth_testing.md` (session-token recipe against the Emergent host).
- **Fix:** rotate the Gmail app password and every listed account password now; remove the files and purge history (approval); seed users from environment-provided passwords or one-time invites; test credentials from CI secrets; gitleaks + push protection (S.1).

### S-04 Critical: Razorpay webhook signature is optional
- **Evidence:** `backend/routes/razorpay_routes.py:250-260`: `if RAZORPAY_WEBHOOK_SECRET and signature:` verify, otherwise continue. A request **without** `X-Razorpay-Signature` is processed. `payment.captured` then updates `razorpay_orders` and the booking (`:300-322`) and creates notifications. Constant-time compare is used when it does run (`:258`). No replay protection (no event-id idempotency; every event is inserted into `razorpay_webhooks`, `:271-277`).
- **Side bug:** the booking update uses `{"_id": ObjectId(order["booking_id"])}` (`:318-320`) while bookings are keyed by UUID `id`; ASSUMPTION the update raises/never matches, so legitimate webhooks do not mark bookings paid.
- **Fix:** require the header and the secret (fail closed, 400), verify raw body with HMAC-SHA256, de-duplicate on `x-razorpay-event-id`, look bookings up by `id`, contract tests with recorded signed payloads.

### S-05 Critical: payment verification can be forged
- **Evidence:** `backend/services/payment_service.py:148-159` returns `{"verified": True, "mock": True}` whenever the Razorpay client or secret is not configured (env or Mongo `api_keys_settings`, `:22`). `backend/routes/payment_routes.py:104-150` (`POST /api/payments/verify`) then sets `payment_status: "paid"`, `status: "confirmed"` on the inquiry/booking whose `id` the **client** sends in `booking_id`, without checking that the booking belongs to `current_user`, nor that the Razorpay order was created for that booking and amount. When keys are configured the HMAC compare uses `==` (`payment_service.py:123`), not `hmac.compare_digest`.
- **Fix:** never mock in non-dev environments (startup check), bind order → booking → customer → amount server-side (look up `payment_orders` by `order_id` and use its `booking_id`), constant-time compare, idempotency key. Add the price-tampering and IDOR abuse cases from S.2 A04.

### S-06 High: Stripe webhook verification is opaque
- **Evidence:** `backend/routes/stripe_payment_routes.py:601-607` passes body and `Stripe-Signature` (may be `None`) to `emergentintegrations` `StripeCheckout.handle_webhook`; `_get_stripe` builds the client with only `STRIPE_API_KEY` (`:17-19`); there is no `STRIPE_WEBHOOK_SECRET`. ASSUMPTION: the wrapper verifies with a secret managed by Emergent; cannot be confirmed without the package source. `_mark_paid_if_needed` is idempotent by design (comment `:602`).
- **Fix:** official `stripe.Webhook.construct_event` with `STRIPE_WEBHOOK_SECRET` from Key Vault, reject missing signature, tolerance window.

### S-07 High: unsigned inbound webhooks (Twilio, CRM leads); no payout webhooks
- **Evidence:** `POST /api/twilio/webhook/call-status` and `/webhook/recording` (`backend/routes/twilio_routes.py:216-253`) take a JSON `dict`, no `X-Twilio-Signature` check, and write `call_logs.status` / `recording_url` (an attacker can plant a phishing link shown to admins). `POST /api/crm/leads/webhook/{source}` (`backend/routes/crm_routes.py:171-200`) is unauthenticated and creates leads (spam, storage abuse, auto-assignment e-mails). RazorpayX/Cashfree payouts have **no** webhook endpoint (status by polling only), so Q.2 journey 6 cannot be event-driven today.
- **Fix:** Twilio `RequestValidator` on form-encoded body; per-source shared secret or HMAC for lead webhooks + rate limit; add signed payout webhooks (RazorpayX `X-Razorpay-Signature`, Cashfree signature) with idempotency.

### S-08 Critical: KYC and personal files in git
- **Evidence:** `git ls-files` shows `secure_uploads/kyc/AADHAR_…pdf.enc` and `secure_uploads/kyc/OTHER_…pdf.enc` (committed `fc91b26`, 2026-08-02) and 9 files under `uploads/` (`attendance_selfies/` 2, `expense_documents/` 5, `profile_photos/` 2). `.gitignore` has no rule for either directory.
- **Impact:** encrypted Aadhaar files plus the weak key handling in S-09 (and possibly a default/derived key) must be treated as exposed; selfies and receipts are personal data in clear.
- **Fix:** move needed files to Blob, delete, purge history (approval), add ignore rules; assess DPDP Act breach-notification duty for the Aadhaar documents (master prompt S.1).

### S-09 High: KYC encryption key management
- **Evidence:** `backend/security_middleware.py:424-426` `os.environ.get('FILE_ENCRYPTION_KEY', self._generate_key())`: when unset, every process generates a new random key, so files encrypted by one replica/restart cannot be decrypted by the next (data loss) and there is no recoverable key escrow. Non-44-char keys are stretched with PBKDF2 using a **static salt** `b'airyatra_kyc_salt'` (`:440-446`). Fernet is AES-128-CBC + HMAC-SHA256, but `backend/routes/customer_kyc_routes.py:5,99` claims AES-256.
- **Fix:** require the key (fail closed), store in Key Vault, envelope encryption with per-file data keys and key versioning, correct the documentation; test decrypt of existing `.enc` files before any change (no data change rule).

### S-10 High: MongoDB durability disabled
- **Evidence:** `backend/database.py:22-23` `"w": 1` and `"journal": False` ("Skip journal for speed").
- **Impact:** acknowledged writes (payments, refunds, audit logs) can be lost on a crash or failover; single-node acknowledgement allows rollback after election.
- **Fix:** `w="majority"`, `journal=True` (additive, allowed in Phase 2 per master prompt T).

### S-11 High: long-lived tokens in `localStorage` with an XSS sink
- **Evidence:** `ACCESS_TOKEN_EXPIRE_MINUTES` default **10080 (7 days)** (`backend/config.py:19`); cookie max-age 7 days (`backend/routes/auth_routes.py:24`); no refresh-token rotation. Back end sets an `httpOnly` cookie (`auth_routes.py:55-80`) **and** returns the token in the body; the SPA stores it in `localStorage` (`frontend/src/pages/LoginPage.js:202`, `frontend/src/components/auth/GoogleLogin.js:106,277,356`) and sends it as `Authorization: Bearer` (`frontend/src/services/apiClient.js:30-33`; 127 `localStorage.getItem('token')` reads). The axios client does not set `withCredentials`, so the cookie path is unused cross-origin (ASSUMPTION). XSS sink: `frontend/src/pages/BlogPage.js:360` renders `post.content` with `dangerouslySetInnerHTML` and only `\n`/`#` replacements (no DOMPurify anywhere in `frontend/src`). Third-party scripts (S-22) run in the same origin.
- **Fix:** access token ≤ 15 min + rotating refresh token in `HttpOnly; Secure; SameSite` cookie with CSRF token; remove `localStorage` use; sanitise blog HTML (DOMPurify) and add CSP.

### S-12 High: public static file mount for personal documents
- **Evidence:** `backend/server.py:422` `app.mount("/api/uploads", StaticFiles(directory="/app/uploads"))` (no auth). Files written there: attendance selfies (`backend/routes/hr_employee_routes.py:153-162`), profile photos (`:397-405`), expense receipts (`backend/routes/hr_advanced_routes.py:375-389`), landing documents (`backend/routes/landing_infrastructure_routes.py:856-863`) and **village landing-permission documents** (land ownership/NOC, `:1174-1182`). URLs are stored in documents and returned to other roles.
- **Fix:** private Blob containers + short-lived SAS behind an authorised download endpoint; move existing files without changing stored URL values (serve a compatibility route that authorises before redirecting).

### S-13 Medium: CORS default
- **Evidence:** `backend/server.py:177` default `https://aviation-erp-2.preview.emergentagent.com`; `allow_credentials=True` (`:180`). Origins are configurable through `CORS_ORIGINS`, methods/headers are restricted (`:182-183`).
- **Fix:** no default; explicit per-environment allow-list from configuration; startup fails if unset in `prod`.

### S-14 High: rate limiting is not effective at scale
- **Evidence:**
  - Global limiter `FastRateLimitMiddleware` keeps buckets in a process-local dict (`backend/ultra_performance_middleware.py:60-62`), 50 rps / burst 100 per key, **skips `/api/auth/login`** (`:157`), keys on the `Authorization` header or else `request.client.host` (`:160-164`) — behind the ingress/Front Door every anonymous user shares the proxy IP's bucket (ASSUMPTION depends on proxy headers), and limits multiply by replica count.
  - slowapi `Limiter(key_func=get_client_ip)` uses default in-memory storage (`backend/security_middleware.py:76`) and is applied to only 5 endpoints, all in `auth_routes.py` (`:83,160,418,556,762`). `get_client_ip` picks the leftmost non-trusted `X-Forwarded-For` entry (`security_middleware.py:57-63`), which a client can forge by prepending an address.
  - No limits on AI endpoints (LLM cost), search/quote, password reset, signup outside `/register`, KYC upload.
  - Account lockout and login shield are stored in Mongo (`backend/services/account_lockout_service.py`, `login_shield_service.py`), so they already work across replicas (positive).
- **Fix:** Redis-backed limiter (Azure Cache for Redis), rightmost-trusted XFF parsing, per-user + per-IP keys, cover S.3 endpoints, Front Door WAF rate rules.

### S-15 High: NoSQL mass assignment and regex injection
- **Evidence (from `tools/audit/collection_inventory.py` → `suspicious_query_inputs`):** request bodies typed as bare `dict` written straight into `$set`:

| File:line | Collection | Body parameter |
|---|---|---|
| `backend/routes/finance_treasury_routes.py:362` | `bank_accounts` | `updates: dict` |
| `backend/routes/referral_routes.py:534` | `discount_codes` | `updates: dict` |
| `backend/routes/crm_routes.py:452` | `crm_leads` | `update_data: dict` |
| `backend/routes/crm_routes.py:775` | `crm_tasks` | `update_data: dict` |
| `backend/routes/landing_infrastructure_routes.py:370` | `landing_points` | `update_data: dict` |
| `backend/routes/hr_routes.py:127` | `incentive_config` | `config_data: dict` |
| `backend/routes/hr_routes.py:811` | `salary_config` | `config_data: dict` |
| `backend/routes/gst_routes.py:86` | `gst_config` | `data: dict` |
| `backend/routes/invoice_routes.py:380` | `settings` | `settings: dict` |
| `backend/routes/pricing_routes.py:250` | `settings` | `config: dict` |
| `backend/routes/loyalty_routes.py:648` | `rewards_catalog` | `reward: dict` |
| `backend/routes/admin_approval_routes.py:374` | `approval_settings` | `{**data}` |

  Any field (including `id`, ownership, amounts, approval flags, or dotted/`$`-prefixed keys) can be overwritten by whoever can call the route (ASSUMPTION each is admin-only; per-route authZ review in Phase 3). Other `dict` bodies feed inserts (e.g. `crm_routes.py:171` lead webhook). `$regex` with raw user input: 70 of 71 occurrences in `backend/routes` and `backend/services` do not use `re.escape` (e.g. `backend/routes/document_vault_routes.py:259-260`, `backend/routes/operations_map_routes.py:53-54`) → ReDoS and pattern injection. Most other filters are built from typed FastAPI parameters (strings), which limits operator injection.
- **Fix:** Pydantic models with `extra="forbid"` and explicit allowed fields; reject `$`/`.` keys centrally; `re.escape` + length limits for search; regression tests with injection payloads (S.5).

### S-16 Medium: file upload validation
- **Evidence:** `UploadFile` is accepted in 13 route modules. None checks magic bytes. No size limit found in `document_vault_routes.py`, `tally_routes.py`, `document_verification_routes.py`, `pilot_document_routes.py`, `aircraft_catalog_routes.py`, `finance_phase4_routes.py`. Several check only the declared `content_type`/extension (e.g. `customer_kyc_routes.py` allowed MIME list after `:35`, `landing_infrastructure_routes.py`). No malware scanning; files land on local disk or Emergent storage.
- **Fix:** shared upload service (allow-list by content, max size, random names, Defender for Storage scan, private Blob).

### S-17 Medium: SSRF surface
- **Evidence:** partner webhooks POST to any admin-supplied `http(s)` URL (`backend/routes/partner_routes.py:124-135`, sender `:45-60`); GST/PAN verification calls a provider URL read from Mongo (`backend/routes/verification_gst_pan_routes.py:168-182,290-300`); Tally `server_url` configurable (`tally_routes.py:18`).
- **Fix:** egress allow-list (Azure Firewall/NAT), block private ranges and metadata IPs, validate hosts on save.

### S-18 High: WebSocket authentication and authorisation missing
- **Evidence:** `/api/ws/chat/{booking_id}` reads `token` from the query string but never validates it (`backend/routes/websocket_chat_routes.py:78`); identity (`user_id`, `name`, `type`) comes from query parameters (`:79-81`), any client can join any booking room and impersonate any sender. `/api/flight-live/ws/{flight_id}` (`backend/routes/flight_tracking_live_routes.py:244-270`) and `/api/voice-video/ws/{call_id}` (`backend/routes/voice_video_routes.py:250-266`) accept without any check and relay/broadcast. No message size or rate limits. Defect: chat persistence calls `await get_database()` on a sync function (`websocket_chat_routes.py:122,157`), ASSUMPTION messages are never saved.
- **Fix:** authenticate on connect (short-lived ticket, not the bearer token in the URL), authorise per booking/flight/call, validate and size-limit messages, Redis pub/sub backplane for multiple replicas.

### S-19 Medium: API surface exposure
- **Evidence:** `FastAPI(...)` without `docs_url=None`/`openapi_url=None` (`backend/server.py:165-169`) → `/docs`, `/redoc`, `/openapi.json` are served by the app (ASSUMPTION the Emergent ingress only forwards `/api/*`, so they may not be reachable today; on Azure they would be). `/api/performance/stats` is unauthenticated and returns cache/rate-limit internals (`:443-455`); `/health` advertises capacity/config (`:425-441`). `uvicorn.run` has no `reload`/debug (`:493`) — OK.
- **Fix:** disable docs in prod (or protect), authenticate internal stats, minimal health/readiness payloads.

### S-20 Medium: secrets in MongoDB
- **Evidence:** admin "API keys" screen stores keys in `api_keys_settings` in clear (`backend/routes/settings_routes.py:393-401`; masked on read showing first 4 + last 4, `:380`); Twilio `auth_token` in `twilio_config` (`twilio_routes.py:16-17,103-107`); Zoho `client_secret`/`refresh_token` (`zoho_routes.py:17-18`); `verification_apis.api_key/api_secret` (`document_master_routes.py:200`). Services prefer these over env (`payment_service.py:22`, `notification_service.py:22-33`).
- **Fix:** Key Vault references; if DB storage is kept, encrypt with a Key Vault key and restrict to super-admin with audit.

### S-21 Medium: KYC verification is simulated
- **Evidence:** `backend/routes/kyc_verification_routes.py:4` ("simulated responses"), `:130-188` return `verified: True` with random name/DOB/address for Aadhaar (and similar for other documents). Business decisions (operator/pilot onboarding) may rely on it.
- **Fix:** gate behind a sandbox flag that cannot be enabled in prod; integrate a real provider (DEPENDENCY_INVENTORY §2).

### S-22 Medium: browser hardening
- **Evidence:** only `X-Content-Type-Options` and `X-Frame-Options` are set (`backend/ultra_performance_middleware.py:186-195`); no CSP, HSTS, Referrer-Policy, Permissions-Policy anywhere in `backend/`. `frontend/public/index.html:36` loads `https://assets.emergent.sh/scripts/emergent-main.js` on every page; `:41-50` loads `debug-monitor.js` and `cdn.tailwindcss.com` when framed; `:79-143` PostHog with key `phc_…`.
- **Fix:** remove Emergent/PostHog scripts, strict CSP (no `unsafe-inline` scripts), HSTS at Front Door, security headers middleware.

### S-23 Medium: error and log hygiene
- **Evidence:** 17 handlers return exception text to clients (`detail=str(e)` or f-strings), e.g. `backend/routes/scheduler_routes.py:46`, `backend/routes/google_auth_routes.py:300,617`; 87 `print(` calls in routes/services, including payment identifiers (`backend/services/payment_service.py:127,145,149`).
- **Fix:** generic client errors with correlation ID; structured logging with PII masking (S.2 A09).

### S-24 Medium: Google OAuth (direct) lacks `state`/PKCE
- **Evidence:** no `state` or `code_challenge` in `backend/routes/google_auth_routes.py`; code exchange at `:104-105`.
- **Fix:** add `state`, PKCE and nonce; validate ID token audience/issuer.

### S-25 Low: dev tooling and plain HTTP
- **Evidence:** CRA dev server exposes `POST /edit-file` that rewrites source and runs `git commit` (`frontend/plugins/visual-edits/dev-server-setup.js:60-110,466-477`), protected by a supervisor password and enabled whenever `NODE_ENV !== "production"` (`frontend/craco.config.js:7-22`). IP geolocation over plain HTTP (`backend/services/ip_geolocation_service.py:51`).
- **Fix:** delete the plugin; HTTPS geolocation provider.

### S-26 Low / positive: authentication primitives
- Passwords: passlib bcrypt (`backend/auth.py:8,14-16`), default cost 12 (ASSUMPTION passlib default); `passlib==1.7.4` is unmaintained and warns with `bcrypt==4.2.1` (`backend/requirements.txt:17,82`) → plan migration to `bcrypt`/Argon2id with rehash-on-login.
- `JWT_SECRET_KEY` is mandatory (`backend/config.py:9-17`), HS256.
- OTP: `secrets.randbelow`, hashed, `hmac.compare_digest`, expiry (`backend/services/otp_service.py:30,88,142,159`).
- Revocation: tokens hashed into `revoked_tokens` and checked per request (`backend/middleware.py:71-78`); no TTL index, so the collection grows unbounded.
- TOTP secrets stored encrypted (`backend/services/totp_service.py:56,315`).

### S-27 Low: repository and CI hygiene
- `.gitignore` lists `memory/test_credentials.md` and `.env*` but the credentials file is still tracked (ignore rules do not untrack). No ignore rule for `uploads/`, `secure_uploads/`, `test_reports/`.
- No gitleaks/secret-scanning workflow; CodeQL template exists (`.github/workflows/codeql.yml`) but `deploy.yml` (and its duplicate under `main..github/workflows/`) is a `workflow_dispatch` job with `contents: write` that generates Mongoose models and pushes a branch (`.github/workflows/deploy.yml:1-30,819-823`), unrelated to this app (see CODE_MAP §4).
- **Fix:** S.1 controls (gitleaks pre-commit, push protection, branch protection), delete template workflows.

## Not covered / follow-up
- Full per-route authorisation (IDOR) review of 1,241 endpoints (see `docs/phase0/route_map.json`) — sampled only (S-05, S-15). Needs the Phase 3 `AuthorizationPolicy` work and negative tests per role (Q.2 item 9).
- Dependency CVE scan (`pip-audit`, `npm audit`) was not run (no network/package install for the app); schedule in CI.
- Git history was not searched for secrets beyond the current tree; run gitleaks on full history before the purge decision.
