# High-Level Sequence Diagrams

How the major parts of AirYatra talk to each other on Azure. Each diagram shows systems, not functions; the
[low-level diagrams](03-sequence-diagrams-low-level.md) zoom into the code paths. Components match
[01-target-architecture.md](01-target-architecture.md) and [`infra/terraform`](../../infra/terraform/README.md).

| # | Flow | Why it matters |
|---|---|---|
| H1 | [Request path through the platform](#h1-request-path-through-the-platform) | Every page load and API call |
| H2 | [Booking lifecycle, end to end](#h2-booking-lifecycle-end-to-end) | Core revenue journey (Q.2 items 2 and 3) |
| H3 | [Payment and settlement money flow](#h3-payment-and-settlement-money-flow) | Payments, invoices, payouts (Q.2 items 2, 4, 6) |
| H4 | [Real-time: chat, live tracking and SOS](#h4-real-time-chat-live-tracking-and-sos) | WebSockets across replicas (Q.2 item 8) |
| H5 | [Background jobs run exactly once](#h5-background-jobs-run-exactly-once) | Scheduler in the worker (Q.2 item 10) |
| H6 | [Build and deploy (CI/CD)](#h6-build-and-deploy-cicd) | How code reaches prod |
| H7 | [Data migration and cutover](#h7-data-migration-and-cutover) | Phase 2, zero data change |
| H8 | [Regional disaster recovery](#h8-regional-disaster-recovery) | RPO 15 min / RTO 4 h |

---

## H1. Request path through the platform

```mermaid
sequenceDiagram
    autonumber
    actor U as User browser / PWA
    participant AFD as Front Door + WAF
    participant WEB as Static site (Blob)
    participant API as Container Apps api
    participant R as Managed Redis
    participant DB as Atlas (Private Link)
    participant KV as Key Vault
    participant AI as App Insights

    U->>AFD: GET https://airyatra.co.in/booking
    AFD->>AFD: TLS, WAF rules (OWASP, bot, rate limit)
    AFD->>WEB: /booking has no extension, rewrite to /index.html
    WEB-->>AFD: index.html + hashed JS/CSS (cached at edge)
    AFD-->>U: 200 + security headers (HSTS, nosniff, frame DENY)

    U->>AFD: POST /api/quotes (cookie session)
    AFD->>AFD: WAF inspects body, per-IP API rate limit
    AFD->>API: forward over Private Link (internal environment)
    Note over API,KV: Secrets were resolved from Key Vault at revision start via managed identity
    API->>R: per-user rate limit and cache lookup
    alt cache hit
        R-->>API: cached response
    else cache miss
        API->>DB: query (owner-scoped)
        DB-->>API: documents (unchanged schema)
        API->>R: store with TTL
    end
    API-->>AFD: 200 JSON (same contract as today)
    AFD-->>U: 200 JSON
    API--)AI: trace, metrics, logs (PII masked)
```

## H2. Booking lifecycle, end to end

```mermaid
sequenceDiagram
    autonumber
    actor C as Customer
    participant FE as AirYatra web app
    participant API as AirYatra API
    participant DB as MongoDB (Atlas)
    participant N as Notifications (in-app, email, WhatsApp/SMS)
    actor OP as Operators within 500 km
    participant PG as Payment gateway
    participant W as Worker (scheduler)

    C->>FE: search route, date, passengers
    FE->>API: request price estimate
    API->>DB: aircraft catalog, route pricing, peak season, corporate contract
    API-->>FE: fare estimate and price breakup
    C->>FE: submit booking request
    FE->>API: create booking
    API->>DB: insert booking (status pending_quotes)
    API-)N: broadcast inquiry to nearby operators
    N-)OP: new inquiry with route and pax
    OP->>API: accept and quote (or reject)
    API->>DB: save quote, update mapping
    API-)N: quote received
    N-)C: notify customer
    C->>FE: accept a quote
    FE->>API: accept quote
    API->>DB: booking confirmed_pending_payment
    C->>PG: pay (see H3)
    PG-)API: signed webhook payment.captured
    API->>DB: booking paid, invoice (GST), loyalty points
    API-)N: confirmation, invoice, boarding pass
    W->>DB: reminders before departure, document expiry checks
    W-)N: reminders to customer, pilot, operator
    Note over C,OP: Flight day: live tracking and SOS (H4). After the flight: review, settlement to operator (H3)
```

## H3. Payment and settlement money flow

```mermaid
sequenceDiagram
    autonumber
    actor C as Customer
    participant API as AirYatra API
    participant DB as MongoDB
    participant RZ as Razorpay / Stripe / Cashfree
    participant RX as RazorpayX (payouts)
    participant W as Worker
    actor FIN as Finance (checker)
    actor OPS as Operator

    C->>API: pay for booking
    API->>DB: load booking, recompute amount server-side
    API->>RZ: create order (amount from server, idempotency key)
    RZ-->>API: order id
    API-->>C: order id + public key id
    C->>RZ: checkout (card / UPI / netbanking)
    RZ-->>C: payment id + signature
    C->>API: verify payment
    API->>API: verify signature (HMAC)
    API->>DB: order paid, booking paid
    RZ-)API: webhook payment.captured (signed)
    API->>API: verify signature, reject replays (event id store)
    API->>DB: idempotent upsert, GST invoice
    Note over API,DB: Refunds follow the same pattern: cancellation policy computed server-side, idempotency key, maker-checker above threshold

    W->>RZ: daily settlement sync (Razorpay, Stripe)
    W->>DB: reconcile, flag mismatches
    W->>DB: compute operator settlements (commission, TDS, GST)
    FIN->>API: approve payout batch (step-up MFA)
    API->>RX: create payouts (idempotency key per settlement)
    RX-)API: payout.processed webhook (signed)
    API->>DB: settlement paid, audit log
    API-)OPS: settlement statement
```

## H4. Real-time: chat, live tracking and SOS

```mermaid
sequenceDiagram
    autonumber
    actor C as Customer
    actor P as Pilot / Operator
    actor A as Admin (SOS desk)
    participant AFD as Front Door
    participant API1 as api replica 1
    participant API2 as api replica 2
    participant R as Redis pub/sub
    participant DB as MongoDB
    participant TW as Twilio SMS/WhatsApp

    C->>AFD: WebSocket /api/ws/chat/{booking_id}
    AFD->>API1: upgrade (sticky for the connection)
    API1->>API1: validate JWT, check customer owns booking
    P->>AFD: WebSocket /api/ws/chat/{booking_id}
    AFD->>API2: upgrade
    API2->>API2: validate JWT, check pilot assigned to booking
    C->>API1: chat message
    API1->>DB: persist message
    API1->>R: PUBLISH chat:{booking_id}
    R-->>API2: message
    API2-->>P: deliver

    P->>API2: live position update
    API2->>DB: store position
    API2->>R: PUBLISH tracking:{booking_id}

    C->>API1: POST /api/sos/alert (location)
    API1->>DB: insert sos_alert, notify admins
    API1->>R: PUBLISH sos:admins
    R-->>API2: alert
    API2-->>A: live SOS on dashboard
    API1-)TW: SMS/WhatsApp to emergency contacts and duty manager
    A->>API2: acknowledge and update alert
    API2->>DB: status, audit log
```

## H5. Background jobs run exactly once

```mermaid
sequenceDiagram
    autonumber
    participant API as api replicas (2..N)
    participant WRK as worker (1 replica)
    participant R as Redis
    participant DB as MongoDB
    participant EXT as Email / SMS / gateways

    Note over API: SCHEDULER_ENABLED=false, no jobs start here
    WRK->>WRK: start APScheduler (SCHEDULER_ENABLED=true)
    loop every trigger (e.g. pilot_document_expiry daily)
        WRK->>R: SET lock:job:{id}:{fire_time} NX PX ttl
        alt lock acquired
            WRK->>DB: read due items
            WRK->>EXT: send reminders / sync settlements
            WRK->>DB: write results and job run log
        else lock held (overlapping deploy)
            WRK->>WRK: skip, log duplicate prevented
        end
    end
    WRK--)API: nothing, results are visible through the DB and /api/scheduler status routes
```

## H6. Build and deploy (CI/CD)

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer
    participant GH as GitHub (PR)
    participant CI as GitHub Actions
    participant ENTRA as Entra ID (OIDC)
    participant ACR as Container Registry
    participant WEB as Static web storage
    participant ACA as Container Apps
    actor V as Vishal (prod approver)

    Dev->>GH: push branch, open PR
    GH->>CI: run gates
    CI->>CI: lint, typecheck, unit, integration (Testcontainers), contract diff, data-shape, SAST, deps, secrets, terraform validate + Checkov
    CI-->>GH: status checks (merge blocked on any failure)
    Dev->>GH: merge to main
    GH->>CI: build workflow
    CI->>ENTRA: exchange GitHub OIDC token
    ENTRA-->>CI: short-lived Azure token (dev identity)
    CI->>CI: docker build (multi-stage, non-root), Trivy scan, SBOM
    CI->>ACR: push api and worker images (tag = git sha)
    CI->>WEB: upload React build
    CI->>ACA: update dev revisions to new image
    CI->>ACA: smoke tests and E2E smoke on dev
    CI->>V: request approval for prod environment
    V-->>CI: approve
    CI->>ENTRA: exchange OIDC token (prod identity)
    CI->>ACA: new prod revision, health probes must pass
    alt probes fail
        ACA->>ACA: keep previous revision serving
    end
```

## H7. Data migration and cutover

```mermaid
sequenceDiagram
    autonumber
    actor V as Vishal
    participant OLD as Emergent deployment (current Mongo)
    participant TOOL as Migration runner (verify scripts)
    participant ATL as Atlas (Central India)
    participant NEW as Azure deployment
    participant DNS as DNS

    V->>TOOL: approve rehearsal
    TOOL->>OLD: mongodump --oplog (read-only)
    TOOL->>ATL: mongorestore --preserveUUID (same _id, types, values)
    TOOL->>OLD: per-collection counts and hashes
    TOOL->>ATL: per-collection counts and hashes, index parity
    TOOL-->>V: verification report (must be 100% equal)
    TOOL->>NEW: run regression pack read-only against the copy
    V->>OLD: freeze writes (maintenance banner), stop old scheduler
    TOOL->>OLD: final dump
    TOOL->>ATL: final restore + verify again
    TOOL->>ATL: add new indexes (additive only)
    V->>DNS: switch airyatra.co.in to Front Door (written approval)
    NEW-->>V: smoke tests green
    alt anything fails
        V->>DNS: point back to Emergent, unfreeze
    end
```

## H8. Regional disaster recovery

```mermaid
sequenceDiagram
    autonumber
    participant MON as Azure Monitor / Atlas alerts
    actor ON as On-call
    participant ATL as Atlas replica set
    participant TF as Terraform (DR tfvars)
    participant SIN as South India resources
    participant AFD as Front Door

    MON-)ON: Central India region outage
    alt stage 2 (DR node enabled)
        ATL->>ATL: South India electable node elected primary automatically
    else stage 1
        ON->>ATL: restore latest PITR snapshot to South India cluster
    end
    ON->>TF: apply prod with location = southindia (new resource group)
    TF->>SIN: Container Apps, Redis, Key Vault, private endpoints
    ON->>SIN: point Blob to the RA-GZRS secondary (account failover)
    ON->>AFD: switch API origin to South India environment
    AFD-->>ON: health probe green
    Note over ON,AFD: Targets: RPO 15 min (Atlas continuous backup), RTO 4 h
```
