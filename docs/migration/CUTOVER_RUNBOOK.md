# Data Migration and Cutover Runbook

How AirYatra's data moves from the current Emergent deployment to Azure with **zero data change**
(master prompt Phase 2), how we prove it, and how we roll back. The flow is diagram
[H7](../architecture/02-sequence-diagrams-high-level.md#h7-data-migration-and-cutover).

Nothing in this runbook is run without Vishal's go-ahead. The steps marked **APPROVAL** need his written
approval in the project thread (master prompt Constraint 9).

## What moves

| Data | From | To | Verified by |
|---|---|---|---|
| MongoDB database (285 collections) | Emergent MongoDB | Atlas cluster `airyatra-prod` (Central India, Private Link) | `tools/migration/verify_migration.py` |
| Public uploads | `/app/uploads/**` | Blob container `uploads` | `tools/migration/verify_files.py` |
| KYC files (encrypted `.enc`) | `/app/secure_uploads/kyc/**` | Blob container `kyc` | `verify_files.py --decrypt-check` |
| Pilot documents | `/app/secure_uploads/pilot_documents/**` | Blob container `documents` | `verify_files.py` |
| Document vault and exchange images | Emergent object store (`services/storage_service.py`), keys in `storage_path` / `thumb_storage_path` of `documents_vault`, `document_files`, `exchange_images` | Blob container `documents`, **same key as blob name** so stored paths stay unchanged | object copy tool (ships with the Phase 3b storage adapter) |
| `FILE_ENCRYPTION_KEY` | Emergent environment | Key Vault secret `file-encryption-key` | decrypt check above |

Allowed changes are additive only: new indexes and the write concern (`w: "majority"`, `journal: true`,
already in `backend/database.py`). No field renames, type changes, merges or value rewrites.

## Gates before the first rehearsal

1. Terraform `prod` applied (see [infra/terraform/README.md](../../infra/terraform/README.md)) and the Atlas
   major version set to the source's major version (`atlas_mongo_major_version`).
2. Phase 3b shipped: the app reads and writes files through the Blob storage adapter. Until then uploads
   would land on a container's temporary disk and be lost on restart, so **cutover cannot happen before it**.
3. The object-store copy tool from Phase 3b: it reads every `storage_path` above, copies each object from the
   Emergent object store to Blob under the same name and compares SHA-256. Needs the current `EMERGENT_LLM_KEY` (it also unlocks the object store),
   which is lost when the Emergent account closes, so this copy must finish before then.
4. Read access to the source database: a `mongodump`-capable connection string from Emergent
   (`ASSUMPTION`: Emergent can provide one, or a full export with `_id`s and BSON types intact).
5. A migration host inside the Azure VNet (a temporary VM or Container Apps job) with `mongodump`,
   `mongorestore` (Database Tools 100.9+), `azcopy` 10 and Python 3.11. Atlas and Blob have no public
   access, so the copy must run from inside the network.
6. A temporary Atlas database user with the `restore` role for the copy, deleted after cutover.
   The app's own user stays `readWrite` only.

## Environment on the migration host

```bash
export SOURCE_MONGO_URL='mongodb://...'            # Emergent, read-only user
export TARGET_RESTORE_URL='mongodb+srv://...'       # Atlas, temporary restore user
export TARGET_MONGO_URL="$TARGET_RESTORE_URL"       # used by the verifier (it only reads)
export SOURCE_DB=airyatra TARGET_DB=airyatra        # DB_NAME on each side
export STORAGE=$(terraform -chdir=infra/terraform/envs/prod output -raw data_storage_account_name)
export KV=$(terraform -chdir=infra/terraform/envs/prod output -raw key_vault_uri | sed 's#https://##; s#.vault.azure.net/##')
```

Connection strings stay in environment variables, never on the command line or in files.

## Rehearsal (repeat until clean, at least once a week before cutover)

```bash
# 1. Dump the source (read-only)
mongodump --uri "$SOURCE_MONGO_URL" --db "$SOURCE_DB" --archive=airyatra.archive.gz --gzip

# 2. Restore into Atlas, replacing any previous rehearsal copy (the target holds no live data yet)
mongorestore --uri "$TARGET_RESTORE_URL" --archive=airyatra.archive.gz --gzip \
  --nsFrom "$SOURCE_DB.*" --nsTo "$TARGET_DB.*" --drop --preserveUUID \
  --writeConcern '{w:"majority"}' --numInsertionWorkersPerCollection 4

# 3. Verify every collection: counts, SHA-256 of all documents in _id order, index parity
python3 tools/migration/verify_migration.py --source-db "$SOURCE_DB" --target-db "$TARGET_DB" \
  --mode full --json db-report.json --markdown db-report.md

# 4. Copy files, then download the copy and verify it, including KYC decryption with the Key Vault key
azcopy login --identity
azcopy copy '/app/uploads/*' "https://$STORAGE.blob.core.windows.net/uploads" --recursive --put-md5
azcopy copy '/app/secure_uploads/kyc/*' "https://$STORAGE.blob.core.windows.net/kyc" --recursive --put-md5
azcopy copy '/app/secure_uploads/pilot_documents/*' "https://$STORAGE.blob.core.windows.net/documents" --recursive --put-md5
mkdir -p check/kyc && azcopy copy "https://$STORAGE.blob.core.windows.net/kyc/*" check/kyc --recursive --check-md5 FailIfDifferent
FILE_ENCRYPTION_KEY="$(az keyvault secret show --vault-name "$KV" -n file-encryption-key --query value -o tsv)" \
  python3 tools/migration/verify_files.py --source /app/secure_uploads/kyc --target check/kyc --decrypt-check
# repeat verify_files.py (without --decrypt-check) for uploads and documents
# then run the Phase 3b object-store copy and check for documents_vault, document_files and exchange_images
rm -rf check   # never leave decrypted-capable copies or KYC files on the host
```

5. Point the **dev** environment at the copy and run the read-only regression smoke pack (login, search,
   price estimate, booking list and detail, invoices, operator and admin dashboards). No writes.
6. Record how long each step took. The freeze window is sized from these timings plus 50%.

A rehearsal passes only if both reports say **PASS**: every collection matches (extra *new* indexes on
the target are allowed), every file matches, and every KYC file decrypts.

`--mode sample --sample-size 5000` gives a quick check during long copies; the final check is always `--mode full`.

## Cutover day

| Step | Who | Action |
|---|---|---|
| T-48h | Vishal | **APPROVAL** for the window; customers and operators told about the maintenance window |
| T-24h | Claude | Lower the DNS TTL for `airyatra.com` to 300 s |
| T-0 | Vishal | Maintenance banner on, writes frozen on Emergent, Emergent scheduler stopped |
| T+5m | Claude | Final `mongodump`, `mongorestore`, `verify_migration.py --mode full` (must PASS) |
| T+… | Claude | Final file copy with `azcopy sync --put-md5`, `verify_files.py` (must PASS) |
| T+… | Claude | Additive indexes (Phase 3b index fix), then readiness check `GET /api/health/ready` |
| T+… | Claude | Smoke tests through the Front Door URL with test accounts |
| Go/no-go | Vishal | **APPROVAL**: switch DNS for `airyatra.com` to Front Door |
| +1h | Claude | Watch App Insights alerts, error rate, payment webhooks, scheduler run log |
| +24h | Vishal | Delete the temporary restore user and migration host, keep the Emergent copy read-only for 30 days |

Keys are rotated at cutover (Razorpay, Stripe, Cashfree, Twilio, SendGrid, Google OAuth, LLM), since the old ones
were exposed in git history. Rotation of live payment keys is a Constraint 9 step and needs Vishal's approval.

## Rollback

- **Before the DNS switch:** abort. Emergent is untouched; lift the freeze and the banner.
- **After the DNS switch, no customer writes yet:** point DNS back to Emergent and unfreeze.
- **After the DNS switch, with new writes on Azure:** freeze again, dump Atlas with the same commands in
  reverse (`SOURCE` = Atlas, `TARGET` = Emergent), verify with `verify_migration.py`, then point DNS back.
  Payments captured on Azure are reconciled from the Razorpay dashboard before reopening.

Decide go or rollback within 4 hours of the switch (RTO target).

## Tools

| Tool | Proves | Tests |
|---|---|---|
| [`verify_migration.py`](../../tools/migration/verify_migration.py) | Same collections, counts, byte-identical documents (types, values, field order), source indexes present on target | `tools/migration/test_verify_migration.py` |
| [`verify_files.py`](../../tools/migration/verify_files.py) | Same files with the same SHA-256; KYC files decrypt with the Key Vault key | `tools/migration/test_verify_files.py` |

Both only read. Exit code 0 means pass, 1 means a mismatch, so they can gate a pipeline step.
