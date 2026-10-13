# AirYatra data dictionary (Phase 0, derived from code)

> **Source of truth:** static analysis of `backend/**/*.py` (including `backend/tests` and `backend/scripts`) by `tools/audit/collection_inventory.py`, plus a read of `backend/models.py`, `backend/pricing_models.py` and the Pydantic models in routes. **No database was accessed.** Anything that depends on the live data (actual types stored, documents written by old code, indexes created by hand) is marked **ASSUMPTION** and must be confirmed in Phase 2 by sampling the real database.
>
> Raw output: [`collection_inventory.json`](collection_inventory.json). Regenerate with:
> `python3 tools/audit/collection_inventory.py -o docs/phase0/collection_inventory.json` and
> `python3 tools/audit/render_data_dictionary.py docs/phase0/collection_inventory.json --header <this header> -o docs/phase0/DATA_DICTIONARY.md`.

## 1. Summary

| Metric | Value | Evidence |
|---|---|---|
| Python files scanned / failed to parse | 182 / 0 | `collection_inventory.json` → `files_scanned`, `parse_errors` |
| Distinct collections referenced | **285** (master prompt C.2 estimated ~288) | `collection_inventory.json` → `collection_count` |
| Collections referenced by exactly one call site | 32 | compact table, section 4 |
| Index specifications in code | **67**: 57 in the `INDEXES` table of `backend/db_optimization.py:14-100` (16 collections) and 10 `create_index` calls in `backend/scripts/seed_landing_data.py:376-385` | section 2.6 |
| Dynamic collection access | 1 (`db[collection_name]`, `backend/db_optimization.py:108`, iterates the `INDEXES` table) | `dynamic_accesses` |
| Pydantic model / Enum classes found | 328 | `pydantic_models` |

## 2. Cross-cutting conventions (what a migration must preserve byte for byte)

### 2.1 Document IDs
| Pattern | Where | Evidence |
|---|---|---|
| **Application `id` = `str(uuid.uuid4())`**, Mongo `_id` left as auto ObjectId. Every read uses `{"id": ...}` and projects `{"_id": 0}`. Dominant pattern. | 327 write sites classify `id` as UUID string; e.g. `users` (`backend/routes/auth_routes.py:96`), `bookings` (`backend/routes/booking_routes.py:82`) | `collection_inventory.json` fields.id.kinds |
| `id` as a **prefixed custom string** (`f"duty_{ObjectId()}"`, `f"conv_{ObjectId()}"`, `test-stripe-inquiry-1`) | `pilot_mobile_routes.py:397,466`, `pilot_chat_routes.py:121,147` | 58 write sites classified `str` |
| **`_id` set by code to a string** | `ai_warnings`, `bank_accounts`, `cash_entries`, `favorites`, `finance_transactions`, `notifications`, `sos_alerts` | `fields._id.sources.insert` |
| **`_id` queried as ObjectId** of a value that is elsewhere a UUID `id` | `backend/routes/command_center_routes.py:107,113,134` (`users` by `ObjectId(flight["operator_id"])`), `backend/routes/razorpay_routes.py:318-320` (`bookings` by `ObjectId(order["booking_id"])`) | These lookups cannot match UUID-keyed documents; ASSUMPTION they silently fail today (see SECURITY_AUDIT / CODE_MAP). |
| No `id` field at all (only auto `_id`) | 28 inserted collections incl. `account_lockouts`, `razorpay_orders`, `razorpay_webhooks`, `revoked_tokens`, `payment_otps`, `loyalty_profiles`, `live_tracking` | compact table "ID" column |

### 2.2 Dates and times
| Format | Write sites | Typical code | Notes |
|---|---|---|---|
| **ISO-8601 string** | **854** | `datetime.utcnow().isoformat()` (naive, no offset) or `datetime.now(timezone.utc).isoformat()` (with `+00:00`) | Majority format. Two sub-variants (with and without UTC offset) coexist; string comparison/sort across them is lexically, not chronologically, correct only when the variant is the same. ASSUMPTION: both variants exist in live data. |
| **BSON Date** (`datetime` object) | **207** | `datetime.now(timezone.utc)` / `datetime.utcnow()` passed directly | 43 collections are Date-only, e.g. `documents_vault`, `razorpay_orders`, `razorpay_webhooks`, `account_lockouts`, `finance_transactions`, `memberships`, `corporates`, `customer_kyc_documents` |
| **Mixed in the same collection** | 11 collections | e.g. `bookings.captured_at` is a Date (`razorpay_routes.py:320`) while every other `bookings.*_at` is ISO; `bookings.paid_at` is ISO in `payment_routes.py:131` but Date elsewhere; `notifications.created_at` ISO 18 sites / Date 6 sites | `bookings`, `generated_reports`, `invoices`, `notifications`, `payment_transactions`, `platform_settings`, `sos_alerts`, `user_sessions`, `vendor_bills`, `vendor_payments`, `verification_logs` |
| `strftime` strings (`"%Y-%m-%d"`) | 8 | dates without time | `compliance_reports`, `duty_logs`, `helipad_availability`, `inventory_slots`, `ledger_entries`, `user_sessions` |
| Pydantic models declare `datetime` | `backend/models.py:65-66,99-100,150-151,...` (`Field(default_factory=datetime.utcnow)`) | but routes mostly build plain dicts with ISO strings, so the models are **not** the persistence schema (`models.py` is imported for `UserRole` and a handful of request models only: `auth.py:6`, `middleware.py:6`, `quote_routes.py:3`, `membership_routes.py:12`, `corporate_routes.py:12`, `document_vault_routes.py:18`, `landing_infrastructure_routes.py:14`). |

Consequence for Phase 2: the migration must copy values verbatim (mongodump/mongorestore preserves both types); any later "normalise dates" idea is a schema change and stays a future option. The TTL index `sessions.expires_at` (`db_optimization.py:83`) only expires documents whose `expires_at` is a BSON Date; ASSUMPTION: string values never expire.

### 2.3 Money
| Convention | Evidence |
|---|---|
| **Rupees as float/number** in business collections (`bookings.total_amount`, `quotes.amount`, `invoices.*`, `payment_transactions.amount`, `payroll.net_salary`, `settlements.payout_amount`) | Pydantic `float` in `models.py:145-146,158,182-184`; write sites classify as `float`/`number`; `round(x, 2)` is common |
| **Paise as int only at the gateway edge**, stored as a companion field `amount_paise` | `payment_orders.amount_paise` (`backend/routes/payment_routes.py:65,92`), `razorpay_orders.amount_paise` (`backend/routes/razorpay_routes.py:79,105`) |
| Converted back from paise on receipt | `razorpay_routes.py:302` (`/ 100`), `backend/services/payment_service.py:133` |
| Stripe amounts | handled as cents/paise inside `finance_reconciliation_routes.py:239`; ASSUMPTION stored as returned by Stripe in `stripe_balance_transactions` |
| `currency` field | mostly absent (INR implied); `payment_transactions.currency` has both `INR` and `inr` (`collection_inventory.json`) |

### 2.4 Enumerations (stored as lower-case strings)
Stored values are plain strings; `str, Enum` classes are written via `.value` (`enum_value` kind). Canonical enums: `UserRole` (`backend/models.py:6-24`: customer, operator, regional_manager, helipad_owner, hr, finance, marketing, sales, support, operations, employee, admin, super_admin, cfo, finance_head, accounts_manager, treasury_analyst), `BookingStatus` (`models.py:26-36`), `ApprovalStatus` (`models.py:46-49`), `OperatorStatus` (`models.py:51-54`). **The code writes values outside these enums**, e.g. `bookings.status` also takes `boarding`, `departed`, `operator_assigned`, `passenger_details_filled`, `pending`, `quote_rejected` (not in `BookingStatus`), and `operators.status` takes `pending_verification`, `rejected` (not in `OperatorStatus`). Per-field string constants are listed in sections 3 and 4 as "enum candidates".

### 2.5 Other value conventions
| Item | Convention | Evidence |
|---|---|---|
| Roles on users | `users.roles` is an **array** of role strings (filtered 42 times); a few legacy paths also read singular `users.role` | `collection_inventory.json` users.fields |
| Passwords | `users.password_hash` = passlib bcrypt | `backend/auth.py:8,14-16` |
| TOTP secrets | `users.totp_secret` / `totp_secret_pending` written through `_encrypt_secret` | `backend/services/totp_service.py:56,315` |
| Third-party API keys | stored **in Mongo** in `api_keys_settings` (`type: "api_keys"`), `twilio_config`, `zoho_config`, `tally_config` | `backend/routes/settings_routes.py:393-401`, `twilio_routes.py:103-107`, `zoho_routes.py:17-18,59` |
| Emergent auth artefacts | `users.auth_provider` = `google_emergent` / `emergent_google`, `users.emergent_session_token` | `auth_routes.py:1666,1721`, `google_auth_routes.py:563,568` |
| Settings singletons | `settings` collection keyed by `type` (`loyalty_tiers`, `api_keys`, `google_auth`, ...) | `loyalty_routes.py:112`, `inquiry_broadcast_service.py:46,391` |

### 2.6 Indexes
- **57 index specs** live in `INDEXES` (`backend/db_optimization.py:14-100`) for 16 collections (`users`, `bookings`, `inquiries`, `quotes`, `operators`, `notifications`, `crm_leads`, `call_logs`, `support_tickets`, `audit_logs`, `sessions`, `landing_points`, `fleet`, `payments`). They are applied on every API start (`backend/server.py:464-468` → `optimize_database()`).
- **Bug / ASSUMPTION:** `optimize_database()` opens its **own** client and uses `client.airyatra` (`backend/db_optimization.py:127-129`) instead of `DB_NAME` (default `airyatra_db`, `backend/config.py:15`). Unless `DB_NAME=airyatra`, these 57 indexes are created on an unused database and **the application database has none of them**. Errors are swallowed at debug level (`db_optimization.py:118-120`). Index parity must be read from the live DB in Phase 2.
- Unique indexes declared on fields that not every insert sets (`inquiries.inquiry_number`, `support_tickets.ticket_number`, `bookings.booking_number`, `call_logs.call_sid`, `operators.user_id`): if these ever get applied to the real DB, documents missing the field collide on `null`. ASSUMPTION, verify before adding them in Phase 3.
- `sessions` (TTL) and `payments`/`fleet` are indexed but barely used (`sessions` 1 call site, `payments` 5); the live session collection is `user_sessions` (28 call sites, no index).
- `landing_points` has a `2dsphere` index on `location`, but code writes `latitude`/`longitude` scalars (e.g. `scripts/seed_landing_data.py`), never `location`.
- **10 `create_index` calls** in `backend/scripts/seed_landing_data.py:376-385` (`landing_points`, `helipad_availability`, `landing_rent`, `village_landing_permissions`) run only when the seed script is executed.
- Hot query keys with **no** index anywhere in code (top filters): `bookings.id` (94 filters), `users.id` (99), `operators.id` (52), `inquiries.id` (40), `aircraft_catalog.id` (28), `aircraft.id`/`operator_id`, `pilots.id`/`operator_id`, `payment_transactions.payment_status`, `documents_vault.owner_id`/`document_id`, `user_sessions.*`. Candidates for additive indexes in Phase 3.

## 3. Top 25 collections by code references

Legend for **Seen as**: I = written by insert, S = `$set`, SoI = `$setOnInsert`, F = used in a filter, O = sort key, `$inc`/`$push`/... = other update operators; the number is how many call sites. **Format** is inferred from the value expression at the write site (e.g. `datetime.utcnow().isoformat()` → ISO-8601 string, `datetime.now(timezone.utc)` → BSON Date). "runtime value" means the value comes from a variable or request field and the type cannot be read statically. Fields seen only as sort keys after a `$group` stage are aggregate aliases, not stored fields.

### `bookings`

- **References:** 208 in 58 files. **Operations:** find_one 61, find 47, update_one 35, count_documents 31, aggregate 23, index_spec 7, insert_one 2, update_many 2.
- **ID strategy:** `id` UUID string; `_id` used in filters. **Date format:** MIXED (ISO 37 / Date 2).
- **Referencing modules:** `db_optimization.py`, `routes/accounting_routes.py`, `routes/admin_analytics_routes.py`, `routes/admin_approval_routes.py`, `routes/admin_booking_management_routes.py`, `routes/admin_landing_permission_routes.py`, `routes/admin_operator_management_routes.py`, `routes/admin_payments_routes.py`, `routes/admin_routes.py`, `routes/admin_settlement_routes.py`, `routes/ai_advisor_routes.py`, `routes/ai_pricing_routes.py`, `routes/ai_reports_routes.py`, `routes/ai_routes.py`, `routes/ai_sales_routes.py`, `routes/analytics_routes.py`, `routes/boarding_pass_routes.py`, `routes/booking_routes.py`, `routes/calendar_sync_routes.py`, `routes/ceo_routes.py`, `routes/chat_routes.py`, `routes/command_center_routes.py`, `routes/currency_routes.py`, `routes/customer_routes.py`, `routes/email_routes.py`, `routes/feedback_routes.py`, `routes/finance_treasury_routes.py`, `routes/flight_tracking_live_routes.py`, `routes/hr_routes.py`, `routes/inquiry_broadcast_routes.py`, `routes/insurance_routes.py`, `routes/journey_routes.py`, `routes/landing_infrastructure_routes.py`, `routes/landing_permission_routes.py`, `routes/live_tracking_routes.py`, `routes/loyalty_routes.py`, `routes/multileg_booking_routes.py`, `routes/operator_routes.py`, `routes/payment_routes.py`, `routes/pilot_mobile_routes.py`, `routes/predictive_analytics_routes.py`, `routes/pricing_routes.py`, `routes/quote_routes.py`, `routes/razorpay_routes.py`, `routes/regional_manager_routes.py`, `routes/reports_routes.py`, `routes/reviews_routes.py`, `routes/route_intelligence_routes.py`, `routes/search_routes.py`, `routes/settlement_automation_routes.py`, `routes/sos_routes.py`, `routes/stripe_payment_routes.py`, `routes/tally_routes.py`, `routes/weather_routes.py`, `routes/zoho_routes.py`, `scheduler.py`, `services/inquiry_broadcast_service.py`, `services/settlement_service.py`.
- **Indexes declared in code:** `booking_number:1` unique=True, name='booking_number_unique' (db_optimization.py:22); `customer_id:1` name='customer_idx' (db_optimization.py:23); `operator_id:1` name='operator_idx' (db_optimization.py:24); `status:1` name='status_idx' (db_optimization.py:25); `travel_date:1` name='travel_date_idx' (db_optimization.py:26); `created_at:-1` name='created_at_idx' (db_optimization.py:27); `status:1, created_at:-1` name='status_created_compound' (db_optimization.py:28).

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `_id` | F4 | (read only here) |  |
| `accepted_operator_id` | S1 | runtime value |  |
| `accepted_quote` | S1 | object |  |
| `accepted_quote_id` | S2 | param str |  |
| `ai_price_suggestion` | I1 | runtime value |  |
| `aircraft_id` | S4 | runtime value |  |
| `aircraft_preference` | I1 | runtime value |  |
| `arrival_city` | F1 | (read only here) |  |
| `balance_paid_at` | S1 | ISO-8601 string |  |
| `balance_session_id` | S1 | runtime value |  |
| `billing_address` | I1 | runtime value |  |
| `booking_for` | I1 | runtime value |  |
| `booking_id` | F1 | (read only here) |  |
| `booking_number` | I2 | string |  |
| `booking_purpose` | I1 | runtime value |  |
| `booking_type` | F1 I1 | runtime value | `corporate` |
| `cancellation_approved` | S1 | bool |  |
| `cancellation_approved_at` | S1 | ISO-8601 string |  |
| `cancellation_approved_by` | S1 | runtime value |  |
| `cancellation_fee` | S1 | int, number (expr) |  |
| `cancellation_reason` | S3 F1 | string |  |
| `cancellation_request_id` | S1 | runtime value |  |
| `cancellation_requested` | S1 | bool |  |
| `cancelled_at` | F2 S1 | ISO-8601 string |  |
| `cancelled_by` | F1 | (read only here) | `operator` |
| `captured_at` | S1 | BSON Date (datetime) |  |
| `company_name` | I1 | runtime value |  |
| `completed_at` | F7 S2 | ISO-8601 string |  |
| `created_at` | F41 O13 I2 | ISO-8601 string |  |
| `customer_email` | F1 | (read only here) |  |
| `customer_id` | F16 I1 | runtime value |  |
| `customer_name` | F1 | (read only here) |  |
| `departure_city` | F1 | (read only here) |  |
| `departure_date` | F2 O1 I1 | runtime value |  |
| `destination` | F5 I1 | runtime value |  |
| `drop_landing_point_id` | F2 | (read only here) |  |
| `emergency_override` | S1 | bool |  |
| `estimated_price` | I2 F1 | runtime value |  |
| `final_price` | F1 | (read only here) |  |
| `flight_date` | F3 O1 | (read only here) |  |
| `flight_status` | S2 | string | `preparing` |
| `flight_type` | I1 | runtime value |  |
| `flight_type_details` | I1 | runtime value |  |
| `force_assigned_at` | S1 | ISO-8601 string |  |
| `force_assigned_by` | S1 | runtime value |  |
| `from_district` | I1 | runtime value |  |
| `from_latitude` | I1 | runtime value |  |
| `from_location` | I1 F1 | runtime value |  |
| `from_longitude` | I1 | runtime value |  |
| `from_pincode` | I1 | runtime value |  |
| `from_state` | I1 | runtime value |  |
| `gst_billing` | I1 | runtime value |  |
| `gstin` | I1 | runtime value |  |
| `id` | F94 I2 | UUID string |  |
| `include_insurance` | I1 | runtime value |  |
| `insurance_policy_id` | S1 | runtime value |  |
| `insurance_premium` | S1 | runtime value |  |
| `is_emergency` | F1 | (read only here) |  |
| `is_emergency_cancellation` | S1 | runtime value |  |
| `journey_completed_at` | S1 | ISO-8601 string |  |
| `journey_date` | F3 I1 O1 | runtime value |  |
| `journey_started_at` | S1 | ISO-8601 string |  |
| `journey_status` | S5 | string | `awaiting_completion_otp`, `completed`, `in_flight`, `pickup_verified`, `pilot_enroute` |
| `journey_time` | I1 | runtime value |  |
| `landing_permission_status` | S4 | string | `approved`, `documents_pending`, `rejected` |
| `landing_permissions` | I1 $push1 | array |  |
| `latest_quote` | S1 | object |  |
| `leg_number` | I1 | number (expr) |  |
| `live_flight_id` | S1 F1 | UUID string |  |
| `multi_location_stops` | I1 | runtime value |  |
| `operator_accepted_at` | S1 | ISO-8601 string |  |
| `operator_id` | F18 S7 | param str |  |
| `operator_name` | F1 | (read only here) |  |
| `origin` | F6 I1 | runtime value |  |
| `override_action` | S1 | runtime value |  |
| `override_at` | S1 | ISO-8601 string |  |
| `override_by` | S1 | runtime value |  |
| `override_reason` | S2 | runtime value |  |
| `paid_at` | S3 | **MIXED** ISO-8601 string, BSON Date (datetime) |  |
| `parent_booking_id` | S1 I1 | null |  |
| `passenger_details` | I1 S1 | runtime value |  |
| `passenger_details_filled_at` | S1 | ISO-8601 string |  |
| `passengers` | I2 | runtime value |  |
| `payment_gateway` | S1 | string | `stripe_test` |
| `payment_id` | S1 | runtime value |  |
| `payment_order_id` | S1 | runtime value |  |
| `payment_session_id` | S1 | runtime value |  |
| `payment_status` | S5 F1 | string | `captured`, `fully_paid`, `paid`, `pending` |
| `pickup_initiated_at` | S1 | ISO-8601 string |  |
| `pickup_landing_point_id` | F2 | (read only here) |  |
| `pickup_time` | I1 | runtime value |  |
| `pickup_verified_at` | S1 | ISO-8601 string |  |
| `pilot_id` | S1 F1 | runtime value |  |
| `previous_operator_id` | S2 | runtime value |  |
| `quote_accepted_at` | S1 | ISO-8601 string |  |
| `quote_ids` | I1 $push1 | array |  |
| `razorpay_payment_id` | S1 | runtime value |  |
| `reassigned_at` | S2 | ISO-8601 string |  |
| `reassigned_by` | S2 | runtime value |  |
| `reassignment_reason` | S2 | runtime value |  |
| `refund_amount` | S4 | number (expr) |  |
| `refund_approved` | S1 | bool |  |
| `refund_approved_at` | S1 | ISO-8601 string |  |
| `refund_approved_by` | S1 | runtime value |  |
| `refund_id` | S1 | runtime value |  |
| `refund_reason` | S1 | runtime value |  |
| `refund_status` | S1 | string | `processed` |
| `refunded_at` | S1 | ISO-8601 string |  |
| `region` | F3 | (read only here) |  |
| `return_date` | I1 | runtime value |  |
| `review_id` | S1 | runtime value |  |
| `reviewed` | S1 F1 | bool |  |
| `sales_person_id` | F1 | (read only here) |  |
| `settlement_id` | S1 | runtime value |  |
| `settlement_status` | F2 S1 | string | `pending`, `settled` |
| `special_requests` | I1 | runtime value |  |
| `special_requirements` | I1 | runtime value |  |
| `status` | F41 S16 I2 | string, Enum .value (string) | `boarding`, `cancelled`, `completed`, `confirmed`, `departed`, `in_progress`, `operator_assigned`, `passenger_details_filled`, `pending`, `pending_quotes`, `quote_accepted`, `quote_rejected`, `quote_requested`, `quote_sent` |
| `to_district` | I1 | runtime value |  |
| `to_latitude` | I1 | runtime value |  |
| `to_location` | I1 F1 | runtime value |  |
| `to_longitude` | I1 | runtime value |  |
| `to_pincode` | I1 | runtime value |  |
| `to_state` | I1 | runtime value |  |
| `total_amount` | S2 F2 | runtime value |  |
| `total_luggage_count` | S1 | runtime value |  |
| `total_luggage_weight` | S1 | runtime value |  |
| `total_passenger_weight` | S1 | runtime value |  |
| `trip_type` | I1 | runtime value |  |
| `type` | F1 | (read only here) | `booking_inquiry`, `inquiry` |
| `updated_at` | S14 I1 | ISO-8601 string |  |
| `user_id` | F3 | (read only here) |  |
| `village_landing_permission_id` | S1 F1 | UUID string |  |
| `zoho_invoice_id` | S1 | runtime value |  |
| `zoho_synced` | S1 F1 | bool |  |

