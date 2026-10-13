# Incident response

## Severity

| Sev | Example | Respond within | Who is told |
|---|---|---|---|
| 1 | Site down, payments failing, data exposed, SOS not delivered | 15 min, around the clock | Vishal at once; affected users when the cause is known |
| 2 | One feature broken (chat, KYC upload, payouts), p95 over 1.5 s | 1 h in business hours | Vishal |
| 3 | Minor bug, single-user problem | Next business day | Ticket |

## Alerts (action group `ag-airyatra-<env>-cin`, e-mail from `alert_email`)

| Alert | Means | First move |
|---|---|---|
| `api-error-rate` | More than 1% of API requests failed in 5 minutes | Application Insights, Failures: find the failing operation and exception. Was there a deploy in the last hour? If so, [roll back](ROLLBACK.md). |
| `api-latency-p95` | p95 over 1.5 s | Performance blade: slow dependency? Check Atlas (CPU, slow queries), Redis server load, replica count ([SCALE.md](SCALE.md)). |
| `payment-webhook-failures` | Razorpay/Stripe webhooks rejected or erroring | A 400 usually means a signature mismatch after a secret change ([ROTATE_SECRETS.md](ROTATE_SECRETS.md)). Payments can still be reconciled from the gateway dashboard. |
| `scheduler-job-failures` | A worker job failed | `az containerapp logs show -n $WORKER -g $RG --tail 200`. Check that exactly one worker replica runs. |
| Budget alert | Spend above plan | Azure Cost Management by resource; usually replica count or OpenAI usage. |
| Defender for Cloud | Threat or malware detection | Treat as a security incident (below). |

## First 15 minutes (any Sev 1)

1. Say in the project thread that you are on it and what you see.
2. Check whether the problem is the app or the platform:
   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' https://<public url>/health
   az containerapp revision list -n $API -g $RG -o table      # Running? Restarting?
   az containerapp logs show -n $API -g $RG --tail 100
   ```
   Also check Azure status (status.azure.com) and Atlas status (status.mongodb.com).
3. If there was a recent deploy, roll back first and investigate afterwards ([ROLLBACK.md](ROLLBACK.md)).
4. If one replica is stuck, restart the revision: `az containerapp revision restart -n $API -g $RG --revision <name>`.
5. Write down every action with its time. You will need them for the review.

## Security incident (suspected breach, leaked key, account takeover)

1. **Contain:**
   - Rotate the exposed secret ([ROTATE_SECRETS.md](ROTATE_SECRETS.md)). Live payment keys need Vishal's approval.
   - Revoke sessions by rotating `jwt-secret-key` if tokens may be stolen. This signs everyone out.
   - Block abusive IPs with a Front Door WAF custom rule.
   - Disable a compromised staff account (`status: inactive`).
2. **Preserve evidence:**
   - Do not delete logs.
   - Export the relevant Application Insights, Front Door WAF, Key Vault audit and Atlas access logs.
   - The `audit-logs` Blob container is immutable.
3. **Assess personal data:**
   - Work out whether KYC documents, phone numbers, e-mails or payment data were exposed.
   - Under India's DPDP Act, a personal-data breach must be reported to the Data Protection Board and to the affected
     people. Vishal decides on and sends the notices.
   - Card data never touches AirYatra (the gateways hold it). Still tell the gateway if their keys leaked.
4. **Recover:** fix the cause, deploy and verify.
5. **Review within 5 working days:** write the timeline, root cause, what worked and what did not, and the follow-up
   tickets. Add an abuse case to the regression pack (threat model, `docs/architecture/04-threat-model.md`).

## Dependencies and who to call

| Dependency | Status page / support |
|---|---|
| Azure (Container Apps, Front Door, Redis, Blob, Key Vault, OpenAI) | status.azure.com; Azure portal, Help + support |
| MongoDB Atlas | status.mongodb.com; Atlas support |
| Razorpay / RazorpayX | Razorpay dashboard support |
| Stripe | status.stripe.com |
| Twilio, SendGrid | status.twilio.com |
| Emergent (until decommissioned) | Emergent support; only needed for the legacy object store and LLM key |

## Drill

Run one Sev 1 drill per quarter on `dev`: break a deploy on purpose, page through the alert, roll back and time it. Record
it with the restore test in [BACKUP_RESTORE.md](BACKUP_RESTORE.md).
