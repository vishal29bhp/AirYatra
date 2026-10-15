# AirYatra on Azure: Terraform

Infrastructure for the AirYatra platform, as designed in
[`docs/architecture/01-target-architecture.md`](../../docs/architecture/01-target-architecture.md).
Everything is in Central India (`centralindia`), with South India (`southindia`) for DR copies and Azure OpenAI.

> Nothing here has been applied to a real subscription. `terraform fmt`, `terraform validate` and
> Checkov pass for `bootstrap`, `envs/dev` and `envs/prod`. Applying is a manual step (below).

## Layout

| Path | What it is |
|---|---|
| `bootstrap/` | One-time state storage account (`rg-airyatra-tfstate-cin`). Local state. |
| `envs/dev/` | Dev: 1 API replica, Standard Front Door (WAF in Detection), Cosmos DB for MongoDB vCore M10, Managed Redis B0. |
| `envs/prod/` | Prod at stage 1 (~1K users): 2+ zone-redundant API replicas, Premium Front Door + WAF (Prevention) over Private Link, Atlas M10 with PITR and autoscale to M30, Managed Redis B1 HA, RA-GZRS blobs. |
| `modules/platform` | Composition used by every environment. |
| `modules/network` | VNet, `/23` Container Apps subnet, private endpoint subnet, NSGs, private DNS zones. |
| `modules/container_apps` | ACR, Container Apps environment, `api` app (HTTP + CPU autoscale) and single-replica `worker` app (APScheduler). |
| `modules/cosmos_mongo` | Azure Cosmos DB for MongoDB (vCore), private endpoint only. Needs no account outside Azure. |
| `modules/mongodb_atlas` | Atlas project and replica set on Azure Central India, continuous backup, Private Link, least-privilege app user. |
| `modules/storage` | Private Blob storage (uploads, documents, kyc, invoices, exports, WORM audit-logs), Defender malware scanning. |
| `modules/redis` | Azure Managed Redis, Entra auth only, private endpoint. |
| `modules/keyvault` | Key Vault (RBAC, purge protection), private endpoint, audit logs. |
| `modules/openai` | Azure OpenAI account and model deployments, keyless, private endpoint. |
| `modules/frontdoor` | Front Door, WAF (OWASP DRS 2.1, bot manager, rate limits, `/docs` blocked), security headers, SPA fallback, static web storage. |
| `modules/observability` | Log Analytics, Application Insights, action group, alerts (error rate, p95, payment webhooks, scheduler). |
| `modules/governance` | India-only location policy, monthly budget alerts, Defender for Cloud plans. |
| `modules/github_oidc` | Managed identity + federated credential so GitHub Actions deploys without secrets. |

## Prerequisites

- Terraform >= 1.9, Azure CLI, an Azure subscription where you are Owner (role assignments are created).
- Database: `database_engine` picks it. `cosmos_vcore` (dev default) needs nothing beyond the subscription. `atlas`
  (prod default) needs a MongoDB Atlas organisation and an Atlas **service account** (or API key) with Organization
  Project Creator.
- Your public IP, so Terraform can write Key Vault secrets through the vault firewall.

## Apply, step by step

For dev there is a fuller copy-paste walkthrough (bash and PowerShell), including GitHub and Key Vault setup:
[docs/operations/FIRST_DEPLOY_DEV.md](../../docs/operations/FIRST_DEPLOY_DEV.md).

```bash
az login
az account set --subscription <SUBSCRIPTION_ID>

# 1. State storage (once)
cd infra/terraform/bootstrap
terraform init
terraform apply -var subscription_id=<SUBSCRIPTION_ID>
terraform output -raw backend_config      # paste into envs/<env>/backend.hcl, plus key = "airyatra-<env>.tfstate"

# 2. Environment (dev first, then prod)
cd ../envs/dev
cp backend.hcl.example backend.hcl            # fill from step 1
cp terraform.tfvars.example terraform.tfvars  # subscription, alert email, your IP/32 (+ Atlas org id on atlas)
# Atlas only: export MONGODB_ATLAS_CLIENT_ID=... MONGODB_ATLAS_CLIENT_SECRET=...  (never in tfvars)
terraform init -backend-config=backend.hcl
git add .terraform.lock.hcl                   # commit the lock file this creates
terraform plan -out tfplan
terraform apply tfplan
```