### `users`

- **References:** 185 in 53 files. **Operations:** find_one 94, find 30, update_one 26, count_documents 22, insert_one 8, index_spec 4, lookup_from 1.
- **ID strategy:** `id` UUID string; `_id` used in filters. **Date format:** ISO string.
- **Inserts not statically resolvable:** 1 (document built at runtime).
- **Referencing modules:** `db_optimization.py`, `middleware.py`, `routes/admin_analytics_routes.py`, `routes/admin_approval_routes.py`, `routes/admin_audit_routes.py`, `routes/admin_booking_management_routes.py`, `routes/admin_document_routes.py`, `routes/admin_landing_permission_routes.py`, `routes/admin_operator_management_routes.py`, `routes/admin_payments_routes.py`, `routes/admin_routes.py`, `routes/admin_user_routes.py`, `routes/ai_advisor_routes.py`, `routes/ai_reports_routes.py`, `routes/aircraft_catalog_routes.py`, `routes/analytics_routes.py`, `routes/auction_routes.py`, `routes/auth_routes.py`, `routes/aviation_exchange_routes.py`, `routes/ceo_routes.py`, `routes/command_center_routes.py`, `routes/compliance_monitor_routes.py`, `routes/crm_routes.py`, `routes/customer_routes.py`, `routes/email_routes.py`, `routes/field_tracking_routes.py`, `routes/finance_analytics_routes.py`, `routes/finance_reconciliation_routes.py`, `routes/google_auth_routes.py`, `routes/hr_advanced_routes.py`, `routes/hr_employee_routes.py`, `routes/hr_routes.py`, `routes/journey_routes.py`, `routes/landing_infrastructure_routes.py`, `routes/loyalty_routes.py`, `routes/maintenance_routes.py`, `routes/membership_routes.py`, `routes/pilot_availability_routes.py`, `routes/predictive_analytics_routes.py`, `routes/quote_routes.py`, `routes/referral_routes.py`, `routes/search_routes.py`, `routes/sos_routes.py`, `routes/stripe_payment_routes.py`, `routes/support_routes.py`, `routes/two_factor_auth_routes.py`, `routes/voice_video_routes.py`, `scheduler.py`, `scripts/seed_demo_users.py`, `services/approval_workflow.py`, `services/login_shield_service.py`, `services/totp_service.py`, `tests/test_account_lockout.py`.
- **Indexes declared in code:** `email:1` unique=True, name='email_unique' (db_optimization.py:16); `roles:1` name='roles_idx' (db_optimization.py:17); `is_active:1` name='active_idx' (db_optimization.py:18); `created_at:-1` name='created_at_idx' (db_optimization.py:19).

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `_id` | F5 | (read only here) |  |
| `alternate_phone` | I1 | runtime value |  |
| `auth_provider` | I4 S1 | string | `emergent_google`, `google`, `google_emergent` |
| `created_at` | I7 F5 O2 | ISO-8601 string |  |
| `created_by` | I2 | runtime value |  |
| `date_of_birth` | I1 | runtime value |  |
| `department` | I2 F2 | runtime value |  |
| `designation` | I2 | runtime value |  |
| `device_info` | I3 | object |  |
| `disabled_at` | S1 | ISO-8601 string, null |  |
| `disabled_by` | S1 | null |  |
| `disabled_reason` | S1 | null |  |
| `email` | F18 I7 | string | `admin@airyatra.com`, `operator@airyatra.com`, `pilot@airyatra.com`, `testadmin@airyatra.com` |
| `email_verified` | I3 | bool |  |
| `emergent_session_token` | S1 I1 | runtime value |  |
| `employee_code` | F1 I1 | string |  |
| `first_booking_done` | S1 | bool |  |
| `first_name` | I2 | runtime value |  |
| `full_name` | I7 S1 O1 F1 | runtime value |  |
| `google_id` | I4 S1 | runtime value |  |
| `google_profile_picture` | S3 I3 | runtime value |  |
| `id` | F99 I7 | UUID string |  |
| `is_active` | F17 I4 S2 | bool |  |
| `is_premium_member` | S1 | bool |  |
| `is_role_selected` | S1 | bool |  |
| `is_verified` | I2 | bool |  |
| `joining_date` | I1 | runtime value |  |
| `last_device_info` | S4 I4 | object |  |
| `last_login` | S1 I1 | ISO-8601 string |  |
| `last_login_at` | S3 | ISO-8601 string |  |
| `last_name` | I2 | runtime value |  |
| `login_history` | $push3 I3 | array |  |
| `login_shield_enabled` | I1 | bool |  |
| `membership_id` | S1 | string |  |
| `membership_tier` | S2 | Enum .value (string) |  |
| `otp_enabled` | I1 | bool |  |
| `password_changed_at` | S1 | ISO-8601 string |  |
| `password_hash` | I3 S2 | bcrypt hash |  |
| `password_reset_at` | S1 | ISO-8601 string |  |
| `password_reset_by` | S1 | runtime value |  |
| `phone` | I4 F1 | runtime value |  |
| `photo_url` | S1 | string |  |
| `profile_picture` | I4 S2 | runtime value |  |
| `referral_applied_at` | S1 | ISO-8601 string |  |
| `referral_code_used` | S1 | string |  |
| `referred_by` | S1 | runtime value |  |
| `region` | I1 F1 | runtime value |  |
| `regions_access` | I1 | runtime value |  |
| `role` | F2 I1 | runtime value | `admin`, `sales`, `sales_manager` |
| `role_selected_at` | S1 | ISO-8601 string |  |
| `roles` | F42 I7 S1 | array | `admin`, `customer`, `employee`, `hr`, `operator`, `pilot`, `sales`, `sales_manager`, `super_admin`, `support` |
| `status` | F6 I4 S1 | string | `active`, `inactive` |
| `totp_enabled` | S2 I1 | bool |  |
| `totp_enabled_at` | S1 $unset1 | ISO-8601 string |  |
| `totp_last_used_timecode` | S2 $unset1 | runtime value |  |
| `totp_recovery_codes` | S3 $unset1 | array |  |
| `totp_recovery_codes_pending` | S1 $unset1 | array |  |
| `totp_secret` | S1 $unset1 | runtime value |  |
| `totp_secret_pending` | S1 $unset1 | runtime value |  |
| `totp_setup_started_at` | S1 $unset1 | ISO-8601 string |  |
| `two_factor_enabled` | S3 I1 | bool |  |
| `two_factor_secret` | I1 S1 | null |  |
| `updated_at` | S12 I7 | ISO-8601 string |  |
| `updated_by` | S2 | runtime value |  |

### `operators`

- **References:** 151 in 38 files. **Operations:** find_one 104, find 15, update_one 13, count_documents 10, index_spec 4, insert_one 4, distinct 1.
- **ID strategy:** `id` UUID string. **Date format:** ISO string.
- **Inserts not statically resolvable:** 1 (document built at runtime).
- **Referencing modules:** `db_optimization.py`, `routes/admin_approval_routes.py`, `routes/admin_booking_management_routes.py`, `routes/admin_document_routes.py`, `routes/admin_operator_management_routes.py`, `routes/admin_routes.py`, `routes/admin_settlement_routes.py`, `routes/aircraft_document_routes.py`, `routes/analytics_routes.py`, `routes/auth_routes.py`, `routes/booking_routes.py`, `routes/ceo_routes.py`, `routes/chat_routes.py`, `routes/customer_routes.py`, `routes/dgca_compliance_routes.py`, `routes/email_routes.py`, `routes/emergency_booking_routes.py`, `routes/feedback_routes.py`, `routes/fixed_route_pricing_routes.py`, `routes/fleet_routes.py`, `routes/inquiry_broadcast_routes.py`, `routes/landing_infrastructure_routes.py`, `routes/maintenance_routes.py`, `routes/operator_erp_routes.py`, `routes/operator_routes.py`, `routes/partner_routes.py`, `routes/pilot_document_routes.py`, `routes/pricing_engine_routes.py`, `routes/quote_routes.py`, `routes/regional_manager_routes.py`, `routes/reports_routes.py`, `routes/reviews_routes.py`, `routes/search_routes.py`, `routes/settlement_automation_routes.py`, `scheduler.py`, `scripts/seed_demo_users.py`, `services/inquiry_broadcast_service.py`, `services/settlement_service.py`.
- **Indexes declared in code:** `user_id:1` unique=True, name='user_id_unique' (db_optimization.py:44); `status:1` name='status_idx' (db_optimization.py:45); `base_city:1` name='base_city_idx' (db_optimization.py:46); `rating:-1` name='rating_idx' (db_optimization.py:47).

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `average_rating` | S1 | float |  |
| `bank_account` | I1 | runtime value |  |
| `base_city` | I2 | runtime value |  |
| `base_latitude` | I2 S1 | runtime value |  |
| `base_longitude` | I2 S1 | runtime value |  |
| `base_state` | I2 S1 | runtime value |  |
| `city` | F1 | (read only here) |  |
| `commission_rate` | S2 I2 | float |  |
| `commission_updated_at` | S1 | ISO-8601 string |  |
| `commission_updated_by` | S1 | runtime value |  |
| `company_name` | F3 I3 | number (expr) |  |
| `contact_email` | I2 F1 | runtime value |  |
| `contact_name` | I1 | runtime value |  |
| `contact_person` | I1 | runtime value |  |
| `contact_phone` | I2 F1 | runtime value |  |
| `created_at` | I3 O2 | ISO-8601 string |  |
| `documents` | I1 | array |  |
| `email` | I1 | runtime value |  |
| `gstin` | I1 | runtime value |  |
| `id` | F52 I3 | UUID string |  |
| `onboarding_approved_at` | S1 | ISO-8601 string |  |
| `onboarding_approved_by` | S1 | runtime value |  |
| `onboarding_notes` | S1 | runtime value |  |
| `previous_status` | S1 | runtime value |  |
| `rating` | S1 I1 | float |  |
| `reactivated_at` | S1 | ISO-8601 string |  |
| `reactivated_by` | S1 | runtime value |  |
| `reactivation_notes` | S1 | runtime value |  |
| `recommend_percent` | S1 | int |  |
| `region` | F4 S1 | runtime value |  |
| `region_assigned_at` | S1 | ISO-8601 string |  |
| `region_assigned_by` | S1 | runtime value |  |
| `regional_approval_notes` | S1 | param Optional[str] |  |
| `regional_approval_status` | S2 | string | `approved`, `rejected` |
| `regional_approved_at` | S1 | ISO-8601 string |  |
| `regional_approved_by` | S1 | runtime value |  |
| `regional_rejected_by` | S1 | runtime value |  |
| `regional_rejection_reason` | S1 | param str |  |
| `rejected_at` | S1 | ISO-8601 string |  |
| `rejected_by` | S1 | runtime value |  |
| `rejection_reason` | S1 | runtime value |  |
| `status` | F14 S5 I3 | string, Enum .value (string) | `active`, `pending`, `pending_verification`, `rejected`, `suspended` |
| `suspended_at` | S2 O1 | ISO-8601 string, null |  |
| `suspended_by` | S2 | null |  |
| `suspension_end_date` | S2 | null, ISO-8601 string |  |
| `suspension_reason` | S2 | null |  |
| `suspension_type` | S2 | null |  |
| `total_aircraft` | I1 | int |  |
| `total_reviews` | S2 | runtime value |  |
| `updated_at` | S10 I3 | ISO-8601 string |  |
| `user_id` | F63 I3 | UUID string |  |
| `verification_notes` | S1 | runtime value |  |
| `verification_status` | S3 F3 I2 | string, Enum .value (string) | `approved`, `pending`, `rejected`, `verified` |
| `verified_at` | S1 I1 | ISO-8601 string |  |
| `verified_by` | S1 | runtime value |  |

### `inquiries`

- **References:** 79 in 20 files. **Operations:** find 30, find_one 25, update_one 15, index_spec 5, insert_one 2, aggregate 1, count_documents 1.
- **ID strategy:** `id` UUID string. **Date format:** ISO string.
- **Referencing modules:** `db_optimization.py`, `routes/admin_operator_management_routes.py`, `routes/admin_payments_routes.py`, `routes/admin_routes.py`, `routes/booking_routes.py`, `routes/customer_routes.py`, `routes/email_routes.py`, `routes/finance_analytics_routes.py`, `routes/finance_reconciliation_routes.py`, `routes/inquiry_broadcast_routes.py`, `routes/landing_infrastructure_routes.py`, `routes/operator_routes.py`, `routes/payment_routes.py`, `routes/pricing_routes.py`, `routes/quote_routes.py`, `routes/revenue_analytics_routes.py`, `routes/search_routes.py`, `routes/stripe_payment_routes.py`, `scheduler.py`, `services/inquiry_broadcast_service.py`.
- **Indexes declared in code:** `inquiry_number:1` unique=True, name='inquiry_number_unique' (db_optimization.py:31); `customer_id:1` name='customer_idx' (db_optimization.py:32); `status:1` name='status_idx' (db_optimization.py:33); `created_at:-1` name='created_at_idx' (db_optimization.py:34); `status:1, created_at:-1` name='status_created_compound' (db_optimization.py:35).

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `accepted_operator_id` | I1 S1 | null |  |
| `accepted_quote` | I1 S1 | null, object |  |
| `accepted_quote_id` | S1 | param str |  |
| `adults_female` | I1 | runtime value |  |
| `adults_male` | I1 | runtime value |  |
| `aircraft_type` | I1 F1 | runtime value |  |
| `arrival_city` | F1 | (read only here) |  |
| `assigned_operator_id` | F1 | (read only here) |  |
| `assigned_pilot_id` | S1 $unset1 | runtime value |  |
| `assigned_pilot_name` | S1 $unset1 | runtime value |  |
| `auto_balance_reminder_amount` | S1 | number (expr) |  |
| `auto_balance_reminder_at` | S1 | ISO-8601 string |  |
| `auto_balance_reminder_sent` | S2 F1 | bool |  |
| `balance_paid_at` | S1 | ISO-8601 string |  |
| `balance_session_id` | S1 | runtime value |  |
| `booking_for` | I1 | runtime value |  |
| `booking_id` | I1 | UUID string |  |
| `booking_purpose` | I1 | runtime value |  |
| `booking_purpose_other` | I1 | runtime value |  |
| `broadcast_result` | S1 | object |  |
| `children_count` | I1 | runtime value |  |
| `created_at` | F10 O4 I2 | ISO-8601 string |  |
| `customer_email` | I1 F1 | runtime value |  |
| `customer_id` | F7 I1 | runtime value |  |
| `customer_name` | I1 F1 | runtime value |  |
| `customer_phone` | I1 | runtime value |  |
| `departure_city` | F1 | (read only here) |  |
| `departure_date` | F4 O1 I1 | runtime value |  |
| `destination` | F2 | (read only here) |  |
| `distance_km` | I1 | runtime value |  |
| `drop_district` | I1 | runtime value |  |
| `drop_latitude` | I1 | runtime value |  |
| `drop_location` | I1 | runtime value |  |
| `drop_longitude` | I1 | runtime value |  |
| `drop_pincode` | I1 | runtime value |  |
| `drop_state` | I1 | runtime value |  |
| `estimated_price` | I1 F1 | runtime value |  |
| `from_location` | F2 | (read only here) |  |
| `id` | F40 I2 | UUID string |  |
| `inquiry_number` | I1 | string |  |
| `landing_permission_status` | S4 | string | `approved`, `documents_pending`, `rejected` |
| `operator_id` | F4 I1 S1 | runtime value |  |
| `operator_responses` | I1 $push1 | array |  |
| `origin` | F2 | (read only here) |  |
| `paid_at` | S3 | ISO-8601 string |  |
| `passenger_details` | I1 S1 | array |  |
| `passenger_details_filled_at` | S1 | ISO-8601 string |  |
| `payment_gateway` | S1 | string | `stripe_test` |
| `payment_id` | S2 | runtime value |  |
| `payment_order_id` | S2 | runtime value |  |
| `payment_session_id` | S1 | runtime value |  |
| `payment_status` | F8 S4 I1 | string | `fully_paid`, `paid`, `pending` |
| `pickup_district` | I1 | runtime value |  |
| `pickup_latitude` | I1 | runtime value |  |
| `pickup_location` | I1 | runtime value |  |
| `pickup_longitude` | I1 | runtime value |  |
| `pickup_pincode` | I1 | runtime value |  |
| `pickup_state` | I1 | runtime value |  |
| `pickup_time` | I1 | runtime value |  |
| `pilot_assigned_at` | S1 $unset1 | ISO-8601 string |  |
| `price_breakdown` | I1 | runtime value |  |
| `quote_accepted_at` | S1 | ISO-8601 string |  |
| `responded_at` | F1 | (read only here) |  |
| `special_requirements` | I1 | runtime value |  |
| `status` | F13 S6 I2 | string | `assigned`, `cancelled`, `completed`, `confirmed`, `paid`, `passenger_details_filled`, `pending`, `pending_acceptance`, `pending_payment`, `quote_accepted`, `quote_received`, `quoted`, `rejected` |
| `to_location` | F2 | (read only here) |  |
| `total_amount` | S1 | runtime value |  |
| `total_luggage_count` | S1 | runtime value |  |
| `total_luggage_weight` | S1 | runtime value |  |
| `total_passenger_weight` | S1 | runtime value |  |
| `total_passengers` | I1 | runtime value |  |
| `travel_date` | F1 | (read only here) |  |
| `type` | I1 | string | `booking_inquiry` |
| `udan_prakar` | I1 | runtime value |  |
| `updated_at` | S7 F2 I1 | ISO-8601 string |  |
| `village_landing_permission_id` | S1 | UUID string |  |

