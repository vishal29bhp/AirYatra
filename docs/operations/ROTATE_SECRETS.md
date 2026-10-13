# Rotate secrets

All runtime secrets live in Key Vault (`$KV`). The secret name is the env var name in lowercase with dashes, for example
`RAZORPAY_KEY_SECRET` becomes `razorpay-key-secret`. Both container apps reference the **versionless** secret id, so a
new version is picked up when the apps restart. Key Vault keeps every old version (soft delete and purge protection are on).

**Rotating live payment keys needs Vishal's written approval first (Constraint 9).** Rotate every key once at cutover,
then on the schedule below, and at once whenever one may have leaked.

## Standard rotation (third-party keys)

1. Create the new key at the provider. Keep the old one active.
2. Store it:
   ```bash
   az keyvault secret set --vault-name $KV --name <secret-name> --value '<new value>' -o none
   ```
3. Restart both apps so they read the new version:
   ```bash
   for app in $API $WORKER; do
     rev=$(az containerapp show -n $app -g $RG --query properties.latestRevisionName -o tsv)
     az containerapp revision restart -n $app -g $RG --revision $rev
   done
   ```
4. Check the feature that uses the key. For payments, run a test-mode order. Also check webhooks (see below).
5. Revoke the old key at the provider.

| Secret | Provider | Rotate every | Notes |
|---|---|---|---|
| `razorpay-key-id` / `razorpay-key-secret` | Razorpay dashboard | 12 months | Payment orders and refunds |
| `razorpay-webhook-secret` | Razorpay, Webhooks | 12 months | Set the same value on the webhook in the dashboard **in the same minute**; webhooks signed with the old secret fail with 400 until both match |
| `razorpayx-*` | RazorpayX | 12 months | Payouts; maker-checker still applies |
| `stripe-api-key` / `stripe-webhook-secret` | Stripe, Developers | 12 months | Roll the webhook signing secret in Stripe, which keeps the old one valid for up to 24 h |
| `cashfree-client-id` / `cashfree-client-secret` | Cashfree | 12 months | |
| `twilio-account-sid` / `twilio-auth-token` | Twilio console | 12 months | Secondary auth token, then promote |
| `sendgrid-api-key` / `smtp-password` | SendGrid | 12 months | |
| `google-client-id` / `google-client-secret` | Google Cloud console | 12 months | |
| `openweather-api-key` | OpenWeather | 12 months | |

## Secrets Terraform generates

| Secret | How to rotate | Effect |
|---|---|---|
| `jwt-secret-key` | `terraform apply -replace=module.platform.random_password.jwt`, then restart both apps | **Every user is signed out**, because all issued tokens become invalid. Do it in a quiet hour and announce it. |
| `mongo-url` | `terraform apply -replace=module.platform.module.mongodb.random_password.app`. This updates the Atlas user and the secret together. Restart both apps straight after. | Requests fail until the restart finishes (a few seconds per replica) |

There are no other credentials:
- Redis, Blob storage, Azure OpenAI, ACR and Key Vault use managed identity.
- GitHub Actions uses OIDC.

## FILE_ENCRYPTION_KEY: do not rotate in place

`file-encryption-key` encrypts the KYC files at rest. Changing it makes every stored KYC file unreadable. It can only be
rotated with a re-encryption job: decrypt with the old key, re-encrypt with the new one, and verify with
`tools/migration/verify_files.py --decrypt-check`. That job does not exist yet. If this key leaks, treat it as a data
breach ([INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md)) and plan the re-encryption with Vishal.

## Roll back a secret

```bash
az keyvault secret list-versions --vault-name $KV --name <secret-name> -o table
az keyvault secret show --id <old version id> --query value -o tsv | \
  xargs -I{} az keyvault secret set --vault-name $KV --name <secret-name> --value '{}' -o none
```
Then restart both apps as in step 3.