### After the first apply

1. **Set the real secrets in Key Vault.** Terraform creates every third-party secret as `set-me` and never touches it
   again. Set each one (names are the env var in lowercase with dashes):
   ```bash
   KV=$(terraform output -raw key_vault_uri | sed 's#https://##; s#.vault.azure.net/##')
   az keyvault secret set --vault-name $KV --name razorpay-key-id --value '<value>'
   ```
   **`file-encryption-key` must be the exact `FILE_ENCRYPTION_KEY` the current Emergent deployment uses.** The KYC
   files already stored were encrypted with it; a new key would make them unreadable.
2. **Prod only, approve the Front Door Private Link connection** on the Container Apps environment
   (Portal: Container Apps environment, Networking, Private endpoint connections, Approve), or:
   ```bash
   az network private-endpoint-connection list --id <container-apps-environment-id>
   az network private-endpoint-connection approve --id <connection-id>
   ```
3. **Custom domain** (optional): add `custom_domains` in tfvars, apply, then create the `_dnsauth` TXT records from
   `terraform output custom_domain_validation_tokens` and a CNAME to `terraform output frontdoor_endpoint`.
4. **GitHub Actions**: create GitHub environments `dev` and `prod` (add yourself as a required reviewer on `prod`)
   and add every entry of `terraform output github_actions_variables` as an environment variable. No client secret
   is needed. Deploys then run from the **Deploy to Azure** workflow ([docs/operations/DEPLOY.md](../../docs/operations/DEPLOY.md)).
5. Restart the container apps so they pick up the new secret values:
   `az containerapp revision restart` (or deploy a new image).

## Scale from 1K to 20K users

Change values in `envs/prod/main.tf`, `plan`, `apply`. No module changes:

| Setting | Stage 1 (1K) | Stage 2 (20K) |
|---|---|---|
| `api_min_replicas` / `api_max_replicas` | 2 / 6 | 3 / 20 |
| `api_cpu` / `api_memory` | 1 / 2Gi | 2 / 4Gi |
| `atlas_instance_size` / autoscale max | M10 / M30 | M30 / M50 |
| `atlas_dr_node_enabled` | false | true (electable node in South India) |
| `redis_sku_name` | Balanced_B1 | Balanced_B5 |
| `openai_deployments.capacity` | 30 | 100 |

## Destroying

Use [`infra/scripts/teardown.ps1`](../scripts/teardown.ps1), not a bare `terraform destroy`. It runs `terraform destroy`
for one environment with guard rails:

- It plans first and stops, before deleting anything, if any planned change is not a delete or any resource is outside
  the environment's own resource group (`rg-airyatra-<env>-...`). Other projects on the subscription are never touched.
- You type `destroy airyatra-<env>` to go ahead. Prod also needs `-ConfirmProduction` and the Atlas credentials.
- Subscription-wide Defender for Cloud plans (prod turns them on) stay on unless you pass `-DisableDefenderPlans`,
  because they cover every project on the subscription.
- Key Vault secrets and the static website setting are dropped from state and go with their parent, so the teardown
  does not need to reach Key Vault through its firewall.
- Prod: Atlas termination protection is turned off on the cluster just before the destroy
  (`atlas_termination_protection` defaults to `true` and nothing else sets it).
- `-RemoveGitHubEnvironment` also deletes the GitHub environment. `-RemoveStateStorage` also deletes the state storage
  account, only when every state file in it is empty. `-PlanOnly` checks and lists, deleting nothing.

```powershell
.\infra\scripts\teardown.ps1 -Environment dev -SubscriptionId <id> -PlanOnly   # see what would go
.\infra\scripts\teardown.ps1 -Environment dev -SubscriptionId <id>
```

What remains afterwards: Key Vault keeps the deleted vault for 90 days (purge protection; `az keyvault recover --name
<vault>` brings the keys back). The database and blob files are gone for good; for prod, Atlas backups go with the
cluster, so download a snapshot first. Do not tear down prod without a verified backup.

## Checks run

```bash
terraform fmt -check -recursive
(cd envs/dev && terraform init -backend=false && terraform validate)
(cd envs/prod && terraform init -backend=false && terraform validate)
checkov -d . --framework terraform     # 0 failed; each skip carries its reason inline
```