### `aircraft_catalog`

- **References:** 63 in 6 files. **Operations:** count_documents 18, find 14, find_one 14, update_one 11, delete_one 3, insert_one 1, aggregate 1, update_many 1.
- **ID strategy:** `id` UUID string. **Date format:** ISO string.
- **Referencing modules:** `routes/aircraft_catalog_routes.py`, `routes/compliance_monitor_routes.py`, `routes/emergency_booking_routes.py`, `scheduler.py`, `tests/test_aircraft_and_pricing.py`, `tests/test_aircraft_catalog_smart.py`.
- **Indexes declared in code:** none.

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `archived_at` | S1 $unset1 O1 | ISO-8601 string |  |
| `archived_by` | S1 $unset1 | runtime value |  |
| `auto_hidden_at` | S4 | ISO-8601 string |  |
| `auto_hidden_reason` | S4 | string | `Document expired (automated check)`, `Document expired (automated compliance check)`, `Insurance expired`, `Maintenance overdue` |
| `availability_status` | S3 F3 I1 | string, param str | `archived`, `available`, `reserved` |
| `basic_info` | I1 S1 | object |  |
| `basic_info.aircraft_type` | F2 | (read only here) |  |
| `basic_info.registration_number` | F1 | (read only here) |  |
| `created_at` | O3 I1 | ISO-8601 string |  |
| `crew` | I1 $push1 | array |  |
| `crew_configuration` | I1 | object |  |
| `description` | I1 S1 | runtime value |  |
| `documents` | I1 S1 | object |  |
| `documents.insurance_expiry` | F7 | (read only here) |  |
| `documents.next_maintenance_due` | F7 | (read only here) |  |
| `features` | I1 S1 | object |  |
| `features.total_seats` | F1 | (read only here) |  |
| `highlights` | I1 S1 | array |  |
| `id` | F28 I1 | UUID string |  |
| `is_archived` | S2 F2 | bool |  |
| `is_published` | F14 S7 I1 | bool |  |
| `operator_email` | I1 | runtime value |  |
| `operator_id` | F5 I1 | runtime value |  |
| `photos` | I1 S1 | object |  |
| `pricing` | I1 S1 | object |  |
| `pricing.hourly_price` | F1 | (read only here) |  |
| `published_at` | I1 S1 | null, ISO-8601 string |  |
| `restored_at` | S1 | ISO-8601 string |  |
| `restored_by` | S1 | runtime value |  |
| `safety_equipment` | I1 S1 | object |  |
| `updated_at` | S8 I1 | ISO-8601 string |  |
| `verification` | I1 | object |  |
| `verification.documents_verified` | S2 | bool |  |
| `verification.last_reviewed_at` | S1 | ISO-8601 string |  |
| `verification.notes` | S2 | string | `Re-review required after update` |
| `verification.photos_verified` | S2 | bool |  |
| `verification.pricing_verified` | S1 | runtime value |  |
| `verification.reviewed_by` | S1 | runtime value |  |
| `verification.status` | F15 S2 O2 | string | `pending`, `premium_verified`, `suspended`, `under_review`, `verified` |
| `version` | I1 | string | `2.0` |

### `audit_logs`

- **References:** 59 in 22 files. **Operations:** insert_one 38, count_documents 7, find 6, aggregate 4, index_spec 3, alias 1.
- **ID strategy:** `id` UUID string. **Date format:** ISO string.
- **Referencing modules:** `db_optimization.py`, `routes/admin_approval_routes.py`, `routes/admin_audit_routes.py`, `routes/admin_booking_management_routes.py`, `routes/admin_landing_permission_routes.py`, `routes/admin_operator_management_routes.py`, `routes/admin_routes.py`, `routes/admin_settlement_routes.py`, `routes/admin_user_routes.py`, `routes/aircraft_catalog_routes.py`, `routes/auth_routes.py`, `routes/hr_routes.py`, `routes/journey_routes.py`, `routes/landing_infrastructure_routes.py`, `routes/regional_manager_routes.py`, `routes/settings_routes.py`, `routes/settlement_automation_routes.py`, `scheduler.py`, `security_middleware.py`, `services/login_shield_service.py`, `services/otp_service.py`, `services/totp_service.py`.
- **Indexes declared in code:** `user_id:1` name='user_idx' (db_optimization.py:76); `action:1` name='action_idx' (db_optimization.py:77); `created_at:-1` name='created_at_idx' (db_optimization.py:78).

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `action` | I38 F9 | string | `2fa_disabled`, `2fa_enabled`, `2fa_recovery_code_used`, `2fa_recovery_codes_regenerated`, `2fa_setup_started`, `2fa_setup_verify_failed`, `aircraft_permanent_delete`, `api_keys_update`, `approval_approved`, `auto_lead_reassignment`, `booking_reassignment`, `call_recording_settings_update`, `emergency_override`, `flight_type_pricing_update` |
| `actor` | I1 | string | `system_scheduler` |
| `category` | I6 | string | `security` |
| `changes` | I28 | object, param dict |  |
| `count` | F1 | (read only here) |  |
| `created_at` | I31 F8 O5 | ISO-8601 string |  |
| `details` | I7 | object |  |
| `entity_id` | I29 F2 | param str, string, UUID string | `api_keys`, `call_recording`, `commission_settings`, `flight_type_pricing`, `payment_rules`, `platform`, `pricing`, `settlement_scheduler` |
| `entity_type` | I30 F3 | string | `approval_request`, `booking`, `hr_settings`, `landing_permission`, `operator`, `operator_document`, `pilot`, `settings`, `settlement`, `user`, `village_landing_permission` |
| `id` | I37 | UUID string, string |  |
| `ip_address` | I1 | null |  |
| `is_critical` | I3 F1 | bool |  |
| `resource_id` | I1 | param str |  |
| `resource_type` | I1 | string | `aircraft` |
| `status` | I6 F3 | string | `failed`, `pending`, `success` |
| `timestamp` | I7 O1 | ISO-8601 string |  |
| `user_email` | F2 I1 | param str |  |
| `user_id` | I37 F6 | param str |  |
| `user_name` | I29 | runtime value |  |

### `notifications`

- **References:** 57 in 17 files. **Operations:** insert_one 25, count_documents 16, find 5, index_spec 4, update_one 4, update_many 1, delete_one 1, delete_many 1.
- **ID strategy:** `id` UUID string; `_id` set by code (string). **Date format:** MIXED (ISO 22 / Date 8).
- **Referencing modules:** `db_optimization.py`, `routes/command_center_routes.py`, `routes/content_routes.py`, `routes/emergency_booking_routes.py`, `routes/hr_advanced_routes.py`, `routes/notification_center_routes.py`, `routes/notification_routes.py`, `routes/payment_gateway_routes.py`, `routes/push_notification_routes.py`, `routes/razorpay_routes.py`, `routes/sos_routes.py`, `routes/support_routes.py`, `scheduler.py`, `services/approval_workflow.py`, `services/inquiry_broadcast_service.py`, `services/login_shield_service.py`, `tests/test_emergency_booking.py`.
- **Indexes declared in code:** `user_id:1` name='user_idx' (db_optimization.py:50); `is_read:1` name='read_idx' (db_optimization.py:51); `created_at:-1` name='created_at_idx' (db_optimization.py:52); `user_id:1, is_read:1, created_at:-1` name='user_unread_compound' (db_optimization.py:53).

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `_id` | F3 I1 | string |  |
| `action_deadline` | I1 | ISO-8601 string |  |
| `action_label` | I1 | runtime value |  |
| `action_url` | I3 | string |  |
| `body` | I1 | runtime value |  |
| `channel` | I1 | string | `in_app` |
| `created_at` | I25 O4 F1 | **MIXED** ISO-8601 string, BSON Date (datetime) |  |
| `data` | I7 | object |  |
| `data.emergency_booking_id` | F1 | (read only here) |  |
| `days_remaining` | I1 | runtime value |  |
| `details` | I1 | runtime value |  |
| `document_type` | I1 | runtime value |  |
| `for_roles` | I1 | array | `admin`, `ceo` |
| `id` | I19 F2 | UUID string, string |  |
| `is_archived` | F7 I6 S1 | bool |  |
| `is_broadcast` | I1 | bool |  |
| `is_read` | I17 F8 S2 | bool |  |
| `message` | I23 | string, param str |  |
| `metadata` | I3 | object |  |
| `notification_type` | I1 | runtime value |  |
| `pilot_id` | I1 | runtime value |  |
| `priority` | I11 F5 | string | `critical`, `high`, `normal`, `urgent` |
| `read` | I7 F2 S1 | bool |  |
| `read_at` | S3 I1 | **MIXED** BSON Date (datetime), null, ISO-8601 string |  |
| `recipient_email` | I1 | runtime value |  |
| `recipient_id` | F5 I2 | runtime value |  |
| `recipient_phone` | I1 | runtime value |  |
| `reference_id` | I10 | param str |  |
| `requires_action` | I1 | bool |  |
| `scheduled_for` | I1 | runtime value |  |
| `sent_at` | I1 F1 S1 O1 | null, ISO-8601 string |  |
| `sent_by` | I1 | runtime value |  |
| `sent_count` | I2 S1 | int |  |
| `severity` | I2 | string | `high` |
| `status` | F4 I1 S1 | string | `scheduled`, `sending`, `sent` |
| `target_user_id` | I1 | runtime value |  |
| `title` | I24 | string | `Approval Request Rejected`, `Expense Claim Approved!`, `Expense Claim Rejected`, `New Expense Claim for Approval`, `New Investor Interest!`, `New Lead Assigned / नई लीड असाइन`, `New Response to Your Emergency Request`, `Salary Credited! 💰`, `🎉 Emergency Booking Confirmed!`, `🚁 New Booking Inquiry - AirYatra` |
| `type` | I24 F7 | string | `alert`, `approval_pending`, `approval_rejected`, `emergency_booking`, `emergency_confirmed`, `emergency_response`, `expense_approval`, `expense_approved`, `expense_rejected`, `inquiry_broadcast`, `investor_interest`, `lead_assigned`, `new_ticket`, `payment` |
| `user_id` | I15 F3 | param str, string | `admin` |
| `user_role` | I1 | string | `hr` |

### `aircraft`

- **References:** 50 in 18 files. **Operations:** find 16, find_one 15, update_one 10, count_documents 7, insert_one 1, delete_one 1.
- **ID strategy:** `id` UUID string. **Date format:** ISO string.
- **Referencing modules:** `routes/admin_routes.py`, `routes/aircraft_document_routes.py`, `routes/analytics_routes.py`, `routes/ceo_routes.py`, `routes/customer_routes.py`, `routes/fixed_route_pricing_routes.py`, `routes/fleet_routes.py`, `routes/flight_record_routes.py`, `routes/inventory_routes.py`, `routes/live_tracking_routes.py`, `routes/maintenance_routes.py`, `routes/operator_erp_routes.py`, `routes/operator_routes.py`, `routes/partner_routes.py`, `routes/regional_manager_routes.py`, `routes/search_routes.py`, `scheduler.py`, `services/inquiry_broadcast_service.py`.
- **Indexes declared in code:** none.

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `aircraft_type` | I1 | runtime value |  |
| `base_location` | I1 | runtime value |  |
| `capacity` | I1 | runtime value |  |
| `created_at` | I1 | ISO-8601 string |  |
| `current_total_km` | I1 S1 | number (expr) |  |
| `documents` | $push1 $pull1 I1 | array |  |
| `engine_hours` | S2 | runtime value |  |
| `enrollment_odometer_km` | I1 | runtime value |  |
| `hourly_rate` | I1 | runtime value |  |
| `hours_since_service` | S2 | runtime value |  |
| `id` | F25 I1 | UUID string |  |
| `is_available` | F2 I1 | bool |  |
| `last_inspection_date` | S2 | runtime value |  |
| `last_known_location` | S1 | object |  |
| `last_maintenance_date` | S2 | ISO-8601 string |  |
| `last_maintenance_hours` | S1 | runtime value |  |
| `maintenance_notes` | S2 | runtime value |  |
| `maintenance_pending` | S3 | bool |  |
| `maintenance_status` | I1 S1 | string | `operational` |
| `manufacture_year` | I1 | runtime value |  |
| `manufacturer` | I1 F1 | runtime value |  |
| `model` | F1 | (read only here) |  |
| `model_name` | I1 | runtime value |  |
| `next_maintenance_date` | S2 | runtime value |  |
| `operator_id` | F14 I1 | runtime value |  |
| `registration` | F2 | (read only here) |  |
| `registration_number` | I1 | runtime value |  |
| `status` | F1 | (read only here) | `active` |
| `total_flight_hours` | I1 S1 | int, number (expr) |  |
| `total_maintenance_count` | $inc1 |  |  |
| `type` | F1 | (read only here) |  |
| `updated_at` | S5 I1 | ISO-8601 string |  |

### `payment_transactions`

- **References:** 48 in 6 files. **Operations:** find 23, find_one 9, update_one 8, insert_one 5, count_documents 2, find_one_and_update 1.
- **ID strategy:** `id` UUID string. **Date format:** MIXED (ISO 12 / Date 4).
- **Referencing modules:** `routes/admin_payments_routes.py`, `routes/finance_analytics_routes.py`, `routes/finance_reconciliation_routes.py`, `routes/payment_gateway_routes.py`, `routes/stripe_payment_routes.py`, `scheduler.py`.
- **Indexes declared in code:** none.

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `actual_utr` | S1 | runtime value |  |
| `advance_percent` | I1 | int, null |  |
| `amount` | I3 | number (expr) |  |
| `bank_name` | I1 | runtime value |  |
| `bank_reference` | S1 | runtime value |  |
| `bank_transaction_id` | I2 | runtime value |  |
| `batch_id` | I2 | UUID string |  |
| `batch_number` | I2 | string |  |
| `beneficiary_account` | I2 | runtime value |  |
| `beneficiary_ifsc` | I2 | runtime value |  |
| `beneficiary_name` | I2 | runtime value |  |
| `bill_number` | I1 | runtime value |  |
| `booking_id` | F7 I2 | runtime value |  |
| `completed_at` | S2 I1 | ISO-8601 string, null |  |
| `created_at` | F10 O3 I3 | ISO-8601 string |  |
| `created_by` | I1 | runtime value |  |
| `currency` | I2 | string | `INR`, `inr` |
| `customer_id` | I2 | runtime value |  |
| `deductions` | I1 | runtime value |  |
| `dispute_reason` | S2 | param str, string |  |
| `disputed_at` | S1 | BSON Date (datetime) |  |
| `disputed_by` | S1 | runtime value |  |
| `employee_id` | I2 | runtime value |  |
| `employee_name` | I2 | runtime value |  |
| `flagged_at` | S1 | BSON Date (datetime) |  |
| `gateway` | F4 I2 | string | `stripe_test` |
| `gross_amount` | I2 | runtime value |  |
| `id` | F11 I5 | UUID string |  |
| `initiated_at` | I2 F1 | ISO-8601 string |  |
| `initiated_by` | I2 | runtime value |  |
| `is_inquiry` | I1 | bool |  |
| `manual_match` | S1 | bool |  |
| `match_notes` | S1 | param Optional[str] |  |
| `net_amount` | I2 | runtime value |  |
| `original_amount` | I1 | float |  |
| `original_transaction_id` | I1 | param str |  |
| `payment_link_token` | I1 | param str |  |
| `payment_mode` | I2 | runtime value |  |
| `payment_status` | F15 I2 S2 | string | `expired`, `paid`, `pending` |
| `payment_type` | F2 I2 | string | `balance` |
| `reason` | I1 | runtime value |  |
| `reconciled_at` | S2 | BSON Date (datetime) |  |
| `reconciled_by` | S2 | runtime value |  |
| `reconciliation_status` | S4 F3 | string | `disputed`, `matched` |
| `reference_id` | I3 | runtime value |  |
| `reversal_id` | S1 | UUID string |  |
| `reversal_reason` | S1 | runtime value |  |
| `reversal_utr` | I1 | runtime value |  |
| `reversed_at` | S1 I1 | ISO-8601 string, null |  |
| `session_id` | F7 I2 | runtime value |  |
| `settlement_amount` | S1 | float |  |
| `settlement_id` | S2 | param str, string |  |
| `status` | F7 S5 I4 | Enum .value (string), string | `completed`, `expired`, `initiated`, `paid` |
| `tds_amount` | I1 | runtime value |  |
| `tds_rate` | I1 | runtime value |  |
| `tds_section` | I1 | runtime value |  |
| `total_amount` | I1 | runtime value |  |
| `type` | I3 | Enum .value (string) |  |
| `updated_at` | O2 F2 I2 S2 | ISO-8601 string |  |
| `utr_number` | I2 | runtime value |  |
| `vendor_id` | I1 | runtime value |  |
| `vendor_name` | I1 | runtime value |  |
| `voucher_code` | I1 | null |  |
| `voucher_discount` | I2 | int, float, number (expr) |  |

### `landing_points`

