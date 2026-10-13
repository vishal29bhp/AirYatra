# Threat Model (STRIDE)

Scope: booking, payment, payout, KYC, SOS and admin flows (S.2 A04), on the Azure design in
[01-target-architecture.md](01-target-architecture.md). Flows referenced as L1..L15 are in
[03-sequence-diagrams-low-level.md](03-sequence-diagrams-low-level.md). Evidence for "today" findings is in the
Phase 0 [security audit](../phase0/SECURITY_AUDIT.md). Review this file whenever a change touches auth, money,
KYC, file upload or admin (S.6).

## Trust boundaries

| # | Boundary | Crossed by |
|---|---|---|
| B1 | Internet to Front Door | Every browser, PWA and webhook request |
| B2 | Front Door to API (Private Link) | Allowed routes only, after WAF |
| B3 | API to data services (private endpoints) | Mongo, Redis, Blob, Key Vault, OpenAI |
| B4 | API to third parties (egress) | Razorpay, RazorpayX, Stripe, Cashfree, Twilio, SendGrid, Google, OpenWeather |
| B5 | Third parties to API (webhooks) | Payment and payout callbacks, Twilio status |
| B6 | Staff privilege boundary | Admin, Finance, HR, CEO routes |
| B7 | CI/CD to Azure | GitHub Actions with OIDC |

## Threats and controls

| Flow | STRIDE | Threat | Today | Control (target) | Phase |
|---|---|---|---|---|---|
| L1 login | S | Credential stuffing, brute force | Lockout after 5 failures; in-memory rate limit per process | WAF auth rate rule (30/min/IP), Redis-backed limiter and lockout shared by all replicas, CAPTCHA after repeated failures, breached-password check | 1 (WAF), 3 |
| L1 login | S | Stolen long-lived token replayed | 7-day JWT in `localStorage` | 15-min access token, rotating refresh token with reuse detection, HttpOnly Secure SameSite cookies, revocation on logout/password change | 3 |
| L1 OTP | S/D | OTP brute force or SMS/email bombing | OTP service with resend cooldown | Single-use, 5-min expiry, constant-time compare, per-user and per-IP OTP limits | 3 |
| L2 Google | S/E | **Account takeover: `/api/auth/google/emergent-callback` issues a token for any e-mail the browser posts, including admin accounts, and skips OTP/TOTP** (Phase 0 S-02) | Live in code today | Remove the Emergent callback (or require a server-verified Emergent session) before anything else; direct Google OAuth with verified id_token | **Immediately**, 3 |
| L2 Google | S | Login CSRF / code injection | Emergent-managed flow | State, nonce, PKCE; id_token verified against Google JWKS | 3 |
| L3 booking | T | Client sets `estimated_price` or other money fields | `booking_data: dict` stored as sent | Typed request model with same field names, server recomputes every fare | 3 |
| L3 booking | T/I | NoSQL injection via `$`-prefixed keys in dict bodies | Raw dicts reach Mongo in several routes | Reject `$` keys and unknown fields, never pass client dicts into filters, `javascript_enabled=false` on Atlas | 1 (Atlas), 3 |
| L4 quote | E | Operator accepts/reads another operator's inquiry (IDOR) | Partial checks | Repository queries always scoped by `operator_id` from token; negative tests | 3 |
| L4 quote | T | Race: two quotes accepted | Non-atomic read then write | Conditional `update_one` on current status | 3 |
| L5 payment | T | Price tampering at create-order | Client `amount` trusted, endpoint unauthenticated | Auth + owner check, amount from booking, mismatch rejected | 3 |
| L5 webhook | S/T | Forged webhook marks booking paid | Signature skipped if header or secret missing | Signature mandatory on raw body, replay store by event id, idempotent handlers | 3 |
| L6 refund | T/R | Double refund, refund abuse | No idempotency | Idempotency key, maker-checker above threshold, audit log | 3 |
| L7 KYC | I | KYC documents exposed | `.enc` files committed in git; local disk; key falls back to a random per-process value | Blob private container over private endpoint, Defender scan, key only in Key Vault, purge git history (approval needed), DPDP breach assessment | 1, 3 |
| L7 KYC | T | Malicious file upload | Magic-byte check, 5 MB limit | Plus Defender malware scan on upload, random names, never served from app domain | 1 |
| L8 payout | E/T | Insider creates or alters payouts | Single actor | Maker-checker, step-up TOTP, idempotency per settlement, payout spike alert | 3 |
| L9 approvals | E | Skipping an approval level | Status field set by route | State machine allows only legal transitions by role | 3 |
| L10 SOS | D | SOS not delivered when one replica or channel fails | In-app notifications only | Redis pub/sub to every replica + SMS/WhatsApp escalation + alert if unacknowledged | 3 |
| L11 authZ | E | Role escalation via `/auth/set-role` or admin routes | Role checks spread across modules | Central `AuthorizationPolicy`, admin router with step-up MFA, negative tests per role | 3 |
| L12 scheduler | T/D | Jobs run N times with N replicas (duplicate payouts/reminders) | Scheduler inside every API process | Single worker + Redis lock per fire time | 1 (infra), 3 (code) |
| L13 chat | S/I | Anyone with a booking id joins its chat and impersonates a user | Token not verified, name/type from query | Verify JWT on connect, authorise per booking, identity from token, message size and rate limits | 3 |
| L14 AI | I | Prompt injection exfiltrates data; PII sent to the model | Emergent key hard-coded as fallback | Remove key, Azure OpenAI with managed identity, PII redaction, no tool access, output filter | 1, 3 |
| All | I | Secrets leaked from repo or images | Hard-coded fallback LLM key, credentials file in `memory/` | Key Vault only, gitleaks pre-commit + push protection, rotate every key at cutover | 1, 3 |
| All | R | No trustworthy record of sensitive actions | `audit_logs` collection (mutable) | Also write to WORM `audit-logs` Blob container; Key Vault and Blob audit logs to Log Analytics | 1, 3 |
| All | S/D | Behind Front Door every request arrives from a Front Door IP, so per-IP limits, lockout IPs and audit IPs collapse to one value | `request.client.host` used directly | Trust `X-Azure-ClientIP` / `X-Forwarded-For` only from Front Door (check `X-Azure-FDID` equals this profile's id) | 3 |
| All | D | Volumetric or app-layer DoS | Process-local token bucket | Front Door edge, WAF rate rules, bot manager, autoscale, budget alerts | 1 |
| B7 CI/CD | E | Stolen deploy credential | n/a | OIDC (no secret), prod environment needs Vishal's approval, Contributor scoped to one resource group | 1 |
| B3 data | I | Data services reachable from internet | Unknown (Emergent) | Public network access disabled on Mongo (Private Link), Redis, Blob, OpenAI; Key Vault public only for deployer IPs | 1 |

## Abuse cases to test (feeds Q.2 regression pack)

1. Create a Razorpay order with `amount: 1` for a ₹2 lakh booking: must be rejected.
2. POST a webhook without `X-Razorpay-Signature`: must return 400 and change nothing.
3. Replay a valid webhook twice: second call is a no-op.
4. Customer A fetches customer B's booking, invoice, KYC document or chat: 403/404.
5. Operator accepts an inquiry mapped to another operator: 403/404.
6. Send `{"email": {"$ne": null}}` as login email: 422, no query executed.
7. Accept the same quote concurrently from two sessions: exactly one succeeds.
8. Cancel and refund twice in parallel: one refund created.
9. Start three API replicas: each scheduled job runs once per trigger.
10. Connect to `/api/ws/chat/{id}` with no token or someone else's booking: socket closed.
