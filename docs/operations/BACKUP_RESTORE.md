# Backup and restore

Targets: **RPO 15 minutes, RTO 4 hours** (master prompt Phase 5).

## What is backed up

| Data | Backup | Retention | Point-in-time |
|---|---|---|---|
| MongoDB (Atlas) | Continuous cloud backup, snapshots every 6 h and daily | 6-hourly 7 days, daily 35 days | Yes, any second in the last 7 days (prod) |
| Blob (`uploads`, `documents`, `kyc`, `invoices`, `exports`) | Versioning, 30-day soft delete for blobs and containers, RA-GZRS copy in South India | 30 days | Restore any version |
| Blob `audit-logs` | WORM (immutable) | Per the DPDP retention schedule | Cannot be changed or deleted |
| Key Vault | Soft delete and purge protection | 90 days | Every version kept |
| Container images | ACR, tagged by git SHA | Tagged images kept | n/a |
| Web build | Rebuilt from git; 7-day soft delete on `$web` | | |
| Redis | Not backed up: it only holds rate limits, cache and chat fan-out, which rebuild on their own | | |

## Restore MongoDB

**Restoring overwrites data, so it needs Vishal's written approval first.** Prefer restoring to a **new** cluster and copying back only
what is needed. Restore over the live cluster only when the whole database is lost.

1. Pick the restore time, just before the bad write or outage.
2. Atlas, the cluster, Backup, Restore, Point in Time. Choose the time, then restore to a new cluster in the same project
   (for example `airyatra-prod-restore`).
3. Compare it with the live data:
   ```bash
   export SOURCE_MONGO_URL='<restore uri>' TARGET_MONGO_URL='<live uri>'   # read-only; never paste into files
   python tools/migration/verify_migration.py --source-db airyatra_db --target-db airyatra_db --mode counts
   ```
4. Then either:
   - **Partial:** export the affected documents from the restore with `mongoexport` and a query, and import them into
     the live cluster.
   - **Full:** point `mongo-url` in Key Vault at the restored cluster (`az keyvault secret set ...`) and restart both
     apps ([ROTATE_SECRETS.md](ROTATE_SECRETS.md)). Afterwards, bring the restored cluster under Terraform or swap it
     back during a maintenance window.
5. Delete the temporary cluster when it is no longer needed. That deletion also needs approval.

## Restore files

```bash
# A deleted blob, inside the soft-delete window
az storage blob undelete --auth-mode login --account-name <data account> -c documents -n <blob name>
# An earlier version of an overwritten blob
az storage blob list --auth-mode login --account-name <data account> -c documents --prefix <name> --include v -o table
az storage blob copy start --auth-mode login --account-name <data account> -c documents -b <name> \
  --source-uri "https://<data account>.blob.core.windows.net/documents/<name>?versionid=<version id>"
```
If Central India is lost, Microsoft can fail the account over to South India (RA-GZRS). You can also start the failover
yourself: Storage account, Redundancy, Prepare for failover.

## Quarterly restore test (proves the RTO)

1. Restore the latest prod snapshot to a temporary cluster and time the restore.
2. Run `verify_migration.py --mode counts` (restore as source, prod as target) and record the result.
3. Point the `dev` environment at the restore, sign in and open one booking.
4. Record the start time, the end time and any problems in the release checklist. Delete the temporary cluster.