- **References:** 46 in 5 files. **Operations:** find_one 14, insert_one 8, find 8, create_index 5, index_spec 4, update_one 4, count_documents 3.
- **ID strategy:** `id` UUID string; `_id` used in filters. **Date format:** ISO string.
- **Referencing modules:** `db_optimization.py`, `routes/admin_routes.py`, `routes/landing_infrastructure_routes.py`, `scripts/seed_landing_data.py`, `services/pricing_engine.py`.
- **Indexes declared in code:** `city:1` name='city_idx' (db_optimization.py:85); `state:1` name='state_idx' (db_optimization.py:86); `is_active:1` name='active_idx' (db_optimization.py:87); `location:'2dsphere'` name='geo_idx' (db_optimization.py:88); `type:1` (scripts/seed_landing_data.py:376); `state:1` (scripts/seed_landing_data.py:377); `city:1` (scripts/seed_landing_data.py:378); `latitude:1, longitude:1` (scripts/seed_landing_data.py:379); `is_active:1` (scripts/seed_landing_data.py:380).

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `_id` | F1 | (read only here) |  |
| `address` | I1 | runtime value |  |
| `availability_calendar_required` | I36 | bool |  |
| `calendar_enabled` | I1 | bool |  |
| `category` | I37 | string | `airport` |
| `city` | I38 F4 | runtime value |  |
| `code` | I37 F1 | runtime value |  |
| `contact_email` | F2 I1 | runtime value |  |
| `contact_name` | I1 | runtime value |  |
| `contact_phone` | I1 | runtime value |  |
| `created_at` | I38 | ISO-8601 string |  |
| `created_by` | I2 | runtime value |  |
| `deleted_at` | S1 | ISO-8601 string |  |
| `deleted_by` | S1 | runtime value |  |
| `district` | I37 | runtime value |  |
| `facilities` | I7 | runtime value |  |
| `fuel_available` | I1 | runtime value |  |
| `helipad_size_m` | I1 | runtime value |  |
| `icao_code` | I8 | runtime value |  |
| `id` | I38 F17 | UUID string |  |
| `is_active` | I38 F7 S1 | bool |  |
| `is_verified` | I37 | bool |  |
| `landing_point_id` | I1 F1 | UUID string |  |
| `landing_point_name` | I1 | runtime value |  |
| `landing_point_type` | I1 | runtime value |  |
| `latitude` | I38 | runtime value |  |
| `lighting_available` | I1 | runtime value |  |
| `longitude` | I38 | runtime value |  |
| `name` | I38 F2 | runtime value |  |
| `night_operations` | I1 | runtime value |  |
| `notes` | I1 | runtime value |  |
| `operating_hours` | I1 | runtime value |  |
| `owner_id` | I1 F1 | runtime value |  |
| `owner_type` | I37 | string | `government` |
| `permission_required` | I38 | bool |  |
| `pincode` | I1 | runtime value |  |
| `rent` | I1 | runtime value |  |
| `rent_applicable` | I38 S1 F1 | bool |  |
| `rent_config_id` | S1 | UUID string |  |
| `rent_per_landing` | I1 S1 | runtime value |  |
| `runway_length` | I1 | runtime value |  |
| `state` | I38 F7 | runtime value |  |
| `status` | I2 | string | `active` |
| `surface_type` | I1 | runtime value |  |
| `type` | I38 F10 | string | `airport`, `govt_helipad`, `private_helipad` |
| `updated_at` | I38 S2 | ISO-8601 string |  |
| `updated_by` | S1 | runtime value |  |

### `documents_vault`

- **References:** 44 in 2 files. **Operations:** count_documents 10, find_one 9, find 7, update_one 7, update_many 4, aggregate 4, insert_one 1, delete_one 1, delete_many 1.
- **ID strategy:** `id` custom string. **Date format:** BSON Date.
- **Referencing modules:** `routes/admin_document_routes.py`, `routes/document_vault_routes.py`.
- **Indexes declared in code:** none.

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `archived_at` | S2 | BSON Date (datetime) |  |
| `category` | F3 I1 | param str |  |
| `created_at` | O5 F1 I1 | BSON Date (datetime) |  |
| `description` | F2 I1 | param Optional[str] |  |
| `document_id` | F18 I1 | string |  |
| `document_type` | F2 I1 | param str |  |
| `download_count` | I1 $inc1 | int |  |
| `expiry_date` | F4 O2 I1 | BSON Date (datetime), null |  |
| `file_hash` | I1 | string |  |
| `file_id` | F4 I1 S1 | string |  |
| `file_name` | I1 S1 | runtime value |  |
| `file_size` | I1 S1 | int |  |
| `file_type` | F2 I1 | string |  |
| `file_url` | I1 S1 | string |  |
| `folder_id` | F3 I1 S1 | param Optional[str] |  |
| `id` | I1 | string |  |
| `is_sensitive` | I1 | param bool |  |
| `issued_by` | I1 | param Optional[str] |  |
| `issued_date` | I1 | BSON Date (datetime), null |  |
| `last_accessed` | S2 I1 | BSON Date (datetime), null |  |
| `name` | F2 I1 | param str |  |
| `owner_id` | F18 I1 | param str |  |
| `owner_type` | I1 | param str |  |
| `reference_number` | F2 I1 | param Optional[str] |  |
| `reminder_days` | I1 | param int |  |
| `shared_with` | I1 $push1 | array |  |
| `status` | F6 S3 I1 | string | `archived` |
| `storage_path` | I1 | null, string |  |
| `storage_type` | I1 | string |  |
| `tags` | F2 I1 $addToSet1 | array |  |
| `thumb_storage_path` | I1 | null, string |  |
| `thumbnail_url` | I1 | null, string |  |
| `updated_at` | S4 I1 | BSON Date (datetime) |  |
| `verification_notes` | S2 | param Optional[str] |  |
| `verification_status` | F4 S2 I1 | param str, string | `pending`, `rejected`, `verified` |
| `verified_at` | S2 I1 | BSON Date (datetime), null |  |
| `verified_by` | S2 I1 | null |  |
| `version` | I1 S1 | int, number (expr) |  |
| `versions_history` | I1 $push1 | array |  |

### `pilots`

- **References:** 44 in 16 files. **Operations:** find_one 17, find 13, count_documents 6, update_one 6, insert_one 1, delete_one 1.
- **ID strategy:** `id` UUID string. **Date format:** ISO string.
- **Referencing modules:** `routes/admin_analytics_routes.py`, `routes/admin_routes.py`, `routes/ai_advisor_routes.py`, `routes/customer_routes.py`, `routes/dgca_compliance_routes.py`, `routes/flight_record_routes.py`, `routes/journey_routes.py`, `routes/maintenance_routes.py`, `routes/operator_erp_routes.py`, `routes/operator_routes.py`, `routes/pilot_document_routes.py`, `routes/pilot_mobile_routes.py`, `routes/regional_manager_routes.py`, `routes/reports_routes.py`, `routes/search_routes.py`, `scheduler.py`.
- **Indexes declared in code:** none.

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `created_at` | I1 | ISO-8601 string |  |
| `documents` | I1 $push1 $pull1 | array |  |
| `documents_updated_at` | S1 | ISO-8601 string |  |
| `email` | I1 | runtime value |  |
| `experience_years` | I1 | runtime value |  |
| `full_name` | I1 | runtime value |  |
| `id` | F22 I1 | UUID string |  |
| `is_available` | I1 | bool |  |
| `is_restricted` | S1 F1 | runtime value |  |
| `license_expiry` | S1 | param str |  |
| `license_number` | S1 I1 F1 | param str |  |
| `medical_expiry` | S1 | param str |  |
| `name` | F1 | (read only here) |  |
| `operator_id` | F13 I1 | runtime value |  |
| `phone` | I1 F1 | runtime value |  |
| `restricted_at` | S1 | ISO-8601 string |  |
| `restricted_by` | S1 | runtime value |  |
| `restriction_reason` | S1 | runtime value |  |
| `restriction_until` | S1 | ISO-8601 string, null |  |
| `total_flight_hours` | $inc1 |  |  |
| `type_rating_expiry` | S1 | param str |  |
| `updated_at` | I1 S1 | ISO-8601 string |  |
| `user_id` | F2 | (read only here) |  |

### `crm_leads`

- **References:** 38 in 4 files. **Operations:** count_documents 12, update_one 7, index_spec 5, find 5, find_one 5, insert_one 2, aggregate 2.
- **ID strategy:** `id` UUID string. **Date format:** ISO string.
- **Referencing modules:** `db_optimization.py`, `routes/crm_routes.py`, `routes/hr_routes.py`, `scheduler.py`.
- **Indexes declared in code:** `status:1` name='status_idx' (db_optimization.py:56); `source:1` name='source_idx' (db_optimization.py:57); `assigned_to:1` name='assigned_idx' (db_optimization.py:58); `created_at:-1` name='created_at_idx' (db_optimization.py:59); `priority:1, created_at:-1` name='priority_created_compound' (db_optimization.py:60).

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `address` | I1 | runtime value |  |
| `alternate_phone` | I1 | runtime value |  |
| `assigned_at` | I2 S2 F1 | ISO-8601 string, null |  |
| `assigned_to` | F9 S3 I2 | runtime value |  |
| `assigned_to_name` | S1 | runtime value |  |
| `assignment_deadline` | I2 S2 | ISO-8601 string, null |  |
| `budget_range` | I1 | runtime value |  |
| `city` | I2 | runtime value |  |
| `company_name` | I2 F2 | runtime value |  |
| `converted_at` | F2 I1 S1 | null, ISO-8601 string |  |
| `converted_by` | I1 S1 | null |  |
| `converted_to_customer_id` | I1 S1 | null, UUID string |  |
| `created_at` | F9 I2 O2 | ISO-8601 string |  |
| `created_by` | I2 | string | `webhook` |
| `designation` | I1 | runtime value |  |
| `email` | I2 F2 | runtime value |  |
| `follow_up_notes` | I1 $push1 | array |  |
| `id` | F11 I2 | UUID string |  |
| `is_converted` | I2 F2 S1 | bool |  |
| `last_activity_at` | S3 I2 | ISO-8601 string |  |
| `last_contacted_at` | F1 | (read only here) |  |
| `lead_number` | I2 F2 | string |  |
| `name` | I2 F2 | string |  |
| `next_follow_up` | I1 | runtime value |  |
| `notes` | I1 | runtime value |  |
| `passengers` | I1 | runtime value |  |
| `phone` | I2 F2 | runtime value |  |
| `previous_assignee` | S1 | runtime value |  |
| `priority` | I2 F2 | Enum .value (string) |  |
| `reassigned_at` | S1 | ISO-8601 string |  |
| `reassignment_count` | I2 $inc2 F1 | int |  |
| `reassignment_reason` | S1 | string | `auto_stale_1hr` |
| `requirements` | I2 | runtime value |  |
| `route_from` | I1 | runtime value |  |
| `route_to` | I1 | runtime value |  |
| `service_interested` | I1 | runtime value |  |
| `source` | I2 F2 | runtime value |  |
| `source_details` | I2 | object |  |
| `state` | I2 | runtime value |  |
| `status` | F10 S3 I2 | Enum .value (string), null | `contacted`, `follow_up`, `negotiation`, `new`, `proposal_sent`, `qualified`, `won` |
| `tags` | I2 | array |  |
| `total_calls` | I2 $inc1 | int |  |
| `total_emails` | I2 | int |  |
| `travel_date` | I1 | runtime value |  |
| `updated_at` | S3 I2 | ISO-8601 string |  |

### `approval_requests`

- **References:** 29 in 6 files. **Operations:** find_one 10, update_one 9, find 6, insert_one 2, count_documents 2.
- **ID strategy:** `id` UUID string. **Date format:** ISO string.
- **Referencing modules:** `routes/admin_approval_routes.py`, `routes/admin_booking_management_routes.py`, `routes/ai_advisor_routes.py`, `routes/command_center_routes.py`, `routes/payment_gateway_routes.py`, `services/approval_workflow.py`.
- **Indexes declared in code:** none.

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `admin_approval` | S2 I1 | object, null |  |
| `amount` | I1 | param float |  |
| `approval_chain` | $push2 |  |  |
| `approval_level` | S2 I1 | number (expr), int |  |
| `booking_id` | F1 I1 | param str |  |
| `completed_at` | S5 I1 | ISO-8601 string, null |  |
| `created_at` | O6 I2 | ISO-8601 string |  |
| `current_status` | I1 | runtime value |  |
| `details` | I1 | param Dict[str, Any] |  |
| `entity_id` | F1 | (read only here) |  |
| `escalate_to` | S1 | runtime value |  |
| `escalated` | S1 | bool |  |
| `escalated_at` | S1 | ISO-8601 string |  |
| `escalated_by` | S1 | runtime value |  |
| `escalation_reason` | S1 | runtime value |  |
| `final_approved_at` | S1 | ISO-8601 string |  |
| `final_approved_by` | S1 | runtime value |  |
| `final_approved_by_name` | S1 | runtime value |  |
| `final_remark` | S1 | runtime value |  |
| `finance_approval` | I1 S1 | null, object |  |
| `hr_approval` | I1 S1 | null, object |  |
| `id` | F19 I2 | UUID string |  |
| `notes` | $push5 I1 | array |  |
| `operator_id` | F1 | (read only here) |  |
| `reason` | I1 | runtime value |  |
| `reference_id` | I1 | param str |  |
| `refund_amount` | I1 | runtime value |  |
| `region` | F1 | (read only here) |  |
| `rejected_at` | S1 | ISO-8601 string |  |
| `rejected_by` | S1 | runtime value |  |
| `rejected_by_name` | S1 | runtime value |  |
| `rejection` | S1 | object |  |
| `rejection_remark` | S1 | runtime value |  |
| `request_number` | I1 | string |  |
| `request_type` | F2 I1 | string | `cancellation`, `payout`, `refund`, `settlement` |
| `requested_by` | I1 | runtime value |  |
| `requested_by_name` | I1 | runtime value |  |
| `requestor_id` | I1 | param str |  |
| `requestor_name` | I1 | param str |  |
| `requires_admin` | I1 | param bool |  |
| `requires_finance` | I1 | param bool |  |
| `requires_hr` | I1 | param bool |  |
| `settlement_id` | F1 | (read only here) |  |
| `status` | F8 S7 I2 | Enum .value (string), string | `approved`, `pending`, `pending_admin`, `pending_finance`, `pending_hr`, `rejected` |
| `type` | I1 F1 | Enum .value (string), param ApprovalType |  |
| `updated_at` | S9 I1 | ISO-8601 string |  |

### `auctions`

- **References:** 28 in 2 files. **Operations:** find_one 8, count_documents 8, update_one 6, find 5, insert_one 1.
- **ID strategy:** `id` UUID string. **Date format:** ISO string.
- **Referencing modules:** `routes/auction_routes.py`, `routes/price_breakup_routes.py`.
- **Indexes declared in code:** none.

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `aircraft_category` | I1 F1 | runtime value |  |
| `auction_duration_minutes` | I1 | runtime value |  |
| `auction_number` | I1 | string |  |
| `cancelled_at` | S1 | ISO-8601 string |  |
| `cancelled_by` | S1 | runtime value |  |
| `contact_email` | I1 | runtime value |  |
| `contact_name` | I1 | runtime value |  |
| `contact_phone` | I1 | runtime value |  |
| `created_at` | O3 I1 | ISO-8601 string |  |
| `customer_email` | I1 | runtime value |  |
| `customer_id` | F3 I1 | runtime value |  |
| `customer_name` | I1 | runtime value |  |
| `destination` | F1 I1 | runtime value |  |
| `destination_type` | I1 | runtime value |  |
| `end_time` | I1 O1 F1 | ISO-8601 string |  |
| `expired_at` | S1 | ISO-8601 string |  |
| `flight_type` | I1 | runtime value |  |
| `id` | F13 I1 | UUID string |  |
| `luggage_kg` | I1 | runtime value |  |
| `max_budget` | I1 | runtime value |  |
| `mode` | I1 | string | `reverse_auction` |
| `notification_sent_at` | S1 | ISO-8601 string |  |
| `operators_notified` | S1 I1 | int |  |
| `origin` | F1 I1 | runtime value |  |
| `origin_type` | I1 | runtime value |  |
| `passengers` | I1 | runtime value |  |
| `preferred_aircraft` | I1 | runtime value |  |
| `purpose` | I1 | runtime value |  |
| `quotes_count` | $inc2 I1 | int |  |
| `return_date` | I1 | runtime value |  |
| `selected_at` | S1 | ISO-8601 string |  |
| `selected_quote_id` | I1 S1 | null |  |
| `selection_notes` | S1 | runtime value |  |
| `special_requirements` | I1 | runtime value |  |
| `start_time` | I1 | ISO-8601 string |  |
| `status` | F12 S3 I1 | runtime value | `active`, `cancelled`, `closed`, `confirmed`, `expired`, `quote_selected` |
| `travel_date` | F1 I1 | runtime value |  |
| `travel_time` | I1 | runtime value |  |
| `version` | I1 | string | `1.0` |

### `user_sessions`

- **References:** 28 in 5 files. **Operations:** update_one 8, insert_one 6, find 6, find_one 5, count_documents 2, alias 1.
- **ID strategy:** `id` custom string; `_id` used in filters. **Date format:** MIXED (ISO 4 / Date 15).
- **Referencing modules:** `routes/auth_routes.py`, `routes/google_auth_routes.py`, `security_middleware.py`, `services/login_shield_service.py`, `services/otp_service.py`.
- **Indexes declared in code:** none.

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `_id` | F3 | (read only here) |  |
| `action` | I1 F1 | param str |  |
| `auth_method` | I1 | string | `totp_2fa` |
| `auth_provider` | I1 | string | `google_emergent` |
| `category` | I1 F1 | param str |  |
| `client` | I1 | object |  |
| `created_at` | I5 S1 F1 | **MIXED** BSON Date (datetime), ISO-8601 string |  |
| `date` | I1 | strftime string |  |
| `details` | I1 | object |  |
| `device_hash` | F3 I3 | null |  |
| `device_info` | I1 | object |  |
| `device_trusted` | I1 | runtime value |  |
| `emergent_session_token` | I1 | runtime value |  |
| `expires_at` | I5 S1 | **MIXED** BSON Date (datetime), ISO-8601 string, param datetime |  |
| `hour` | I1 | runtime value |  |
| `id` | F3 I2 | string |  |
| `ip_address` | I5 F2 | string, param str, null |  |
| `is_active` | F8 S6 I4 | bool |  |
| `jwt_token` | S1 | runtime value |  |
| `last_activity` | I4 O2 S1 | BSON Date (datetime) |  |
| `resource` | I1 | object |  |
| `revoke_reason` | S6 | string, param str | `logout`, `logout_all`, `password_change`, `user_requested` |
| `revoked_at` | S6 | BSON Date (datetime) |  |
| `risk_level` | I1 F1 | param str |  |
| `session_token` | I1 S1 | runtime value |  |
| `status` | I1 | param str |  |
| `timestamp` | F2 I1 O1 | BSON Date (datetime) |  |
| `token_hash` | I4 F3 | param str |  |
| `user` | I1 | object |  |
| `user.id` | F1 | (read only here) |  |
| `user_agent` | I4 | null |  |
| `user_id` | F14 I5 S1 | param str, UUID string |  |

