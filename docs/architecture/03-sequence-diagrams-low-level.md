# Low-Level Sequence Diagrams

Code-level flows inside the AirYatra API on Azure. Participants are classes and modules. Where the code
does not yet have the class named here, the participant is the **target class from Section E** (Router → Service →
Repository / Adapter) and the note under the diagram names today's file and line, so Phase 3 refactors have a map.
Every diagram keeps the API path, request and response unchanged (Constraint 4) and the stored document shape
unchanged (Constraint 1).

`[gap]` marks a behaviour that differs from today and is fixed in Phase 3 under Section S; the Phase 0
[security audit](../phase0/SECURITY_AUDIT.md) has the evidence.

| # | Flow | Q.2 journey |
|---|---|---|
| L1 | [Password login: lockout, Login Shield, OTP/TOTP, tokens](#l1-password-login) | 1 |
| L2 | [Google sign-in without Emergent](#l2-google-sign-in-without-emergent) | 1 |
| L3 | [Create booking and broadcast inquiry](#l3-create-booking-and-broadcast-inquiry) | 2, 3 |
| L4 | [Operator quote and customer acceptance](#l4-operator-quote-and-customer-acceptance) | 3 |
| L5 | [Razorpay order, verification and webhook](#l5-razorpay-order-verification-and-webhook) | 2 |
| L6 | [Cancellation and refund](#l6-cancellation-and-refund) | 4 |
| L7 | [KYC upload and download](#l7-kyc-upload-and-download) | 5 |
| L8 | [Operator settlement and RazorpayX payout](#l8-operator-settlement-and-razorpayx-payout) | 6 |
| L9 | [Village landing permission, multi-level approval](#l9-village-landing-permission) | 7 |
| L10 | [SOS alert](#l10-sos-alert) | 8 |
| L11 | [Authorisation on every request](#l11-authorisation-on-every-request) | 9 |
| L12 | [Scheduler job in the worker](#l12-scheduler-job-in-the-worker) | 10 |
| L13 | [WebSocket chat across replicas](#l13-websocket-chat-across-replicas) | — |
| L14 | [AI chatbot through Azure OpenAI](#l14-ai-chatbot-through-azure-openai) | — |
| L15 | [Container start-up and health](#l15-container-start-up-and-health) | — |

---

## L1. Password login

```mermaid
sequenceDiagram
    autonumber
    actor U as Browser
    participant RT as auth_routes.login
    participant LIM as RateLimiter (Redis)
    participant LO as AccountLockoutService
    participant UR as UserRepository
    participant PW as PasswordHasher (bcrypt)
    participant LS as LoginShieldService
    participant OTP as OtpService / TotpService
    participant TS as TokenService
    participant AUD as AuditLogger
    participant MAIL as EmailGateway

    U->>RT: POST /api/auth/login {email, password}
    RT->>LIM: hit(ip, email) for "login"
    alt over limit
        LIM-->>RT: blocked
        RT-->>U: 429
    end
    RT->>LO: check_lockout_status(email)
    alt locked
        LO-->>RT: locked, remaining_seconds
        RT-->>U: 423 account_locked
    end
    RT->>UR: find_by_email(email) projection without _id
    RT->>PW: verify(password, user.password_hash)
    alt wrong email or password
        RT->>LO: record_failed_attempt(email, ip)
        opt reached 5 failures
            LO-->>RT: locked + unlock_token
            RT-)MAIL: send_account_locked_email
        end
        RT->>AUD: LOGIN_FAILED (risk medium)
        RT-->>U: 401 generic message
    end
    RT->>LS: calculate_risk_score(user, ip, user_agent)
    alt block_login
        RT-)MAIL: new device alert
        RT-->>U: 403
    end
    alt user.totp_enabled
        RT->>TS: temp token (5 min, scope "2fa")
        RT-->>U: 200 {totp_required, temp_token}
        U->>RT: POST /api/auth/login/verify-totp {temp_token, code}
        RT->>OTP: verify TOTP (constant-time, window 1, replay guard)
    else OTP required (policy or risk)
        RT->>OTP: create_otp(user, device) single-use, 5 min expiry
        RT-)MAIL: send_otp_email
        RT-->>U: 200 {otp_required, otp_sent}
        U->>RT: POST /api/auth/login/verify-otp {email, otp}
        RT->>OTP: verify (rate-limited, constant-time)
    end
    RT->>LO: reset(email)
    RT->>TS: issue access token (15 min) + refresh token (rotating)
    TS->>UR: store hashed session, device fingerprint
    RT->>AUD: LOGIN_SUCCESS
    RT-->>U: 200 Token {access_token, user} + Set-Cookie (HttpOnly, Secure, SameSite=Strict)
```

Today: `backend/routes/auth_routes.py:159` (login), `:417` (verify-otp), `:555` (verify-totp); token from
`backend/auth.py:18`. `[gap]` Access token lifetime defaults to 7 days (`ACCESS_TOKEN_EXPIRE_MINUTES=10080`,
`backend/config.py`); target 15 minutes plus a refresh token. `[gap]` The body still returns `access_token` so
existing clients keep working; the cookie is added alongside and the front end moves to it in Phase 3.
`[gap]` Lockout counters move from MongoDB/in-memory to Redis so every replica sees the same count.

## L2. Google sign-in without Emergent

```mermaid
sequenceDiagram
    autonumber
    actor U as Browser
    participant FE as React GoogleLogin
    participant RT as google_auth_routes
    participant OA as GoogleOAuthProvider (adapter)
    participant R as Redis
    participant G as accounts.google.com
    participant UR as UserRepository
    participant TS as TokenService

    U->>FE: click Continue with Google
    FE->>RT: GET /api/auth/google/login
    RT->>OA: build_authorization_url()
    OA->>OA: state, nonce, PKCE verifier + S256 challenge
    OA->>R: SET oauth:{state} {verifier, nonce} EX 600
    RT-->>U: 302 to Google (client_id, redirect_uri, scope openid email profile, state, nonce, code_challenge)
    U->>G: consent
    G-->>U: 302 /api/auth/google/callback?code&state
    U->>RT: GET callback
    RT->>OA: exchange(code, state)
    OA->>R: GETDEL oauth:{state}
    alt missing or mismatched state
        RT-->>U: 400
    end
    OA->>G: POST token endpoint (code, code_verifier, client_secret from Key Vault)
    G-->>OA: id_token, access_token
    OA->>OA: verify id_token signature (Google JWKS), aud, iss, exp, nonce, email_verified
    RT->>UR: find_by_email or create user (same fields as today)
    RT->>TS: issue tokens
    RT-->>U: 302 to app with session cookie
```

Today: `backend/routes/google_auth_routes.py:46` (`/login`), `:80` (`/callback`) and the Emergent path
`/google/emergent-callback` (`google_auth_routes.py:498`, `auth_routes.py:1610`). The Emergent routes stay
mounted and return the same shape during the transition, then are retired once no client calls them.

## L3. Create booking and broadcast inquiry

```mermaid
sequenceDiagram
    autonumber
    actor C as Customer
    participant RT as booking_routes.create_booking
    participant AZ as AuthorizationPolicy
    participant BS as BookingService
    participant PE as PricingEngine
    participant LLM as LlmProvider (AzureOpenAiProvider)
    participant BR as BookingRepository
    participant IBS as InquiryBroadcastService
    participant OR as OperatorRepository
    participant N as NotificationService
    participant BG as BackgroundTasks

    C->>RT: POST /api/bookings/ {from, to, date, pax, ...}
    RT->>AZ: require role customer|corporate (deny by default)
    RT->>BS: create(customer_id from token, payload)
    BS->>BS: validate payload (Pydantic, extra fields rejected, no $-keys)
    BS->>PE: estimate(route, pax, aircraft class)
    PE-->>BS: server-side estimate (client estimated_price ignored for money)
    BS->>LLM: price suggestion (no PII in prompt)
    LLM-->>BS: suggestion or timeout (non-blocking)
    BS->>BR: insert booking {id uuid, booking_number, status pending_quotes, created_at ISO string}
    BS->>BG: add_task(broadcast)
    RT-->>C: 200 {message, booking, broadcast: initiated}
    BG->>IBS: create_inquiry_broadcast(booking, lat, lon)
    IBS->>OR: active operators + aircraft
    IBS->>IBS: haversine distance <= radius (settings, default 500 km)
    loop each operator in radius
        IBS->>IBS: insert inquiry_operator_mappings (pending, expires_at)
        IBS->>N: in-app + email + WhatsApp (Twilio)
    end
    IBS->>IBS: update inquiry_broadcasts totals
```

Today: `backend/routes/booking_routes.py:15` takes `booking_data: dict` and stores
`estimated_price` from the client; `backend/services/inquiry_broadcast_service.py:148`.
`[gap]` A typed request model replaces `dict` with the **same field names** so stored documents do not change.
Booking `created_at` stays an ISO string (today's format, see the Phase 0 data dictionary).

## L4. Operator quote and customer acceptance

```mermaid
sequenceDiagram
    autonumber
    actor OP as Operator
    actor C as Customer
    participant RT as inquiry_broadcast_routes / booking_routes
    participant AZ as AuthorizationPolicy
    participant IS as InquiryService
    participant MR as InquiryMappingRepository
    participant BR as BookingRepository
    participant QR as QuoteRepository
    participant N as NotificationService

    OP->>RT: GET /api/inquiry-broadcast/operator/pending
    RT->>AZ: role operator
    RT->>IS: pending_for(operator_id from token)
    IS->>MR: find {operator_id, status pending, not expired}
    RT-->>OP: list
    OP->>RT: POST /operator/accept/{mapping_id} {price, aircraft, notes}
    RT->>AZ: mapping.operator_id == caller (IDOR check)
    RT->>IS: accept(mapping_id, quote)
    IS->>MR: update_one {id, status pending} to accepted (atomic, no double accept)
    IS->>QR: insert quote
    IS->>BR: push quote_id, status quotes_received
    IS->>N: notify customer
    C->>RT: POST /api/bookings/{booking_id}/accept-quote {quote_id}
    RT->>AZ: booking.customer_id == caller
    RT->>IS: accept_quote(booking_id, quote_id)
    IS->>BR: update_one {id, status quotes_received} to confirmed (atomic)
    IS->>MR: mark other mappings closed
    IS->>N: notify winning and losing operators
    RT-->>C: 200 booking
```

Today: `backend/routes/inquiry_broadcast_routes.py:122`, `backend/services/inquiry_broadcast_service.py:446`,
`backend/routes/booking_routes.py:376`.

## L5. Razorpay order, verification and webhook

```mermaid
sequenceDiagram
    autonumber
    actor C as Customer
    participant RT as razorpay_routes
    participant AZ as AuthorizationPolicy
    participant PS as PaymentService
    participant BR as BookingRepository
    participant GW as RazorpayGateway (PaymentGateway)
    participant OR as RazorpayOrderRepository
    participant IDEM as IdempotencyStore (Redis + Mongo)
    participant INV as InvoiceService
    participant EV as DomainEvents
    participant RZ as Razorpay API

    C->>RT: POST /api/razorpay/create-order {booking_id, amount, ...}
    RT->>AZ: authenticated, booking belongs to caller
    RT->>PS: create_order(booking_id, idempotency_key)
    PS->>BR: load booking
    PS->>PS: amount = booking payable (server-side), reject if client amount differs
    PS->>IDEM: reserve key
    PS->>GW: create order (amount_paise, receipt AY000123, notes)
    GW->>RZ: POST /v1/orders
    RZ-->>GW: order
    PS->>OR: insert razorpay_orders {status created, amount, amount_paise, ...}
    RT-->>C: {order_id, key_id, amount, prefill, theme}

    C->>RZ: Checkout
    RZ-->>C: payment_id, signature
    C->>RT: POST /api/razorpay/verify-payment
    RT->>PS: verify(order_id, payment_id, signature)
    PS->>GW: verify_payment_signature (HMAC-SHA256)
    alt invalid
        PS->>OR: status signature_failed
        RT-->>C: 400
    end
    PS->>OR: status paid (only from created)
    PS->>BR: payment_status paid
    PS->>EV: BookingPaid
    RT-->>C: 200

    RZ-)RT: POST /api/razorpay/webhook (X-Razorpay-Signature)
    RT->>GW: verify webhook signature on raw body (required, missing header = 400)
    RT->>IDEM: seen(event id)? reject replay
    RT->>PS: apply event (payment.captured / failed / refund.processed)
    PS->>OR: idempotent update
    EV-)INV: BookingPaid -> GST invoice
    EV-)EV: loyalty points, notifications, boarding pass
    RT-->>RZ: 200
```

Today: `backend/routes/razorpay_routes.py:68` (create-order), `:149` (verify), `:241` (webhook).
`[gap]` create-order has no authentication and trusts the client `amount` (`razorpay_routes.py:68-80`).
`[gap]` The webhook skips the signature check when the header or secret is missing
(`if RAZORPAY_WEBHOOK_SECRET and signature:`). `[gap]` No idempotency or replay store.
Stored fields in `razorpay_orders` and `bookings` are unchanged by these fixes.

## L6. Cancellation and refund

```mermaid
sequenceDiagram
    autonumber
    actor C as Customer
    actor FIN as Finance (checker)
    participant RT as booking_routes.cancel / invoice_routes.refund
    participant BS as BookingService
    participant CP as CancellationPolicy (Strategy)
    participant BR as BookingRepository
    participant RF as RefundService
    participant GW as PaymentGateway (Razorpay/Stripe/Cashfree)
    participant AUD as AuditLogger

    C->>RT: POST /api/bookings/{id}/cancel {reason}
    RT->>BS: cancel(booking_id, caller)
    BS->>BR: load, check owner and state allows cancel
    BS->>CP: refundable_amount(booking, now) per policy tier
    BS->>BR: status cancelled (atomic from allowed states)
    BS->>RF: request refund(amount, idempotency_key = booking_id + attempt)
    alt amount above maker-checker threshold
        RF-->>FIN: pending approval
        FIN->>RF: approve (step-up MFA)
    end
    RF->>GW: refund(payment_id, amount)
    GW-->>RF: refund id
    RF->>AUD: REFUND_CREATED
    Note over RF,GW: refund.processed webhook completes the record (same pattern as L5)
```

Today: `backend/routes/booking_routes.py:413`, `backend/routes/invoice_routes.py:302`,
`backend/routes/razorpay_routes.py:433`; cancellation fee tiers are published in `backend/routes/legal_routes.py:303` (20% / 30% / 50% by hours before departure) and configured through `backend/routes/pricing_engine_routes.py` and the admin `CancellationPolicyTab`.

## L7. KYC upload and download

```mermaid
sequenceDiagram
    autonumber
    actor C as Customer
    actor ADM as Admin verifier
    participant RT as customer_kyc_routes
    participant KS as KycService
    participant FV as FileValidator
    participant ENC as FileEncryption (key from Key Vault)
    participant ST as StorageProvider (AzureBlobStorage)
    participant BL as Blob container kyc
    participant DEF as Defender malware scan
    participant DR as KycDocumentRepository
    participant AUD as AuditLogger

    C->>RT: POST /api/customer/kyc-documents/upload (multipart)
    RT->>KS: upload(user_id from token, type, number, file)
    KS->>FV: size <= 5 MB, non-empty, magic bytes in allow-list (PDF, JPEG, PNG)
    KS->>KS: document_type sanitised to allow-list
    KS->>ENC: encrypt(bytes)
    ENC-->>KS: ciphertext (same Fernet format as today)
    KS->>ST: put(kyc/{TYPE}_{user}_{oid}.{ext}.enc)
    ST->>BL: PUT blob (managed identity, private endpoint)
    BL-)DEF: scan on upload, quarantine tag if malicious
    KS->>DR: insert metadata (same fields, file_path now the blob name)
    KS->>AUD: KYC_UPLOADED
    RT-->>C: 200

    ADM->>RT: GET /api/customer/kyc-documents/download/{doc_id}
    RT->>KS: download(doc_id, caller)
    KS->>KS: caller is owner or has kyc.read permission
    KS->>DR: load metadata
    KS->>ST: get(blob)
    KS->>ENC: decrypt
    KS->>AUD: KYC_ACCESSED (who, which document, from where)
    RT-->>ADM: stream file (no-store, attachment)
```

Today: `backend/routes/customer_kyc_routes.py:90` (upload), `:267` (download), encryption in
`backend/security_middleware.py:412`. Files are written to local disk today; `secure_uploads/kyc/*.enc` is also
committed to git (Phase 0 audit). Encrypted KYC files are streamed through the API rather than given a SAS URL,
because they must be decrypted server-side. Non-sensitive files (village documents, aircraft photos) use a
5-minute user-delegation SAS URL instead.
`ASSUMPTION` Existing `file_path` values stay as stored; the storage adapter maps an old local path to its blob name
so no document is rewritten.

## L8. Operator settlement and RazorpayX payout

```mermaid
sequenceDiagram
    autonumber
    participant WRK as worker: razorpay_settlement_sync
    participant SS as SettlementService
    participant SR as SettlementRepository
    participant BR as BookingRepository
    actor FIN as Finance maker
    actor CHK as Finance checker
    participant RT as admin_settlement_routes
    participant PO as RazorpayXGateway (PayoutGateway)
    participant RX as RazorpayX API
    participant AUD as AuditLogger

    WRK->>SS: build settlements for completed, paid bookings
    SS->>BR: bookings completed and not settled
    SS->>SS: gross - commission - TDS - GST (Money value object, paise ints in memory)
    SS->>SR: insert settlement (status pending, same fields as today)
    FIN->>RT: POST create payout batch
    RT->>SS: propose(batch)
    CHK->>RT: POST approve batch (step-up TOTP)
    RT->>SS: approve(batch, checker != maker)
    loop each settlement
        SS->>PO: payout(fund_account, amount, idempotency key = settlement id)
        PO->>RX: POST /v1/payouts
        RX-->>PO: payout id, status queued
        SS->>SR: status processing
    end
    RX-)RT: webhook payout.processed (signed)
    RT->>SS: mark paid (idempotent)
    SS->>AUD: PAYOUT_COMPLETED
```

Today: `backend/services/settlement_service.py`, `backend/routes/settlement_automation_routes.py`,
`backend/routes/admin_settlement_routes.py`, scheduler job `razorpay_settlement_sync` in `backend/scheduler.py`.
`[gap]` Maker-checker and step-up MFA for payouts are new controls (S.3).

## L9. Village landing permission

```mermaid
sequenceDiagram
    autonumber
    actor C as Customer / Operator
    actor L1 as Regional manager
    actor L2 as Admin
    participant RT as landing_permission_routes / admin_landing_permission_routes
    participant AS as ApprovalWorkflow (State pattern)
    participant LR as LandingPermissionRepository
    participant ST as StorageProvider
    participant N as NotificationService

    C->>RT: POST /api/landing-permissions/ {landing point, date, booking}
    RT->>LR: insert (status pending)
    C->>RT: POST /{id}/upload-document (NOC, village consent)
    RT->>ST: store document (Blob documents container)
    RT->>AS: submit(id)
    AS->>N: notify level-1 approver for the region
    L1->>RT: approve (level 1)
    RT->>AS: transition pending -> level1_approved (only by regional role)
    AS->>N: notify admin
    L2->>RT: POST /api/admin/landing-permissions/{id}/approve
    RT->>AS: transition level1_approved -> approved
    AS->>LR: update status, approval history
    AS->>N: notify requester and operator
```

Today: `backend/routes/landing_permission_routes.py:12`, `:46`, `backend/routes/admin_landing_permission_routes.py:43`,
`backend/services/approval_workflow.py`.

## L10. SOS alert

```mermaid
sequenceDiagram
    autonumber
    actor P as Passenger / Pilot app
    participant RT as sos_routes
    participant SOS as SosService
    participant BR as BookingRepository
    participant SR as SosAlertRepository
    participant BUS as Redis pub/sub
    participant N as NotificationService
    participant TW as TwilioGateway
    actor A as Admin dashboard

    P->>RT: POST /api/sos/alert {booking_id, lat, lon, type}
    RT->>SOS: raise(caller, payload)
    SOS->>BR: booking belongs to caller (or caller is assigned pilot)
    SOS->>SR: insert sos_alerts (status active)
    SOS->>N: notifications for every admin
    SOS->>BUS: PUBLISH sos:admins
    BUS-->>A: live alert on SOS dashboard (WebSocket)
    SOS-)TW: SMS/WhatsApp to duty manager and emergency contacts
    RT-->>P: 200 alert_id + safety instructions
    loop until resolved
        P->>RT: POST /alert/{id}/location
        RT->>SR: append location
        RT->>BUS: PUBLISH sos:{id}
    end
    A->>RT: PUT /admin/alert/{id} {status resolved, notes}
    RT->>SR: update + audit log
```

Today: `backend/routes/sos_routes.py:36` (alert, inserts `sos_alerts` and per-admin `notifications`), `:121`, `:265`.
`[gap]` Admin fan-out is in-app only today; SMS/WhatsApp escalation and the live pub/sub push are added.

## L11. Authorisation on every request

```mermaid
sequenceDiagram
    autonumber
    actor U as Caller
    participant MW as Middleware chain
    participant DEP as get_current_user (Depends)
    participant TS as TokenService
    participant SR as SessionRepository (revocation)
    participant POL as AuthorizationPolicy
    participant SVC as Service
    participant REPO as Repository

    U->>MW: request (cookie or Bearer)
    MW->>MW: correlation id, security headers, Redis rate limit
    MW->>DEP: resolve user
    DEP->>TS: decode JWT (alg pinned HS256, exp, iss)
    DEP->>SR: session not revoked (logout-all, password change)
    DEP-->>MW: user {id, roles}
    MW->>POL: require(role, permission) for this route
    alt denied
        POL-->>U: 403 (generic)
    end
    MW->>SVC: call with caller identity
    SVC->>REPO: query scoped by owner_id / operator_id / tenant
    REPO-->>SVC: only the caller's documents
    SVC-->>U: response
```

Today: `get_current_user` in `backend/routes/auth_routes.py` and role checks spread across route modules.
Negative tests per role are part of the Phase 3 test pack (Q.2 item 9).

## L12. Scheduler job in the worker

```mermaid
sequenceDiagram
    autonumber
    participant MAIN as worker.py
    participant DB as connect_to_mongo
    participant SCH as APScheduler (AsyncIOScheduler)
    participant LOCK as JobLock (Redis SET NX PX)
    participant JOB as job function (e.g. check_pilot_document_expiry)
    participant N as NotificationService
    participant LOG as App Insights (+ new job-run log, additive)

    MAIN->>DB: connect (w majority, journal true)
    MAIN->>SCH: start_scheduler() only if SCHEDULER_ENABLED=true
    SCH->>JOB: trigger fires (cron/interval)
    JOB->>LOCK: acquire job:{id}:{fire_time} ttl = max runtime
    alt acquired
        JOB->>JOB: do work in batches (cursor, limit)
        JOB->>N: send reminders
        JOB->>LOG: success, counts, duration
    else not acquired
        JOB->>LOG: skipped duplicate
    end
    Note over SCH: misfire_grace_time and coalesce=True so a restart does not replay a backlog
```

Today: `backend/scheduler.py` (16 `add_job` calls) started from `server.py` startup in every API process.
`[gap]` `worker.py` entry point and `SCHEDULER_ENABLED` flag are added in Phase 3; the API stops starting the scheduler.

## L13. WebSocket chat across replicas

```mermaid
sequenceDiagram
    autonumber
    actor C as Customer
    actor P as Pilot
    participant WS1 as websocket_chat (replica 1)
    participant WS2 as websocket_chat (replica 2)
    participant TS as TokenService
    participant AZ as AuthorizationPolicy
    participant CM as ConnectionManager (local sockets)
    participant BUS as RedisChatBus
    participant MR as ChatMessageRepository

    C->>WS1: connect /api/ws/chat/{booking_id}?token=...
    WS1->>TS: decode token
    alt invalid or expired
        WS1-->>C: close 4401
    end
    WS1->>AZ: caller is booking customer, assigned pilot/operator, or support
    alt not allowed
        WS1-->>C: close 4403
    end
    WS1->>CM: register(booking_id, socket, user from token)
    WS1->>BUS: SUBSCRIBE chat:{booking_id}
    P->>WS2: connect (same checks)
    C->>WS1: {"type":"chat","text":"..."} (max 4 KB, rate limited)
    WS1->>MR: insert message
    WS1->>BUS: PUBLISH chat:{booking_id} message
    BUS-->>WS1: message
    BUS-->>WS2: message
    WS1-->>C: echo with id
    WS2-->>P: deliver
```

Today: `backend/routes/websocket_chat_routes.py:65`. `[gap]` The token query parameter is read but not
verified; `name`, `type` and `user_id` are taken from the query string. `[gap]` `ConnectionManager` is in process
memory, so users on different replicas cannot see each other until the Redis bus is added.

## L14. AI chatbot through Azure OpenAI

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant RT as chatbot_routes / ai_routes
    participant AIS as AiService (one class, was two ai_service.py files)
    participant RED as PromptGuard
    participant LLM as LlmProvider
    participant AOAI as AzureOpenAiProvider
    participant ID as DefaultAzureCredential (managed identity)
    participant OA as Azure OpenAI (private endpoint)

    U->>RT: POST message
    RT->>AIS: chat(session_id, user_id, text)
    AIS->>RED: strip PII (Aadhaar, PAN, card, phone), length cap
    AIS->>LLM: complete(system_prompt, history, text)
    LLM->>AOAI: same interface as the old LlmChat wrapper
    AOAI->>ID: get token for cognitiveservices
    AOAI->>OA: chat completions (deployment gpt-4o-mini)
    OA-->>AOAI: answer (content filter applied)
    AOAI-->>AIS: text
    AIS->>RED: output filter (no secrets, no tool calls)
    AIS-->>RT: answer (same response shape)
    RT-->>U: 200
```

Today: `backend/services/ai_service.py` and `backend/ai_service.py` both wrap `emergentintegrations.llm.chat.LlmChat`
with `EMERGENT_LLM_KEY` and a hard-coded fallback key (Phase 0 audit, Critical).

## L15. Container start-up and health

```mermaid
sequenceDiagram
    autonumber
    participant ACA as Container Apps
    participant APP as server.py (uvicorn)
    participant SET as Settings (pydantic-settings)
    participant KV as Key Vault refs
    participant DB as MongoDB
    participant R as Redis

    ACA->>KV: resolve secret refs with managed identity
    ACA->>APP: start container (non-root), env vars injected
    APP->>SET: load and validate settings (fail fast if JWT_SECRET_KEY, MONGO_URL missing)
    APP->>DB: connect, ping
    APP->>APP: ensure indexes (additive only)
    APP->>R: connect (Entra token)
    ACA->>APP: GET /health (liveness)
    APP-->>ACA: 200
    ACA->>APP: readiness probe
    APP->>DB: ping
    APP->>R: ping
    APP-->>ACA: 200 ready, traffic shifts to new revision
```