### `vendor_bills`

- **References:** 28 in 6 files. **Operations:** find 16, update_one 6, count_documents 3, find_one 2, insert_one 1.
- **ID strategy:** `id` UUID string. **Date format:** MIXED (ISO 4 / Date 1).
- **Referencing modules:** `routes/finance_advanced_routes.py`, `routes/finance_phase4_routes.py`, `routes/finance_phase5_routes.py`, `routes/finance_treasury_routes.py`, `routes/gst_routes.py`, `routes/payment_gateway_routes.py`.
- **Indexes declared in code:** none.

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `approved_at` | S2 I1 | **MIXED** BSON Date (datetime), null, ISO-8601 string |  |
| `approved_by` | I1 S1 | null |  |
| `bill_number` | I1 | string |  |
| `category` | F1 I1 | runtime value |  |
| `created_at` | O2 I1 | ISO-8601 string |  |
| `created_by` | I1 | runtime value |  |
| `description` | I1 | runtime value |  |
| `due_date` | F1 I1 | runtime value |  |
| `gross_amount` | I1 | float |  |
| `gst_amount` | I1 | runtime value |  |
| `gst_applicable` | F3 | (read only here) |  |
| `gstr2a_matched` | S1 F1 | bool |  |
| `gstr2a_reconciled_at` | S1 | ISO-8601 string |  |
| `id` | F10 I1 | UUID string |  |
| `invoice_date` | I1 | runtime value |  |
| `invoice_number` | I1 | runtime value |  |
| `itc_eligible` | F1 | (read only here) |  |
| `items` | I1 | runtime value |  |
| `month` | F5 | (read only here) |  |
| `net_payable` | I1 | number (expr) |  |
| `paid_at` | S1 | ISO-8601 string |  |
| `payment_batch_id` | S1 | UUID string |  |
| `payment_gateway` | S1 | runtime value |  |
| `payment_mode` | S1 | runtime value |  |
| `payment_reference` | S1 | runtime value |  |
| `payment_status` | F10 S4 I1 | string | `approved`, `paid`, `pending`, `processing`, `unpaid` |
| `payment_transaction_id` | S1 | UUID string |  |
| `status` | F5 S2 I1 | string | `approved`, `paid`, `pending` |
| `tds_amount` | I1 | float, int |  |
| `tds_applicable` | F1 I1 | bool |  |
| `tds_deposited` | F1 | (read only here) |  |
| `tds_rate` | I1 | runtime value |  |
| `tds_section` | I1 | runtime value |  |
| `utr_number` | S1 | runtime value |  |
| `vendor_code` | I1 | runtime value |  |
| `vendor_id` | F2 I1 | runtime value |  |
| `vendor_name` | I1 | runtime value |  |
| `year` | F5 | (read only here) |  |

### `quotes`

- **References:** 27 in 11 files. **Operations:** find 9, find_one 5, index_spec 4, update_one 4, insert_one 3, update_many 1, count_documents 1.
- **ID strategy:** `id` UUID string. **Date format:** ISO string.
- **Referencing modules:** `db_optimization.py`, `routes/admin_routes.py`, `routes/booking_routes.py`, `routes/ceo_routes.py`, `routes/customer_routes.py`, `routes/inquiry_broadcast_routes.py`, `routes/multileg_booking_routes.py`, `routes/operator_erp_routes.py`, `routes/operator_routes.py`, `routes/quote_routes.py`, `routes/reports_routes.py`.
- **Indexes declared in code:** `inquiry_id:1` name='inquiry_idx' (db_optimization.py:38); `operator_id:1` name='operator_idx' (db_optimization.py:39); `status:1` name='status_idx' (db_optimization.py:40); `created_at:-1` name='created_at_idx' (db_optimization.py:41).

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `accepted_at` | S1 | ISO-8601 string |  |
| `aircraft_id` | I1 | runtime value |  |
| `amount` | I2 S1 | float |  |
| `booking_id` | F10 I3 S1 | runtime value |  |
| `breakdown` | S1 I1 | runtime value |  |
| `created_at` | I3 F3 S1 | ISO-8601 string |  |
| `customer_feedback` | S1 | runtime value |  |
| `customer_id` | S1 I1 | runtime value |  |
| `destination` | F1 | (read only here) |  |
| `expires_at` | I1 | ISO-8601 string |  |
| `id` | F7 I3 S1 | UUID string |  |
| `inquiry_id` | F4 I1 | runtime value |  |
| `is_accepted` | S1 I1 | bool |  |
| `notes` | I2 S1 | runtime value |  |
| `operator_id` | F5 I3 S1 | runtime value |  |
| `operator_name` | I2 S1 | runtime value |  |
| `origin` | F1 | (read only here) |  |
| `original_amount` | I1 | int |  |
| `quoted_price` | I1 | runtime value |  |
| `rejected_at` | S1 | ISO-8601 string |  |
| `rejection_feedback` | S1 | runtime value |  |
| `revision_count` | I2 S1 | int, number (expr) |  |
| `special_notes` | I1 | runtime value |  |
| `status` | S4 F3 I2 | string | `accepted`, `approved`, `converted`, `pending`, `rejected`, `rejected_by_customer`, `sent` |
| `updated_at` | O3 I2 S1 | ISO-8601 string |  |
| `valid_until` | S1 I1 | ISO-8601 string |  |
| `validity_hours` | I2 S1 | runtime value |  |

### `call_logs`

- **References:** 26 in 3 files. **Operations:** update_one 7, count_documents 6, index_spec 3, aggregate 3, find 3, find_one 2, insert_one 2.
- **ID strategy:** `id` UUID string. **Date format:** ISO string.
- **Referencing modules:** `db_optimization.py`, `routes/twilio_routes.py`, `routes/voice_video_routes.py`.
- **Indexes declared in code:** `call_sid:1` unique=True, name='call_sid_unique' (db_optimization.py:63); `customer_id:1` name='customer_idx' (db_optimization.py:64); `created_at:-1` name='created_at_idx' (db_optimization.py:65).

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `answered_at` | I1 S1 | null |  |
| `booking_id` | I2 | runtime value |  |
| `call_sid` | F5 I1 | string |  |
| `call_type` | F2 I2 | runtime value |  |
| `callee_id` | F3 I1 | runtime value |  |
| `callee_name` | I1 | runtime value |  |
| `caller_id` | F3 I1 | runtime value |  |
| `caller_name` | I1 | runtime value |  |
| `created_at` | O2 F1 I1 | ISO-8601 string |  |
| `customer_id` | I1 | runtime value |  |
| `duration` | I1 S1 | int |  |
| `duration_seconds` | I1 S1 | int |  |
| `end_reason` | S3 I1 | string, null | `busy`, `rejected` |
| `ended_at` | S3 I1 | null |  |
| `from_number` | I1 | string |  |
| `id` | F4 I2 | UUID string |  |
| `initiated_at` | F2 I1 O1 | ISO-8601 string |  |
| `initiated_by` | I1 | runtime value |  |
| `notes` | S1 | param str |  |
| `notes_at` | S1 | ISO-8601 string |  |
| `notes_by` | S1 | runtime value |  |
| `recording_duration` | S1 | int |  |
| `recording_enabled` | I1 | runtime value |  |
| `recording_sid` | S1 | runtime value |  |
| `recording_url` | S1 F1 | runtime value |  |
| `status` | S5 F3 I2 | string | `busy`, `connected`, `ended`, `initiated`, `rejected`, `ringing` |
| `subject` | I1 | runtime value |  |
| `to_number` | I1 | runtime value |  |
| `updated_at` | S2 | ISO-8601 string |  |

### `settings`

- **References:** 26 in 8 files. **Operations:** find_one 19, update_one 7.
- **ID strategy:** `_id` ObjectId only (ASSUMPTION). **Date format:** ISO string.
- **Referencing modules:** `routes/admin_routes.py`, `routes/google_auth_routes.py`, `routes/inquiry_broadcast_routes.py`, `routes/invoice_routes.py`, `routes/loyalty_routes.py`, `routes/pricing_routes.py`, `routes/support_routes.py`, `services/inquiry_broadcast_service.py`.
- **Indexes declared in code:** none.

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `auto_expire_minutes` | S1 | runtime value |  |
| `broadcast_radius_km` | S1 | runtime value |  |
| `default_operator_rate` | S1 | float |  |
| `enabled` | S1 | runtime value |  |
| `festival_dates` | $push1 |  |  |
| `gst_rate` | S1 | float |  |
| `in_app_enabled` | S1 | runtime value |  |
| `max_operators_per_inquiry` | S1 | runtime value |  |
| `platform_fee` | S1 | float |  |
| `tiers` | S1 | param List[dict] |  |
| `type` | F26 S6 | string | `api_keys`, `commission_settings`, `google_auth`, `inquiry_broadcast`, `invoice_settings`, `loyalty_tiers`, `pricing_config`, `sla_config` |
| `updated_at` | S6 | ISO-8601 string |  |
| `updated_by` | S4 | runtime value |  |
| `whatsapp_enabled` | S1 | runtime value |  |

### `auction_quotes`

- **References:** 25 in 2 files. **Operations:** find_one 7, count_documents 6, find 4, update_one 3, update_many 3, insert_one 1, aggregate 1.
- **ID strategy:** `id` UUID string. **Date format:** ISO string.
- **Referencing modules:** `routes/auction_routes.py`, `routes/price_breakup_routes.py`.
- **Indexes declared in code:** none.

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `aircraft_id` | I1 S1 | runtime value |  |
| `aircraft_model` | I1 S1 | runtime value |  |
| `aircraft_registration` | I1 S1 | runtime value |  |
| `aircraft_type` | I1 S1 | runtime value |  |
| `auction_id` | F15 I1 | param str |  |
| `base_price` | I1 S1 | runtime value |  |
| `created_at` | I1 O1 | ISO-8601 string |  |
| `crew_charges` | I1 S1 | runtime value |  |
| `departure_time` | I1 S1 | runtime value |  |
| `discount` | I1 S1 | runtime value |  |
| `estimated_flight_time` | I1 S1 | runtime value |  |
| `expired_at` | S2 | ISO-8601 string |  |
| `fuel_surcharge` | I1 S1 | runtime value |  |
| `gst_amount` | I1 S1 | float |  |
| `gst_rate` | I1 | int |  |
| `handling_charges` | I1 S1 | runtime value |  |
| `id` | F7 I1 | UUID string |  |
| `landing_charges` | I1 S1 | runtime value |  |
| `operator_email` | I1 | runtime value |  |
| `operator_id` | F6 I1 | runtime value |  |
| `operator_name` | I1 | runtime value |  |
| `operator_notes` | I1 S1 | runtime value |  |
| `other_charges` | I1 S1 | runtime value |  |
| `quote_valid_hours` | I1 S1 | runtime value |  |
| `quote_valid_until` | I1 S1 | ISO-8601 string |  |
| `rejected_at` | S1 | ISO-8601 string |  |
| `selected_at` | S1 | ISO-8601 string |  |
| `status` | S5 F5 I1 | runtime value | `pending`, `selected`, `withdrawn` |
| `subtotal` | I1 S1 | float |  |
| `terms_conditions` | I1 S1 | runtime value |  |
| `total_amount` | O2 I1 S1 | float |  |
| `updated_at` | I1 S1 | ISO-8601 string |  |
| `withdrawn_at` | S1 | ISO-8601 string |  |

### `invoices`

- **References:** 23 in 5 files. **Operations:** find 9, find_one 4, count_documents 3, aggregate 3, insert_one 2, update_one 2.
- **ID strategy:** `id` UUID string. **Date format:** MIXED (ISO 7 / Date 1).
- **Referencing modules:** `routes/accounting_routes.py`, `routes/finance_phase5_routes.py`, `routes/gst_routes.py`, `routes/invoice_routes.py`, `routes/search_routes.py`.
- **Indexes declared in code:** none.

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `amount_due` | S2 I1 | int, number (expr) |  |
| `amount_paid` | S2 I1 | int, number (expr) |  |
| `billing_address` | I1 | runtime value |  |
| `booking_id` | I1 | runtime value |  |
| `company_address` | I1 | runtime value |  |
| `company_gstin` | I1 | runtime value |  |
| `company_name` | I1 | runtime value |  |
| `company_pan` | I1 | runtime value |  |
| `created_at` | I2 O2 | **MIXED** BSON Date (datetime), ISO-8601 string |  |
| `created_by` | I1 | runtime value |  |
| `customer_address` | I1 | runtime value |  |
| `customer_email` | I1 F1 | runtime value |  |
| `customer_gstin` | I1 | runtime value |  |
| `customer_id` | F2 I1 | runtime value |  |
| `customer_name` | I2 F1 | runtime value |  |
| `customer_phone` | I1 | runtime value |  |
| `due_date` | I1 F1 | ISO-8601 string |  |
| `gst_amount` | I1 | runtime value |  |
| `id` | F7 I1 | UUID string |  |
| `invoice_date` | F6 I1 | ISO-8601 string |  |
| `invoice_number` | I2 F1 | string |  |
| `invoice_type` | F7 I1 | runtime value | `tax_invoice` |
| `items` | I1 | array |  |
| `month` | F4 | (read only here) |  |
| `notes` | I1 | runtime value |  |
| `paid_at` | S1 | ISO-8601 string |  |
| `payment_status` | F3 S2 I1 | string | `paid`, `unpaid` |
| `status` | F2 S2 I1 | string, param str | `draft`, `paid` |
| `total` | I1 | runtime value |  |
| `updated_at` | S2 I1 | ISO-8601 string |  |
| `year` | F4 | (read only here) |  |

### `pilot_documents`

- **References:** 23 in 4 files. **Operations:** find_one 7, find 6, insert_one 3, delete_one 3, update_one 3, count_documents 1.
- **ID strategy:** `id` UUID string. **Date format:** ISO string.
- **Referencing modules:** `routes/admin_routes.py`, `routes/maintenance_routes.py`, `routes/pilot_document_routes.py`, `routes/pilot_mobile_routes.py`.
- **Indexes declared in code:** none.

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `ai_verification` | S1 | runtime value |  |
| `confirmed_at` | S1 | ISO-8601 string |  |
| `content_type` | I1 | runtime value |  |
| `created_at` | I2 | ISO-8601 string |  |
| `days_until_expiry` | I1 | null |  |
| `document_number` | I2 F1 | param str |  |
| `document_type` | I3 F1 | param str, string |  |
| `expiry_date` | I3 F2 S1 | ISO-8601 string, param str |  |
| `file_data` | I2 S1 | string |  |
| `file_name` | I3 S1 | runtime value |  |
| `file_size` | I3 S1 | int |  |
| `file_type` | I2 S1 | runtime value |  |
| `id` | F13 I3 | UUID string, string |  |
| `issue_date` | I2 | param str |  |
| `issuer` | S1 I1 | param Optional[str] |  |
| `issuing_authority` | I1 | param str |  |
| `notes` | I2 S1 | param Optional[str], param str |  |
| `operator_id` | I2 F2 | runtime value |  |
| `pilot_id` | F8 I3 | param str, string |  |
| `pilot_name` | I1 | runtime value |  |
| `s3_key` | I1 | runtime value |  |
| `status` | F3 I1 S1 | string | `completed`, `uploading` |
| `updated_at` | S1 | ISO-8601 string |  |
| `uploaded_at` | I2 O1 S1 | ISO-8601 string |  |
| `uploaded_by` | I1 | runtime value |  |
| `verification_notes` | I1 | array |  |
| `verification_status` | I2 F1 S1 | string | `expired`, `expiring_soon`, `pending` |

### `support_tickets`

- **References:** 23 in 2 files. **Operations:** index_spec 6, count_documents 5, find_one 3, update_one 3, find 3, aggregate 2, insert_one 1.
- **ID strategy:** `id` UUID string. **Date format:** ISO string.
- **Referencing modules:** `db_optimization.py`, `routes/support_routes.py`.
- **Indexes declared in code:** `ticket_number:1` unique=True, name='ticket_number_unique' (db_optimization.py:68); `customer_id:1` name='customer_idx' (db_optimization.py:69); `status:1` name='status_idx' (db_optimization.py:70); `priority:1` name='priority_idx' (db_optimization.py:71); `assigned_to:1` name='assigned_idx' (db_optimization.py:72); `created_at:-1` name='created_at_idx' (db_optimization.py:73).

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `assigned_name` | I1 S1 | null |  |
| `assigned_to` | F4 I1 S1 | null |  |
| `attachments` | I1 | runtime value |  |
| `booking_id` | I1 | runtime value |  |
| `category` | F2 I1 | runtime value |  |
| `created_at` | O2 I1 F1 | ISO-8601 string |  |
| `customer_email` | I1 | runtime value |  |
| `customer_id` | I1 F1 | runtime value |  |
| `customer_name` | I1 | runtime value |  |
| `description` | I1 | runtime value |  |
| `first_response_at` | F3 I1 | null |  |
| `id` | F6 I1 | UUID string |  |
| `priority` | F2 I1 S1 | runtime value |  |
| `replies` | $push2 I1 | array |  |
| `resolved_at` | I1 S1 F1 | null, ISO-8601 string |  |
| `sla_resolution_deadline` | F3 I1 | ISO-8601 string |  |
| `sla_resolution_met` | I1 S1 | null, bool |  |
| `sla_response_deadline` | F3 I1 | ISO-8601 string |  |
| `sla_response_met` | I1 | null |  |
| `status` | F11 I1 S1 | string | `closed`, `open`, `resolved` |
| `subject` | I1 | runtime value |  |
| `tags` | I1 | array |  |
| `ticket_number` | I1 | string |  |
| `updated_at` | S2 I1 | ISO-8601 string |  |

### `village_landing_permissions`

- **References:** 23 in 2 files. **Operations:** find_one 10, update_one 8, create_index 3, insert_one 1, find 1.
- **ID strategy:** `id` UUID string. **Date format:** ISO string.
- **Referencing modules:** `routes/landing_infrastructure_routes.py`, `scripts/seed_landing_data.py`.
- **Indexes declared in code:** `customer_id:1` (scripts/seed_landing_data.py:383); `booking_id:1` (scripts/seed_landing_data.py:384); `status:1` (scripts/seed_landing_data.py:385).

| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |
|---|---|---|---|
| `booking_id` | I1 | runtime value |  |
| `created_at` | I1 O1 | ISO-8601 string |  |
| `customer_id` | I1 F1 | runtime value |  |
| `district` | I1 | runtime value |  |
| `documents` | $push2 I1 | array |  |
| `documents.$.rejection_reason` | S1 | null |  |
| `documents.$.status` | S1 | string | `approved`, `rejected` |
| `documents.$.verified_at` | S1 | ISO-8601 string |  |
| `documents.$.verified_by` | S1 | runtime value |  |
| `documents.id` | F1 | (read only here) |  |
| `id` | F17 I1 | UUID string |  |
| `inquiry_id` | I1 F1 | runtime value |  |
| `land_area_sqft` | I1 | runtime value |  |
| `land_owner_name` | I1 | runtime value |  |
| `land_owner_phone` | I1 | runtime value |  |
| `land_type` | I1 | runtime value |  |
| `latitude` | I1 | runtime value |  |
| `location_name` | I1 | runtime value |  |
| `longitude` | I1 | runtime value |  |
| `notes` | I1 | runtime value |  |
| `permission_number` | I1 | string |  |
| `pincode` | I1 | runtime value |  |
| `required_documents` | I1 | object |  |
| `review_notes` | S2 | runtime value |  |
| `reviewed_at` | S3 | ISO-8601 string |  |
| `reviewed_by` | S3 | runtime value |  |
| `state` | I1 | runtime value |  |
| `status` | S5 I1 | string | `approved`, `documents_pending`, `rejected`, `under_review` |
| `updated_at` | S5 I1 | ISO-8601 string |  |
| `village_name` | I1 | runtime value |  |

## 4. Remaining 260 collections (compact)

| Collection | Refs | Modules | Ops | Most-used fields | Dates | ID | Idx |
|---|---|---|---|---|---|---|---|
| `maintenance_schedules` | 22 | r/maintenance_routes.py, r/operator_erp_routes.py, scheduler.py | count_documents, find, find_one, insert_one, update_one | scheduled_date, status, aircraft_id, id, actual_cost, completion_date, actual_hours, notes | ISO string | `id` UUID string | 0 |
| `payroll` | 22 | r/ceo_routes.py, r/hr_advanced_routes.py, r/hr_employee_routes.py +2 | find, find_one, insert_one, update_one | status, id, month, year, employee_id, net_salary, paid_at, payment_reference | ISO string | `id` UUID string | 0 |
| `razorpay_orders` | 21 | r/ai_reports_routes.py, r/finance_reconciliation_routes.py, r/razorpay_routes.py | count_documents, find, find_one, insert_one, update_one | status, razorpay_order_id, razorpay_payment_id, created_at, refund_amount, refund_status, failed_at, refund_initiated_at | BSON Date | `_id` ObjectId only (ASSUMPTION) | 0 |
| `account_lockouts` | 20 | s/account_lockout_service.py, tests/test_account_lockout.py | delete_many, delete_one, find, find_one, insert_one, update_one | email, failed_attempts, updated_at, locked, locked_at, lockout_until, unlock_token, unlock_token_expires | BSON Date | `_id` ObjectId only (ASSUMPTION) | 0 |
| `exchange_listings` | 20 | r/aviation_exchange_routes.py, r/ceo_routes.py | count_documents, find, find_one, insert_many, insert_one, update_one | id, status, created_at, featured, seller_id, verified, views, category | ISO string | `id` custom string | 0 |
| `loyalty_profiles` | 20 | r/ai_advisor_routes.py, r/auth_routes.py, r/loyalty_routes.py | aggregate, count_documents, find, find_one, insert_one, update_one | user_id, available_points, tier, total_points, lifetime_points, total_bookings, total_spent, joined_at | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `sos_alerts` | 20 | r/command_center_routes.py, r/pilot_mobile_routes.py, r/sos_routes.py | aggregate, count_documents, find, find_one, insert_one, update_one | id, status, created_at, resolved_at, acknowledged_at, message, resolved_by, _id | MIXED (ISO 7 / Date 2) | `id` UUID string; `_id` set by code (string) | 0 |
| `verification_apis` | 20 | r/customer_kyc_routes.py, r/document_master_routes.py, r/kyc_verification_routes.py | delete_one, find, find_one, insert_one, update_one | code, id, last_used, successful_calls, total_calls, updated_at, is_enabled, api_key_configured | BSON Date | `id` custom string | 0 |
| `attendance` | 19 | r/ceo_routes.py, r/field_tracking_routes.py, r/hr_advanced_routes.py +3 | count_documents, find, find_one, insert_one, update_one | date, employee_id, check_out_time, id, status, check_out_location, total_hours, check_in_location | ISO string | `id` UUID string | 0 |
| `reviews` | 19 | r/admin_operator_management_routes.py, r/reviews_routes.py | aggregate, count_documents, delete_one, find, find_one, insert_one, update_one | id, status, operator_id, created_at, reported, updated_at, booking_id, customer_id | ISO string | `id` UUID string | 0 |
| `inventory_slots` | 18 | r/inventory_routes.py | aggregate, count_documents, find, find_one, insert_one, update_one | id, is_active, date, is_blocked, aircraft_id, bookings_count, waitlist, block_reason | ISO string | `id` UUID string | 0 |
| `customer_kyc_documents` | 17 | r/customer_kyc_routes.py, r/kyc_verification_routes.py | delete_one, find, find_one, insert_one, update_one | id, verification_status, updated_at, verification_notes, user_id, verified_at, created_at, document_number | BSON Date | `id` custom string | 0 |
| `expense_claims` | 17 | r/ai_advisor_routes.py, r/ceo_routes.py, r/hr_advanced_routes.py +1 | count_documents, find, find_one, insert_one, update_one | status, id, employee_id, added_to_salary_month, submitted_at, added_to_salary_year, approval_flow, created_at | ISO string | `id` UUID string | 0 |
| `finance_transactions` | 17 | r/finance_advanced_routes.py, r/finance_phase4_routes.py, r/finance_phase5_routes.py +1 | aggregate, count_documents, find, insert_one | created_at, transaction_type, category, bank_account_id, _id, amount, balance_after, balance_before | BSON Date | `_id` set by code (string) | 0 |
| `inquiry_operator_mappings` | 17 | r/admin_routes.py, r/email_routes.py, r/inquiry_broadcast_routes.py +1 | aggregate, find, find_one, insert_one, update_many, update_one | id, status, operator_id, action_device, action_ip, action_taken_at, broadcast_id, created_at | ISO string | `id` UUID string | 0 |
| `exchange_auctions` | 16 | r/aviation_exchange_routes.py, r/ceo_routes.py, scheduler.py | count_documents, find, find_one, insert_one, update_one | id, status, ends_at, current_bid_inr, listing_id, bid_count, created_at, ending_reminder_sent | ISO string | `id` custom string | 0 |
| `memberships` | 16 | r/ai_advisor_routes.py, r/ceo_routes.py, r/loyalty_routes.py +1 | aggregate, count_documents, find, find_one, insert_one, update_one | status, user_id, expiry_date, updated_at, auto_renew, benefit_usage, benefits, card_number | BSON Date | `id` custom string; `_id` used in filters | 0 |
| `boarding_passes` | 15 | r/boarding_pass_routes.py | count_documents, find, find_one, insert_one, update_one | id, flight_date, updated_at, boarded, booking_id, checked_in, boarded_at, checked_in_at | ISO string | `id` UUID string | 0 |
| `challans` | 15 | r/finance_advanced_routes.py, r/finance_phase4_routes.py, r/finance_treasury_routes.py | count_documents, find, find_one, insert_one, update_one | status, type, challan_type, due_date, id, period, updated_at, amount | BSON Date | `id` UUID string | 0 |
| `chat_messages` | 15 | r/chat_routes.py, r/pilot_chat_routes.py, r/websocket_chat_routes.py | count_documents, delete_one, find, find_one, insert_one, update_many, update_one | created_at, id, read, sender_id, booking_id, conversation_id, read_by, read_at | ISO string | `id` UUID string | 0 |
| `settlements` | 15 | r/admin_approval_routes.py, r/admin_settlement_routes.py, r/reports_routes.py +2 | count_documents, find, find_one, insert_one, update_one | id, status, created_at, operator_id, paid_at, payment_reference, approved_at, approved_by | ISO string | `id` UUID string | 0 |
| `aircraft_documents` | 14 | r/admin_routes.py, r/aircraft_document_routes.py, r/operator_erp_routes.py +1 | count_documents, delete_one, find, find_one, insert_one, update_one | status, id, expiry_date, aircraft_id, created_at, document_type, operator_id, confirmed_at | ISO string | `id` UUID string | 0 |
| `bank_accounts` | 14 | r/finance_phase4_routes.py, r/finance_treasury_routes.py | find, find_one, insert_one, update_many, update_one | _id, is_active, is_primary, updated_at, account_number, current_balance, account_name, account_type | BSON Date | `_id` set by code (string) | 0 |
| `fleet` | 14 | db_optimization.py, r/admin_analytics_routes.py, r/ai_advisor_routes.py +3 | count_documents, find, find_one, index_spec | status, id | unknown | `id` (queried; written elsewhere) | 3 |
| `flight_records` | 14 | r/fleet_routes.py, r/flight_record_routes.py, r/journey_routes.py +4 | find, find_one, insert_one, update_one | aircraft_id, departure_time, booking_id, flight_date, pilot_id, status, arrival_time, created_at | ISO string | `id` UUID string | 0 |
| `in_app_notifications` | 14 | r/admin_approval_routes.py, r/admin_booking_management_routes.py, r/admin_operator_management_routes.py +3 | count_documents, find, insert_one, update_many, update_one | read, user_id, created_at, id, message, title, type, data | ISO string | `id` UUID string | 0 |
| `landing_permissions` | 14 | r/admin_landing_permission_routes.py, r/admin_routes.py, r/customer_routes.py +2 | count_documents, find, find_one, insert_one, update_one | id, approval_status, booking_id, updated_at, approval_notes, approved_at, approved_by, approved_by_name | ISO string | `id` UUID string | 0 |
| `platform_settings` | 14 | r/customer_routes.py, r/fixed_route_pricing_routes.py, r/price_breakup_routes.py +3 | find_one, insert_one, update_one | type, key, updated_at, updated_by, commission_percent, created_at, gst_rate, id | MIXED (ISO 3 / Date 1) | `id` UUID string | 0 |
| `verified_documents` | 14 | r/document_verification_routes.py | aggregate, count_documents, find, find_one, insert_one, update_one | status, expiry_date, id, submitted_at, document_number, document_type, entity_id, entity_type | ISO string | `id` UUID string | 0 |
| `customer_inquiries` | 13 | r/admin_analytics_routes.py, r/ai_advisor_routes.py, r/operations_map_routes.py +1 | count_documents, find | payment_status, created_at, status, from_location, to_location, travel_date | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `fixed_routes` | 13 | r/fixed_route_pricing_routes.py | count_documents, find, find_one, insert_one, update_one | is_deleted, id, is_active, operator_id, destination, is_verified, origin, aircraft_id | BSON Date | `id` UUID string | 0 |
| `live_flights` | 13 | r/flight_tracking_live_routes.py | aggregate, count_documents, find, find_one, insert_one, update_one | is_active, id, booking_id, actual_arrival, actual_departure, current_position, eta, position_history | ISO string | `id` UUID string | 0 |
| `scheduled_finance_reports` | 13 | r/finance_scheduled_routes.py, scheduler.py | delete_one, find, find_one, insert_one, update_one | id, last_status, is_active, last_sent, send_count, created_at, updated_at, created_by | BSON Date | `id` UUID string | 0 |
| `user_2fa_settings` | 13 | r/two_factor_auth_routes.py | count_documents, find_one, update_one | user_id, backup_codes_used, enabled, backup_codes, totp_verified, codes_regenerated_at, disabled_at, enabled_methods | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `document_types` | 12 | r/customer_kyc_routes.py, r/document_master_routes.py | count_documents, find, find_one, insert_one, update_one | id, is_active, code, updated_at, category, created_at, deleted_at, display_order | BSON Date | `id` custom string | 0 |
| `favorites` | 12 | r/favorites_routes.py | delete_one, find, find_one, insert_one, update_one | user_id, item_type, order, item_id, _id, created_at, label, metadata | BSON Date | `_id` set by code (string) | 0 |
| `field_visits` | 12 | r/field_tracking_routes.py | find, find_one, insert_one, update_one | id, date, status, employee_id, actual_arrival_time, arrival_location, actual_departure_time, departure_location | ISO string | `id` UUID string | 0 |
| `gst_returns` | 11 | r/gst_routes.py | count_documents, find, find_one, insert_one, update_one | id, status, due_date, payment_status, return_type, updated_at, year, arn | ISO string | `id` UUID string | 0 |
| `leaves` | 11 | r/ceo_routes.py, r/hr_employee_routes.py, r/hr_routes.py +1 | count_documents, find, find_one, insert_one, update_one | status, id, approved_at, approved_by, created_at, employee_id, end_date, start_date | ISO string | `id` UUID string | 0 |
| `trusted_devices` | 11 | r/auth_routes.py, s/login_shield_service.py, s/otp_service.py | count_documents, find, find_one, insert_one, update_many, update_one | is_active, user_id, expires_at, id, last_used_at, device_hash, revoked_at, created_at | ISO string | `id` custom string | 0 |
| `corporate_employees` | 10 | r/corporate_routes.py | aggregate, count_documents, find, find_one, insert_one, update_one | corporate_id, employee_code, is_active, role, department, email, total_spend, updated_at | BSON Date | `id` custom string | 0 |
| `corporates` | 10 | r/corporate_routes.py | count_documents, find, find_one, insert_one, update_one | corporate_id, status, updated_at, credit_limit, departments, gst_number, registration_number, address | BSON Date | `id` custom string | 0 |
| `emergency_bookings` | 10 | r/emergency_booking_routes.py, tests/test_emergency_booking.py | delete_many, find, find_one, insert_one, update_one | id, status, created_at, updated_at, customer_id, priority_score, responses, selected_aircraft_id | ISO string | `id` UUID string | 0 |
| `feedback` | 10 | r/analytics_routes.py, r/customer_routes.py, r/feedback_routes.py | aggregate, find, find_one, insert_one, update_one | booking_id, created_at, id, operator_id, customer_id, operator_response, aircraft_id, aircraft_rating | ISO string | `id` UUID string | 0 |
| `helipad_availability` | 10 | r/landing_infrastructure_routes.py, scripts/seed_landing_data.py | create_index, find, find_one, insert_one, update_one | date, landing_point_id, status, from_time, id, reason, to_time, created_at | ISO string | `id` UUID string | 1 |
| `partners` | 10 | r/ceo_routes.py, r/partner_routes.py | count_documents, find, find_one, insert_one, update_one | id, api_key, status, created_at, last_used_at, request_count, webhook_url | ISO string | `id` custom string | 0 |
| `verification_logs` | 10 | r/aircraft_catalog_routes.py, r/document_master_routes.py, r/kyc_verification_routes.py +1 | delete_many, find, insert_one | timestamp, api_code, id, status, document_type, sandbox_mode, user_id, reference_id | MIXED (ISO 1 / Date 6) | `id` UUID string | 0 |
| `wallets` | 10 | r/referral_routes.py | find_one, insert_one, update_one | user_id, balance, total_earned, total_used, created_at, id | ISO string | `id` UUID string | 0 |
| `exchange_fractional` | 9 | r/aviation_exchange_routes.py, r/ceo_routes.py | count_documents, find, find_one, insert_many, update_one | id, created_at, shares_available, status | ISO string | `id` (queried; written elsewhere) | 0 |
| `exchange_watchlist` | 9 | r/aviation_exchange_routes.py, r/ceo_routes.py, scheduler.py | aggregate, count_documents, delete_one, find, find_one, insert_one | user_id, auction_id, created_at, id, auction_title, user_email, user_name | ISO string | `id` UUID string | 0 |
| `flight_duty_logs` | 9 | r/dgca_compliance_routes.py | aggregate, find, find_one, insert_one | date, pilot_id, created_at, id, logged_by | ISO string | `id` UUID string | 0 |
| `hangar_bookings` | 9 | r/hangar_management_routes.py | count_documents, find, find_one, insert_one, update_one | start_date, status, end_date, hangar_id, id, aircraft_id, aircraft_registration, booked_by | ISO string | `id` custom string | 0 |
| `insurance_claims` | 9 | r/insurance_routes.py | aggregate, count_documents, find, insert_one, update_one | status, created_at, approved_amount, customer_id, id, policy_id, remarks, updated_at | ISO string | `id` UUID string | 0 |
| `insurance_policies` | 9 | r/finance_treasury_routes.py, r/insurance_routes.py | aggregate, count_documents, find, find_one, insert_one | status, id, booking_id, created_at, customer_id, booking_number, coverage_amount, customer_name | ISO string | `id` UUID string | 0 |
| `journey_otps` | 9 | r/journey_routes.py | find_one, insert_one, update_one | verified, booking_id, id, otp_type, created_at, expires_at, otp, pilot_id | ISO string | `id` UUID string | 0 |
| `kb_articles` | 9 | r/knowledge_routes.py | aggregate, count_documents, find, find_one, insert_one, update_one | id, is_published, views, content, title, category, created_at, created_by | ISO string | `id` UUID string | 0 |
| `pilot_assignments` | 9 | r/operator_routes.py, r/pilot_availability_routes.py, r/pilot_mobile_routes.py | delete_one, find, find_one, update_one | pilot_id, flight_date, booking_id, date, operator_id, created_at, created_by, flight_id | ISO string | `id` UUID string | 0 |
| `price_locks` | 9 | r/price_breakup_routes.py, tests/test_aircraft_and_pricing.py | delete_one, find_one, insert_one, update_one | id, status, used_at, auction_id, booking_id, created_at, duration_minutes, expires_at | ISO string | `id` UUID string | 0 |
| `salary_runs` | 9 | r/payment_gateway_routes.py | find, find_one, insert_one, update_one | id, status, created_at, year, approval_id, month, batch_id, created_by | ISO string | `id` UUID string | 0 |
| `ai_chat_history` | 8 | r/ai_routes.py | aggregate, find, insert_one | conversation_id, created_at, user_id, content, id, role, ai_generated, model | ISO string | `id` UUID string | 0 |
| `bank_statement_entries` | 8 | r/finance_advanced_routes.py | find, insert_one, update_many, update_one | reconciliation_status, bank_account_id, id, matched_transaction_id, matched_at, statement_id, transaction_date, balance | BSON Date | `id` UUID string | 0 |
| `bill_repository` | 8 | r/finance_phase4_routes.py | count_documents, find, find_one, insert_one, update_one | invoice_date, is_archived, id, tags, bill_number, category, description, invoice_number | BSON Date | `id` UUID string | 0 |
| `blog_posts` | 8 | r/content_routes.py | count_documents, delete_one, find, find_one, insert_one, update_one | id, is_published, slug, category, content, created_at, excerpt, tags | ISO string | `id` custom string | 0 |
| `campaigns` | 8 | r/marketing_routes.py | count_documents, find, find_one, insert_one, update_one | status, created_at, id, type, updated_at, campaign_code, created_by, stats | ISO string | `id` UUID string | 0 |
| `chat_conversations` | 8 | r/pilot_chat_routes.py | find, find_one, insert_one, update_one | pilot_id, last_message_at, participants, type, id, last_message_preview, created_at, last_sender_name | ISO string | `id` custom string | 0 |
| `chatbot_conversations` | 8 | r/chatbot_routes.py | aggregate, count_documents, find, insert_one, update_one | created_at, feedback_helpful, id, intent, session_id, user_id, bot_response, context | ISO string | `id` UUID string | 0 |
| `company_holidays` | 8 | r/hr_employee_routes.py, r/hr_routes.py, scheduler.py | delete_one, find, find_one, insert_one | date, id, created_at, created_by, name | ISO string | `id` UUID string | 0 |
| `crm_tasks` | 8 | r/crm_routes.py | count_documents, find, insert_one, update_one | status, due_date, assigned_to, lead_id, id, priority, created_at, description | ISO string | `id` UUID string | 0 |
| `employee_salaries` | 8 | r/hr_advanced_routes.py, r/hr_employee_routes.py, r/hr_routes.py | find_one, insert_one, update_many | status, employee_id, basic_salary, created_at, created_by, effective_from, gross_salary, id | ISO string | `id` UUID string | 0 |
| `exchange_fractional_reservations` | 8 | r/aviation_exchange_routes.py, r/ceo_routes.py | count_documents, find, find_one, insert_one, update_one | id, status, created_at, investor_id, fractional_id, investor_email, investor_name, investor_phone | ISO string | `id` UUID string | 0 |
| `hr_settings` | 8 | r/hr_employee_routes.py, scheduler.py | find_one, update_one | type, last_run_at, enabled, last_nudge_at, last_nudge_count, last_nudge_date, last_run_count, last_run_net | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `otp_codes` | 8 | s/otp_service.py | find_one, insert_one, update_many, update_one | is_used, id, purpose, user_id, attempts, created_at, is_verified, email | ISO string | `id` custom string | 0 |
| `payments` | 8 | db_optimization.py, r/ai_reports_routes.py, r/command_center_routes.py | count_documents, find, index_spec | created_at, status | unknown | `_id` ObjectId only (ASSUMPTION) | 3 |
| `referral_codes` | 8 | r/referral_routes.py | find, find_one, insert_one, update_one | code, user_id, successful_referrals, total_earnings, total_referrals, created_at, id, user_email | ISO string | `id` UUID string | 0 |
| `vendors` | 8 | r/finance_advanced_routes.py, r/gst_routes.py, r/payment_gateway_routes.py | find, find_one, insert_one | id, is_active, name, tds_rate, vendor_code, account_holder_name, account_number, address | ISO string | `id` UUID string | 0 |
| `ai_advisor_chats` | 7 | r/ai_advisor_routes.py | aggregate, delete_many, find, insert_many | session_id, timestamp, user_id, content, role | BSON Date | `_id` ObjectId only (ASSUMPTION) | 0 |
| `api_keys_settings` | 7 | r/settings_routes.py, r/verification_gst_pan_routes.py, r/verification_routes.py +2 | find_one, update_one | type, updated_at, updated_by | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `crm_calls` | 7 | r/crm_routes.py | count_documents, find, insert_one | created_at, agent_id, lead_id, agent_name, call_type, customer_id, duration_seconds, follow_up_required | ISO string | `id` UUID string | 0 |
| `documents` | 7 | r/document_routes.py | delete_one, find, find_one, insert_one, update_one | id, created_at, status, user_id, content_type, document_type, expires_at, file_name | ISO string | `id` UUID string | 0 |
| `employee_bank_details` | 7 | r/hr_advanced_routes.py, r/payment_gateway_routes.py | find_one, update_one | employee_id, account_holder_name, account_number, account_type, bank_name, ifsc_code, is_verified, updated_at | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `finance_audit_logs` | 7 | r/finance_phase5_routes.py | count_documents, distinct, find, insert_one | created_at, action, description, entity_id, entity_type, module, user_email, id | BSON Date | `id` UUID string | 0 |
| `hangars` | 7 | r/hangar_management_routes.py | find, find_one, insert_many, insert_one, update_one | id, available_slots, status, capacity, created_at, created_by, daily_rate, facilities | ISO string | `id` custom string | 0 |
| `landing_rent` | 7 | r/landing_infrastructure_routes.py, scripts/seed_landing_data.py | create_index, find_one, insert_one, update_many | is_active, landing_point_id, base_rent_amount, created_at, effective_from, effective_to, fixed_wing_rate, gst_applicable | ISO string | `id` UUID string | 1 |
| `login_risk_assessments` | 7 | s/ip_geolocation_service.py, s/login_shield_service.py | count_documents, find, find_one, insert_one | assessed_at, user_id, level, login_successful, action, action.type, alerts, email | ISO string | `id` custom string | 0 |
| `partner_bookings` | 7 | r/ceo_routes.py, r/partner_routes.py | count_documents, find, find_one, insert_one, update_one | id, status, created_at, partner_id, updated_at, partner_company | ISO string | `id` custom string | 0 |
| `payment_links` | 7 | r/admin_payments_routes.py, r/stripe_payment_routes.py | find_one, insert_one, update_one | token, status, amount, booking_id, checkout_at, checkout_session_id, created_at, created_by | ISO string | `id` UUID string | 0 |
| `points_history` | 7 | r/auth_routes.py, r/loyalty_routes.py | find, find_one, insert_one | created_at, type, user_id, description, id, points, reference_id, adjusted_by | ISO string | `id` UUID string | 0 |
| `promo_codes` | 7 | r/marketing_routes.py | aggregate, count_documents, find, find_one, insert_one, update_one | status, code, created_at, id, valid_until, applicable_aircraft, applicable_routes, created_by | ISO string | `id` UUID string | 0 |
| `revoked_tokens` | 7 | middleware.py, r/auth_routes.py, security_middleware.py | alias, find_one, insert_one | token_hash, expires_at, reason, revoked_at, user_id | BSON Date | `_id` ObjectId only (ASSUMPTION) | 0 |
| `reward_redemptions` | 7 | r/loyalty_routes.py, r/payment_routes.py, r/stripe_payment_routes.py +1 | find, find_one, insert_one, update_one | status, code, user_id, created_at, expires_at, expiry_alert_sent, id, used_at | ISO string | `id` UUID string | 0 |
| `roles` | 7 | r/admin_user_routes.py | delete_one, find, find_one, insert_one, update_one | id, description, name, name_hi, permissions, created_at, created_by, is_system | ISO string | `id` (runtime value) | 0 |
| `booking_timeline` | 6 | r/admin_approval_routes.py, r/admin_booking_management_routes.py | find, insert_one | booking_id, created_at, description, event_label, event_type, id, user_id, user_name | ISO string | `id` UUID string | 0 |
| `cash_accounts` | 6 | r/finance_treasury_routes.py | find_one, insert_one, update_one | is_active, _id, balance, created_at, name, updated_at | BSON Date | `_id` set by code (runtime value) | 0 |
| `ceo_settings` | 6 | r/ceo_routes.py, scheduler.py | find_one, update_one | type, last_sent_at, last_sent_count, emails, last_sent_period, updated_at | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `device_tokens` | 6 | r/push_notification_routes.py | aggregate, count_documents, delete_one, find, find_one, insert_one | user_id, device_token, is_active, device_name, id, last_active, platform, registered_at | ISO string | `id` UUID string | 0 |
| `discount_codes` | 6 | r/referral_routes.py | delete_one, find, find_one, insert_one, update_one | code, id, created_at, created_by, is_active, times_used, updated_at, updated_by | ISO string | `id` UUID string | 0 |
| `expenses` | 6 | r/accounting_routes.py, r/finance_reconciliation_routes.py, scheduler.py | aggregate, find, insert_one | created_at, date, category, id, recorded_by, synced, total_amount | ISO string | `id` UUID string | 0 |
| `landing_documents` | 6 | r/landing_infrastructure_routes.py | delete_one, find, find_one, insert_one, update_one | id, created_at, landing_point_id, remark, status, updated_at, verified, verified_at | ISO string | `id` UUID string | 0 |
| `multileg_bookings` | 6 | r/multileg_booking_routes.py | find, find_one, insert_one, update_one | id, created_at, group_members, status, total_passengers, updated_at, user_id, booking_number | ISO string | `id` UUID string | 0 |
| `otp_records` | 6 | r/verification_routes.py | find_one, insert_one, update_one | verified, purpose, email, otp, phone, id, created_at, expires_at | ISO string | `id` UUID string | 0 |
| `payment_batches` | 6 | r/payment_gateway_routes.py | find, find_one, insert_one | id, initiated_at, type, batch_number, failed_count, initiated_by, payment_mode, status | ISO string | `id` UUID string | 0 |
| `payment_rules_settings` | 6 | r/customer_routes.py, r/settings_routes.py, r/stripe_payment_routes.py | find_one, update_one | type, global_settings, payment_rules, updated_at, updated_by | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `razorpay_settlements` | 6 | r/finance_reconciliation_routes.py, r/finance_scheduled_routes.py, scheduler.py | count_documents, find, find_one, insert_one | created_at, settlement_id, amount, fees, id, payment_id, status, synced_at | BSON Date | `id` UUID string | 0 |
| `regional_managers` | 6 | r/regional_manager_routes.py | find_one, insert_one | user_id, created_at, id, region | ISO string | `id` UUID string | 0 |
| `salary_payments` | 6 | r/finance_treasury_routes.py, r/hr_advanced_routes.py | find, find_one, insert_one, update_one | status, employee_id, id, initiated_at, payment_date, payroll_id, utr_number, account_number | ISO string | `id` UUID string | 0 |
| `settlement_runs` | 6 | r/settlement_automation_routes.py, s/settlement_service.py | find, find_one, insert_one, update_one | id, status, errors, operators_processed, settlements_created, total_amount, completed_at, created_at | ISO string | `id` UUID string | 0 |
| `settlement_sync_logs` | 6 | r/finance_scheduled_routes.py, scheduler.py | find, insert_one | created_at, gateway, id, status, error, payouts_synced, settlements_synced, transactions_synced | BSON Date | `id` UUID string | 0 |
| `stripe_settlements` | 6 | r/finance_reconciliation_routes.py, r/finance_scheduled_routes.py, scheduler.py | count_documents, find, find_one, insert_one | created_at, payout_id, amount, arrival_date, currency, destination, id, method | BSON Date | `id` UUID string | 0 |
| `tally_sync_logs` | 6 | r/tally_routes.py | count_documents, find, find_one, insert_one, update_one | created_at, id, status, completed_at, started_at, sync_type, triggered_by, vouchers_synced | ISO string | `id` UUID string | 0 |
| `tally_voucher_queue` | 6 | r/tally_routes.py | count_documents, find, insert_one, update_many | status, created_at, voucher_type, created_by, id, synced_at | ISO string | `id` UUID string | 0 |
| `zoho_config` | 6 | r/zoho_routes.py | find_one, update_one | updated_at, updated_by | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `admin_pricing_controls` | 5 | r/pricing_engine_routes.py, s/pricing_engine.py | find_one, insert_one, update_many, update_one | is_active, peak_dates | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `budgets` | 5 | r/finance_phase4_routes.py | find, find_one, insert_one, update_one | month, category, notes, planned_amount, updated_at, _id, actual_amount, created_at | BSON Date | `id` UUID string; `_id` used in filters | 0 |
| `calendar_sync_settings` | 5 | r/calendar_sync_routes.py | find_one, update_one | user_id, updated_at | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `compliance_reports` | 5 | r/compliance_monitor_routes.py, r/dgca_compliance_routes.py, scheduler.py | find, find_one, insert_one | id, run_at, aircraft_auto_hidden, run_date, total_alerts, actions_taken, alerts, alerts_by_severity | ISO string | `id` UUID string | 0 |
| `corporate_contracts` | 5 | r/pricing_engine_routes.py, s/pricing_engine.py | find, find_one, insert_one | is_active, contract_id, tagged_customer_ids, tagged_email_domains | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `crm_activities` | 5 | r/crm_routes.py | find, insert_one | created_at, lead_id, description, id, type, user_id, user_name | ISO string | `id` UUID string | 0 |
| `document_files` | 5 | r/document_vault_routes.py | delete_one, find_one, insert_one | file_id, content_type, created_at, file_name, content, is_deleted, size, storage_path | BSON Date | `_id` ObjectId only (ASSUMPTION) | 0 |
| `document_shares` | 5 | r/document_vault_routes.py | find_one, insert_one, update_one | share_link, is_active, access_count, last_accessed, created_at, document_id, document_name, expiry_date | BSON Date | `_id` ObjectId only (ASSUMPTION) | 0 |
| `exchange_inquiries` | 5 | r/aviation_exchange_routes.py, r/ceo_routes.py | count_documents, find, insert_one, update_one | created_at, id, listing_id, status, buyer_email, buyer_id, buyer_name, buyer_phone | ISO string | `id` UUID string | 0 |
| `exchange_inspections` | 5 | r/aviation_exchange_routes.py, r/ceo_routes.py | count_documents, find, find_one, insert_one, update_one | id, status, created_at, buyer_email, buyer_id, buyer_name, buyer_phone, listing_id | ISO string | `id` UUID string | 0 |
| `fleet_gallery` | 5 | r/content_routes.py | delete_one, distinct, find, insert_one, update_one | id, is_available, created_at, created_by, hourly_rate, name, type, updated_at | ISO string | `id` custom string | 0 |
| `flight_logs` | 5 | r/pilot_mobile_routes.py, r/predictive_maintenance_routes.py | find | pilot_id, date | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `fuel_records` | 5 | r/fleet_routes.py, r/fuel_record_routes.py, r/operator_erp_routes.py | delete_one, find, insert_one | aircraft_id, refill_date, id, refilled_by, cost_per_liter, created_at, fuel_amount_liters, fuel_type | ISO string | `id` UUID string | 0 |
| `hangar_inventory` | 5 | r/hangar_management_routes.py | find, find_one, insert_many, insert_one, update_one | id, category, created_at, created_by, name, quantity, updated_at | ISO string | `id` custom string | 0 |
| `investor_interests` | 5 | r/content_routes.py | count_documents, find, insert_one, update_one | status, id, created_at, notes, updated_at, updated_by | ISO string | `id` custom string | 0 |
| `notification_queue` | 5 | r/push_notification_routes.py, scheduler.py | find, insert_one, update_one | status, id, body, created_at, data, device_token, error, platform | ISO string | `id` UUID string | 0 |
| `parts_inventory` | 5 | r/maintenance_routes.py | aggregate, find, find_one, insert_one, update_one | id, updated_at, category, created_at, quantity | ISO string | `id` UUID string | 0 |
| `payment_orders` | 5 | r/ceo_routes.py, r/payment_routes.py | find, find_one, insert_one, update_one | order_id, status, amount, amount_paise, booking_id, created_at, customer_id, id | ISO string | `id` UUID string | 0 |
| `pilot_availability` | 5 | r/pilot_availability_routes.py | delete_one, find, update_one | date, pilot_id, created_at, id, notes, status, updated_at | ISO string | `id` custom string | 0 |
| `pilot_fdtl` | 5 | r/pilot_mobile_routes.py | find_one, update_one | pilot_id, is_on_duty, updated_at, duty_end_time, duty_start_time, fdp_used | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `pricing_settings` | 5 | r/pincode_routes.py, r/settings_routes.py | find_one, insert_one, update_one | type, created_at, id, updated_at, updated_by | ISO string | `id` UUID string | 0 |
| `referral_settings` | 5 | r/referral_routes.py | find_one, update_one | type, updated_at, updated_by | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `rewards_catalog` | 5 | r/loyalty_routes.py | count_documents, find, find_one, insert_many, update_one | id, active, can_redeem, tier_locked, updated_at | ISO string | `id` UUID string | 0 |
| `salary_config` | 5 | r/hr_advanced_routes.py, r/hr_routes.py | find_one, insert_one, update_one | type, esi_employer_percent, esi_enabled, esi_limit, esi_percent, overtime_rate_multiplier, pf_employer_percent, pf_enabled | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `sales_targets` | 5 | r/hr_advanced_routes.py | find, insert_one, update_one | status, employee_id, month, year, calls_achieved, conversions_achieved, id, leads_achieved | ISO string | `id` UUID string | 0 |
| `tally_config` | 5 | r/tally_routes.py | find_one, update_one | updated_at, updated_by | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `zoho_invoices` | 5 | r/zoho_routes.py | count_documents, find, insert_one | status, created_at, id, sync_status, total, zoho_invoice_id, booking_id, customer_id | ISO string | `id` UUID string | 0 |
| `calendar_connections` | 4 | r/calendar_sync_routes.py | delete_many, delete_one, find, insert_one | user_id, provider, access_token, calendar_id, connected_at, id, is_active, last_sync | ISO string | `id` UUID string | 0 |
| `calendar_events` | 4 | r/calendar_sync_routes.py | find, find_one, insert_one | user_id, booking_id, created_at, id, synced_to, description, reminder_minutes, start_time | ISO string | `id` UUID string | 0 |
| `cash_entries` | 4 | r/finance_phase4_routes.py, r/finance_treasury_routes.py | find, insert_one | created_at, _id, amount, balance_after, balance_before, category, description, entry_type | BSON Date | `_id` set by code (string) | 0 |
| `emergency_alerts` | 4 | r/emergency_booking_routes.py, tests/test_emergency_booking.py | delete_many, find, insert_one, update_one | emergency_booking_id, operator_id, status, expires_at, notified_at, aircraft_id, id, responded_at | ISO string | `id` UUID string | 0 |
| `flight_type_pricing` | 4 | r/settings_routes.py | find_one, insert_one, update_one | type, created_at, id, updated_at, updated_by | ISO string | `id` UUID string | 0 |
| `incentive_config` | 4 | r/hr_routes.py | find_one, insert_one, update_one | type, incentives_enabled, penalty_amount, penalty_below_percent, penalty_enabled, per_conversion_amount, per_conversion_enabled, per_conversion_min_value | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `inquiry_action_logs` | 4 | r/inquiry_broadcast_routes.py, s/inquiry_broadcast_service.py | find, insert_one | created_at, inquiry_id, action, id, mapping_id, operator_id, device_info, ip_address | ISO string | `id` UUID string | 0 |
| `inquiry_broadcasts` | 4 | r/inquiry_broadcast_routes.py, s/inquiry_broadcast_service.py | find, find_one, insert_one, update_one | id, created_at, status, booking_id, drop_location, expire_at, inquiry_id, notifications_sent | ISO string | `id` UUID string | 0 |
| `kb_faqs` | 4 | r/knowledge_routes.py | count_documents, find, insert_one | answer, question, category, created_at, created_by, id, is_featured, order | ISO string | `id` UUID string | 0 |
| `kb_videos` | 4 | r/knowledge_routes.py | count_documents, find, insert_one | created_at, category, created_by, id, title, views | ISO string | `id` UUID string | 0 |
| `live_tracking` | 4 | r/live_tracking_routes.py | find, find_one, insert_one | aircraft_id, booking_id, timestamp, tracking_id, altitude_feet, flight_status, heading_degrees, latitude | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `location_history` | 4 | r/field_tracking_routes.py | find, insert_one | date, employee_id, timestamp, accuracy, address, altitude, battery_level, employee_name | ISO string | `id` UUID string | 0 |
| `notification_preferences` | 4 | r/notification_routes.py, r/push_notification_routes.py | find_one, update_one | user_id, updated_at | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `operator_pricing` | 4 | r/pricing_engine_routes.py, r/route_intelligence_routes.py, s/pricing_engine.py | find, find_one, update_one | operator_id, helicopter_id, is_active | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `push_notifications` | 4 | r/marketing_routes.py | find, find_one, insert_one, update_one | id, status, created_at, click_count, created_by, read_count, sent_at, sent_count | ISO string | `id` UUID string | 0 |
| `regions` | 4 | r/settings_routes.py | delete_one, find, insert_one, update_one | id, created_at, created_by, updated_at | ISO string | `id` UUID string | 0 |
| `security_incidents` | 4 | r/auth_routes.py, s/login_shield_service.py | count_documents, find, insert_one, update_one | status, created_at, id, email, ip_address, resolution, resolved_at, resolved_by | ISO string | `id` custom string | 0 |
| `travel_policies` | 4 | r/corporate_routes.py | find_one, insert_one, update_one | corporate_id, updated_at, advance_booking_days, allowed_aircraft_types, auto_approve_below, blackout_dates, created_at, international_allowed | BSON Date | `_id` ObjectId only (ASSUMPTION) | 0 |
| `twilio_config` | 4 | r/twilio_routes.py | find_one, update_one | updated_at, updated_by | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `user_notifications` | 4 | r/push_notification_routes.py | count_documents, find, update_many, update_one | is_read, user_id, read_at, created_at, id | ISO string | `id` (queried; written elsewhere) | 0 |
| `wallet_transactions` | 4 | r/referral_routes.py | find, insert_one | created_at, user_id, amount, balance_after, id, reason, type, booking_id | ISO string | `id` UUID string | 0 |
| `zoho_contacts` | 4 | r/zoho_routes.py | count_documents, find, insert_one | contact_type, created_at, id, sync_status, zoho_contact_id | ISO string | `id` UUID string | 0 |
| `zoho_leads` | 4 | r/zoho_routes.py | count_documents, find, insert_one | created_at, lead_source, lead_status, id, sync_status, zoho_lead_id | ISO string | `id` UUID string | 0 |
| `zoho_sync_logs` | 4 | r/zoho_routes.py | count_documents, find, find_one, insert_one | created_at, id, module, records_synced, status, triggered_by | ISO string | `id` UUID string | 0 |
| `additional_charges` | 3 | r/pricing_engine_routes.py, s/pricing_engine.py | find_one, update_one | operator_id, helicopter_id | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `admin_alerts` | 3 | s/login_shield_service.py | find, insert_one, update_one | is_read, created_at, id, type, details, message, read_at, severity | ISO string | `id` custom string | 0 |
| `ai_warnings` | 3 | r/command_center_routes.py | find, insert_one, update_one | status, _id, acknowledged_at, acknowledged_by, created_at, priority, affected_entity, description | BSON Date | `_id` set by code (string) | 0 |
| `automation_config` | 3 | r/settlement_automation_routes.py | find_one, update_one | type, auto_approve_below, day_of_week, enabled, min_amount, next_run, notification_enabled, require_approval_above | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `booking_approvals` | 3 | r/corporate_routes.py | find, insert_one, update_one | status, approval_id, approved_at, approver_id, approver_name, corporate_id, created_at, rejection_reason | BSON Date | `_id` ObjectId only (ASSUMPTION) | 0 |
| `call_recording_settings` | 3 | r/settings_routes.py | find_one, update_one | type, exotel_token, twilio_auth_token, call_provider, call_recording_enabled, exotel_caller_id, exotel_sid, exotel_subdomain | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `compliance_items` | 3 | r/maintenance_routes.py | count_documents, find, insert_one | expiry_date, aircraft_id, created_at, id, status, type | ISO string | `id` UUID string | 0 |
| `corporate_accounts` | 3 | r/loyalty_routes.py | count_documents, find, insert_one | status, account_number, created_at, created_by, credit_used, id, total_bookings, total_spent | ISO string | `id` UUID string | 0 |
| `crm_targets` | 3 | r/crm_routes.py, r/hr_routes.py | find, find_one, insert_one | sales_person_id, period_start, period_end, period_type, calls_achieved, calls_target, conversions_achieved, conversions_target | ISO string | `id` UUID string | 0 |
| `dead_leg_pricing` | 3 | r/pricing_engine_routes.py, s/pricing_engine.py | find_one, update_one | operator_id, helicopter_id | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `document_folders` | 3 | r/document_vault_routes.py | count_documents, find, insert_one | parent_id, owner_id, color, created_at, description, folder_id, icon, name | BSON Date | `_id` ObjectId only (ASSUMPTION) | 0 |
| `duty_logs` | 3 | r/pilot_mobile_routes.py | find, insert_one | created_at, pilot_id, date, id, time, type, hours | ISO string | `id` custom string | 0 |
| `employee_current_location` | 3 | r/field_tracking_routes.py | find, update_one | employee_id, accuracy, address, altitude, battery_level, date, employee_name, heading | ISO string | `id` UUID string | 0 |
| `exchange_bids` | 3 | r/aviation_exchange_routes.py, r/ceo_routes.py | count_documents, find, insert_one | auction_id, created_at, amount_inr, bidder_id, bidder_name, id | ISO string | `id` UUID string | 0 |
| `gst_payments` | 3 | r/gst_routes.py | find, insert_one | payment_date, month, year, bank_name, bank_reference, cess_paid, cgst_paid, challan_number | ISO string | `id` UUID string | 0 |
| `gst_reminders` | 3 | r/gst_routes.py | find, insert_one | sent_at, vendor_id, bills, id, sent_by, status, vendor_email, vendor_name | ISO string | `id` UUID string | 0 |
| `gst_verifications` | 3 | r/verification_gst_pan_routes.py | find_one, update_one | gstin, source, verified, verified_at | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `journal_entries` | 3 | r/payment_gateway_routes.py | insert_one | created_at, created_by, date, entries, entry_number, id, narration, reference_id | ISO string | `id` UUID string | 0 |
| `leave_balance` | 3 | r/hr_employee_routes.py, r/hr_routes.py | find_one, update_one | employee_id, year | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `notification_logs` | 3 | r/notification_routes.py | find, insert_one | created_at, id, result, sent_by, to, type, subject | ISO string | `id` UUID string | 0 |
| `notification_templates` | 3 | r/settings_routes.py | find, insert_one, update_one | id, created_at, template_type, updated_at | ISO string | `id` UUID string | 0 |
| `operator_documents` | 3 | r/admin_operator_management_routes.py | count_documents, find, update_one | operator_id, expiry_date, id, updated_at, verification_notes, verification_status, verified_at, verified_by | ISO string | `id` (queried; written elsewhere) | 0 |
| `operator_suspensions` | 3 | r/admin_operator_management_routes.py | find, insert_one | created_at, operator_id, action, actioned_by, actioned_by_name, id, reason, duration_days | ISO string | `id` UUID string | 0 |
| `pan_verifications` | 3 | r/verification_gst_pan_routes.py | find_one, update_one | pan, source, verified, verified_at | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `payment_otps` | 3 | r/finance_advanced_routes.py | find_one, insert_one, update_one | used, bill_id, otp, _id, created_at, expires_at | BSON Date | `_id` used in filters | 0 |
| `pincode_cache` | 3 | r/pincode_live_routes.py | find, find_one, update_one | pincode, latitude, longitude, area, state, district, division, post_offices | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `pricing_audit_logs` | 3 | r/pricing_engine_routes.py | find, insert_one | timestamp, action, user_id, changes, commission_percent, key, override_type, user_email | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `referral_history` | 3 | r/referral_routes.py | find, insert_one | created_at, referrer_id, status, bonus_amount, booking_amount, booking_id, id, referred_id | ISO string | `id` UUID string | 0 |
| `refund_requests` | 3 | r/customer_routes.py | find, insert_one, update_one | created_at, customer_id, id, status, booking_id, cancellation_fee, original_amount, payment_id | ISO string | `id` UUID string | 0 |
| `refunds` | 3 | r/finance_treasury_routes.py, r/invoice_routes.py | find, insert_one | status, created_at, amount, created_by, customer_id, customer_name, id, invoice_id | ISO string | `id` UUID string | 0 |
| `reminder_configs` | 3 | r/finance_phase4_routes.py | find, update_one | challan_type, is_active, created_at, days_before, email_enabled, id, recipients, updated_at | BSON Date | `id` UUID string | 0 |
| `route_pricing` | 3 | r/pricing_engine_routes.py, s/pricing_engine.py | find, find_one, update_one | is_active, route_from, route_to | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `sessions` | 3 | db_optimization.py, scheduler.py | delete_many, index_spec | created_at | unknown | `_id` ObjectId only (ASSUMPTION) | 2 |
| `stripe_balance_transactions` | 3 | r/finance_scheduled_routes.py, scheduler.py | count_documents, find_one, insert_one | txn_id, amount, available_on, created_at, currency, fee, id, net | BSON Date | `id` UUID string | 0 |
| `tds_config` | 3 | s/approval_workflow.py | find_one, update_one | id, updated_at, custom_rates, updated_by | ISO string | `id` (queried; written elsewhere) | 0 |
| `tds_entries` | 3 | r/payment_gateway_routes.py | find, insert_one | quarter, financial_year, batch_id, created_at, entries, id, total_tds, vendor_count | ISO string | `id` UUID string | 0 |
| `terms_agreements` | 3 | r/settings_routes.py, r/verification_routes.py | count_documents, find, insert_one | user_type, agreed_at, agreed_insurance, agreed_privacy, agreed_terms, email, email_verification_id, email_verified | ISO string | `id` UUID string | 0 |
| `testimonials` | 3 | r/content_routes.py | delete_one, find, insert_one | created_at, id, created_by | ISO string | `id` custom string | 0 |
| `ai_logs` | 2 | r/ai_routes.py | insert_one | created_at, id, type, user_id, document_type, request, response, result | ISO string | `id` UUID string | 0 |
| `approval_settings` | 2 | r/admin_approval_routes.py | find_one, update_one | type, updated_at, updated_by | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `booking_templates` | 2 | r/multileg_booking_routes.py | find, insert_one | user_id, created_at, created_bookings, id, is_active, legs, next_booking_date | ISO string | `id` UUID string | 0 |
| `commission_tiers` | 2 | r/settings_routes.py | find, insert_one |  | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `consent_records` | 2 | r/legal_routes.py | find_one, insert_one | booking_id, user_id, accepted_at, id, ip_address, mandatory_consents, optional_consents, user_agent | BSON Date | `id` UUID string | 0 |
| `department_budgets` | 2 | r/corporate_routes.py | find, update_one | corporate_id, department, start_date, alert_threshold, alert_triggered, budget_amount, budget_used, created_at | BSON Date | `_id` ObjectId only (ASSUMPTION) | 0 |
| `document_alerts` | 2 | r/maintenance_routes.py | find, insert_one | pilot_id, sent_at, document_ids, expired_count, expiring_count, id, pilot_name, sent_by | ISO string | `id` UUID string | 0 |
| `exchange_images` | 2 | r/aviation_exchange_routes.py | find_one, insert_one | id, content_type, created_at, storage_path, uploaded_by | ISO string | `id` custom string | 0 |
| `forex_payments` | 2 | r/finance_phase5_routes.py | find, insert_one | created_at, description, exchange_rate, id, inr_amount, original_amount, original_currency, status | BSON Date | `id` UUID string | 0 |
| `generated_reports` | 2 | r/ai_reports_routes.py | find, insert_one | created_at, _id, date_range, generated_at, period, report_id, report_type | MIXED (ISO 1 / Date 1) | `_id` set by code (null) | 0 |
| `geofences` | 2 | r/field_tracking_routes.py | find, insert_one | active, address, created_at, created_by, id, latitude, longitude, name | ISO string | `id` UUID string | 0 |
| `gst_config` | 2 | r/gst_routes.py | find_one, update_one | id, updated_at, updated_by | ISO string | `id` custom string | 0 |
| `ip_geolocation_cache` | 2 | s/ip_geolocation_service.py | find_one, update_one | ip, fetched_at | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `ledger_entries` | 2 | r/accounting_routes.py | aggregate, insert_one | date, created_at, created_by, id | ISO string | `id` UUID string | 0 |
| `loans` | 2 | r/finance_treasury_routes.py | find | status, next_emi_date | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `maintenance_records` | 2 | r/predictive_maintenance_routes.py | find |  | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `operator_settlements` | 2 | r/finance_treasury_routes.py | find | status | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `partner_webhook_logs` | 2 | r/partner_routes.py | find, insert_one | created_at, partner_id, booking_id, error, event, id, status_code, success | ISO string | `id` UUID string | 0 |
| `pilot_feedback` | 2 | r/reports_routes.py | find | created_at, pilot_id | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `preflight_checks` | 2 | r/pilot_mobile_routes.py | find, insert_one | pilot_id, submitted_at, aircraft_registration, checked_count, completion_percentage, created_at, flight_id, id | ISO string | `id` custom string | 0 |
| `price_calculations` | 2 | r/pricing_engine_routes.py, s/pricing_engine.py | find, insert_one | created_at, audit_log, calculation_id, request, response_summary | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `razorpay_webhooks` | 2 | r/razorpay_routes.py | insert_one, update_one | processed, event, payload, payload.event, processed_at, received_at | BSON Date | `_id` ObjectId only (ASSUMPTION) | 0 |
| `reminder_logs` | 2 | r/finance_phase4_routes.py | find, insert_one | sent_at, amount, challan_id, challan_type, days_remaining, id, period, recipients | BSON Date | `id` UUID string | 0 |
| `review_helpful` | 2 | r/reviews_routes.py | find_one, insert_one | review_id, user_id, created_at | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `review_reports` | 2 | r/reviews_routes.py | find, insert_one | created_at, status, details, id, reason, reported_by, review_id | ISO string | `id` UUID string | 0 |
| `tally_ledgers` | 2 | r/tally_routes.py | find, insert_one | created_at, id, parent, status | ISO string | `id` UUID string | 0 |
| `terms_conditions` | 2 | r/settings_routes.py | find_one, update_one | type, last_updated, updated_by | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `user_currency_preferences` | 2 | r/currency_routes.py | find_one, update_one | user_id, preferred_currency, updated_at | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `accounting_connections` | 1 | r/accounting_routes.py | update_one | provider, api_key, company_id, connected_at, connected_by, id, is_active, settings | ISO string | `id` UUID string | 0 |
| `ai_finance_queries` | 1 | r/finance_phase4_routes.py | insert_one | created_at, query, response, session_id | BSON Date | `_id` ObjectId only (ASSUMPTION) | 0 |
| `balance_reminders` | 1 | r/admin_payments_routes.py | insert_one | amount, booking_id, customer_id, id, result, sent_at, sent_by | ISO string | `id` UUID string | 0 |
| `bulk_reminders` | 1 | r/admin_payments_routes.py | insert_one | failed, id, sent, sent_at, sent_by, total_pending | ISO string | `id` UUID string | 0 |
| `compliance_reminders` | 1 | r/compliance_monitor_routes.py | insert_one | alerts, alerts_count, id, operator_email, sent_at, status | ISO string | `id` UUID string | 0 |
| `counters` | 1 | r/razorpay_routes.py | find_one_and_update | _id, seq | unknown | `_id` used in filters | 0 |
| `crm_customers` | 1 | r/crm_routes.py | insert_one | city, company_name, converted_at, converted_by, created_at, email, id, lead_id | ISO string | `id` UUID string | 0 |
| `daily_reports` | 1 | scheduler.py | insert_one | date, generated_at, id, metrics | ISO string | `id` custom string | 0 |
| `emergency_contacts` | 1 | r/pilot_mobile_routes.py | find |  | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `gateway_config` | 1 | r/payment_gateway_routes.py | update_one | gateway, credentials_set, is_active, updated_at, updated_by | ISO string | `_id` ObjectId only (ASSUMPTION) | 0 |
| `hr_leave_requests` | 1 | r/ai_advisor_routes.py | count_documents | status | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `incentive_calculations` | 1 | r/hr_advanced_routes.py | find_one | employee_id, month, year | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `inventory_movements` | 1 | r/hangar_management_routes.py | insert_one | change, created_at, id, item_id, item_name, new_quantity, reason, user_id | ISO string | `id` custom string | 0 |
| `invoice_payments` | 1 | r/invoice_routes.py | insert_one | amount, id, invoice_id, payment_mode, recorded_at, recorded_by, reference | ISO string | `id` UUID string | 0 |
| `kb_feedback` | 1 | r/knowledge_routes.py | insert_one | article_id, comment, created_at, helpful, id, user_id | ISO string | `id` UUID string | 0 |
| `loyalty_points` | 1 | r/customer_routes.py | find_one | customer_id | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `marketing_content` | 1 | r/ai_advisor_routes.py | insert_one | campaign_theme, content_type, created_at, created_by, generated_content, id, target_audience | BSON Date | `id` custom string | 0 |
| `operator_inquiries` | 1 | r/booking_routes.py | insert_one | created_at, id, inquiry_id, operator_id, status | ISO string | `id` UUID string | 0 |
| `operator_payouts` | 1 | r/operator_routes.py | find | created_at, operator_id | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `overbooking_config` | 1 | r/inventory_routes.py | find_one | aircraft_id | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `payment_settlements` | 1 | r/finance_analytics_routes.py | find | created_at | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `point_redemptions` | 1 | r/loyalty_routes.py | insert_one | code, created_at, discount_value, expires_at, id, points_used, status, user_id | ISO string | `id` UUID string | 0 |
| `promo_usage` | 1 | r/marketing_routes.py | count_documents | promo_id, user_id | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `promo_vouchers` | 1 | r/ai_advisor_routes.py | count_documents | status | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `reconciliation_runs` | 1 | r/finance_reconciliation_routes.py | insert_one | created_at, errors, failed, gateway, id, matched, run_by, run_type | BSON Date | `id` UUID string | 0 |
| `rest_period_logs` | 1 | r/dgca_compliance_routes.py | insert_one | created_at, duration_hours, id, logged_by, meets_minimum | ISO string | `id` UUID string | 0 |
| `security_alerts` | 1 | security_middleware.py | insert_one | action, audit_log_id, id, ip_address, reviewed_at, reviewed_by, severity, status | unknown | `id` custom string | 0 |
| `sla_breaches` | 1 | r/admin_operator_management_routes.py | find | created_at, operator_id | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `stock_transactions` | 1 | r/maintenance_routes.py | insert_one | created_at, id, new_quantity, part_id, part_number, quantity_change, reason, updated_by | ISO string | `id` UUID string | 0 |
| `stripe_payments` | 1 | r/finance_reconciliation_routes.py | find_one | payment_intent_id | unknown | `_id` ObjectId only (ASSUMPTION) | 0 |
| `vendor_payments` | 1 | r/finance_advanced_routes.py | insert_one | amount, approved_at, bill_id, created_at, id, payment_mode, remarks, scheduled_date | MIXED (ISO 1 / Date 2) | `id` UUID string | 0 |
| `whatsapp_logs` | 1 | s/inquiry_broadcast_service.py | insert_one | created_at, id, inquiry_id, mapping_id, message_preview, operator_id, status, to_number | ISO string | `id` UUID string | 0 |
