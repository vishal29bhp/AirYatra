# First deploy of the dev (test) environment

Run these steps once from your own machine, in the VS Code terminal, from the root of this repository. After that,
every release goes through the **Deploy to Azure** workflow ([DEPLOY.md](DEPLOY.md)).

The database is Azure Cosmos DB for MongoDB (vCore), which Terraform creates, so you need no MongoDB Atlas account.

Dev runs without Azure Front Door by default, because Azure Free Trial subscriptions cannot create it. The site is
then served straight from its storage account and the browser calls the API at its own address, with no WAF or edge
security headers. After upgrading the subscription to Pay-As-You-Go, add `frontdoor_enabled = true` to
`infra/terraform/envs/dev/terraform.tfvars` and run the script again.

Dev also runs the API on Azure App Service (one B1 web app that runs the API and the scheduler) instead of Container
Apps, because a Free Trial subscription allows only one Container Apps environment and that may already be used by
another project. Dev lives in South India for the same reason. Prod keeps Container Apps.
No secret goes into a file, the repo, GitHub or chat: keys are typed straight into Key Vault in step 8.

The dev database starts empty, so step 8 also generates one password for the staff logins listed in
`bootstrap_staff` (`infra/terraform/envs/dev/main.tf`) and shows it once on your screen. The API creates those
accounts when it starts and never changes an existing user. Prod never does this.

Each step has a **bash** block (macOS, Linux, Git Bash on Windows) and a **PowerShell** block (the default VS Code
terminal on Windows). Use the same shell for every step, because later steps reuse variables from earlier ones. If you
open a new terminal, run step 1 again first.

If any command fails, paste the error (never a key) in the project thread and stop there.

## Quickest way: one PowerShell script

[`infra/scripts/deploy-dev.ps1`](../../infra/scripts/deploy-dev.ps1) does steps 1 to 9 below for you. It asks you to
confirm before creating anything in Azure, and asks for each key with hidden typing (Enter skips a key). From the
repository root, in the VS Code PowerShell terminal:

```powershell
git pull
powershell -ExecutionPolicy Bypass -File .\infra\scripts\deploy-dev.ps1 -SubscriptionId <your-subscription-id> -AlertEmail <your-email>
```

It is safe to run again. `-KeysOnly` goes straight to entering keys, `-SkipKeys` and `-SkipDeploy` leave those steps
out. The steps below are the same thing done by hand.

## 0. Tools

You need the Azure CLI (you have it), Terraform 1.9 or newer, and the GitHub CLI.

```powershell
# Windows
winget install Hashicorp.Terraform
winget install GitHub.cli
```

```bash
# macOS
brew install terraform gh jq
```

Then close and reopen the VS Code terminal, and check:

```bash
terraform -version    # 1.9 or newer
az version
gh --version
```

## 1. Sign in and set your details

Replace the subscription ID and email with your own.

```bash
SUB="<your-subscription-id>"
ALERT_EMAIL="<your-alert-email>"
az login
az account set --subscription "$SUB"
gh auth login         # GitHub.com, HTTPS, log in with a web browser
```

```powershell
$SUB = "<your-subscription-id>"
$ALERT_EMAIL = "<your-alert-email>"
az login
az account set --subscription $SUB
gh auth login
```

Check you are **Owner** on the subscription (Terraform creates role assignments). This must print `Owner`:

```bash
az role assignment list --all --assignee "$(az ad signed-in-user show --query id -o tsv)" \
  --query "[?contains(scope, '$SUB')].roleDefinitionName" -o tsv
```

```powershell
$me = az ad signed-in-user show --query id -o tsv
az role assignment list --all --assignee $me --query "[?contains(scope, '$SUB')].roleDefinitionName" -o tsv
```

## 2. Turn on the Azure services AirYatra uses (once per subscription)

```bash
for p in Microsoft.App Microsoft.ContainerRegistry Microsoft.DocumentDB Microsoft.Cache Microsoft.KeyVault \
         Microsoft.CognitiveServices Microsoft.Cdn Microsoft.Network Microsoft.Storage \
         Microsoft.OperationalInsights Microsoft.Insights Microsoft.ManagedIdentity Microsoft.Security \
         Microsoft.LoadTestService Microsoft.PolicyInsights Microsoft.Consumption; do
  az provider register --namespace "$p" --wait
done
```

```powershell
"Microsoft.App","Microsoft.ContainerRegistry","Microsoft.DocumentDB","Microsoft.Cache","Microsoft.KeyVault",
"Microsoft.CognitiveServices","Microsoft.Cdn","Microsoft.Network","Microsoft.Storage",
"Microsoft.OperationalInsights","Microsoft.Insights","Microsoft.ManagedIdentity","Microsoft.Security",
"Microsoft.LoadTestService","Microsoft.PolicyInsights","Microsoft.Consumption" |
  ForEach-Object { az provider register --namespace $_ --wait }
```

## 3. Get the latest code

```bash
git checkout main
git pull
```

## 4. Create the Terraform state storage (once)

```bash
cd infra/terraform/bootstrap
terraform init
terraform apply -var "subscription_id=$SUB"      # type yes
terraform output -raw backend_config > ../envs/dev/backend.hcl
echo 'key = "airyatra-dev.tfstate"' >> ../envs/dev/backend.hcl
cd ../envs/dev
```

```powershell
cd infra/terraform/bootstrap
terraform init
terraform apply -var "subscription_id=$SUB"      # type yes
terraform output -raw backend_config | Out-File -Encoding ascii ../envs/dev/backend.hcl
'key = "airyatra-dev.tfstate"' | Out-File -Encoding ascii -Append ../envs/dev/backend.hcl
cd ../envs/dev
```

The bootstrap keeps its own small state file in `infra/terraform/bootstrap/terraform.tfstate` on your machine.
It is git-ignored. Keep it; don't delete the folder.

## 5. Settings for the dev environment

This writes `terraform.tfvars` (git-ignored) with your subscription, alert email and current public IP. The IP lets
Terraform, and you in step 8, write to Key Vault through its firewall.

```bash
MYIP=$(curl -s https://api.ipify.org)
cat > terraform.tfvars <<EOF
subscription_id   = "$SUB"
alert_email       = "$ALERT_EMAIL"
deployer_ip_cidrs = ["$MYIP/32"]
budget_start_date = "2026-11-01T00:00:00Z"
EOF
cat terraform.tfvars
```

```powershell
$MYIP = (Invoke-RestMethod https://api.ipify.org)
@"
subscription_id   = "$SUB"
alert_email       = "$ALERT_EMAIL"
deployer_ip_cidrs = ["$MYIP/32"]
budget_start_date = "2026-11-01T00:00:00Z"
"@ | Out-File -Encoding ascii terraform.tfvars
Get-Content terraform.tfvars
```

If your IP changes later (another network, router restart) and step 8 says "Forbidden" or "client address is not
authorized", run this step and step 6 again.

## 6. Create the environment

```bash
terraform init -backend-config=backend.hcl
terraform plan -out dev.tfplan   # the last line reads "Plan: N to add, 0 to change, 0 to destroy"
terraform apply dev.tfplan       # takes a while: Front Door, Redis and the database are slow to create
```

`terraform init` writes `.terraform.lock.hcl`. Leave it uncommitted for now.

## 7. Connect GitHub to the environment (no secrets involved)

This creates the GitHub environment `dev` and adds the values the deploy workflow needs. None of them is secret;
GitHub signs in to Azure with OIDC.

```bash
gh api -X PUT repos/vishal29bhp/AirYatra/environments/dev > /dev/null
terraform output -json github_actions_variables | jq -r 'to_entries[] | "\(.key)\t\(.value)"' |
  while IFS=$'\t' read -r k v; do gh variable set "$k" --env dev --body "$v" --repo vishal29bhp/AirYatra; done
gh variable list --env dev --repo vishal29bhp/AirYatra
```

```powershell
gh api -X PUT repos/vishal29bhp/AirYatra/environments/dev | Out-Null
$vars = terraform output -json github_actions_variables | ConvertFrom-Json
$vars.PSObject.Properties | ForEach-Object { gh variable set $_.Name --env dev --body $_.Value --repo vishal29bhp/AirYatra }
gh variable list --env dev --repo vishal29bhp/AirYatra
```

The list should show `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, ... `PUBLIC_URL` and `API_URL`.

## 8. Put the keys into Key Vault

Use **test-mode** keys only (Razorpay `rzp_test_...`, Stripe `sk_test_...`, Cashfree sandbox). The helper asks for
each value without showing it and without saving it anywhere.

```bash
KV=$(terraform output -raw key_vault_uri | sed 's#https://##; s#.vault.azure.net/##')
set_secret() { read -rsp "$1: " v; echo; az keyvault secret set --vault-name "$KV" --name "$1" --value "$v" -o none && echo "saved $1"; unset v; }

# Required: the key that encrypts uploaded KYC files. The dev database starts empty, so a fresh key is right.
az keyvault secret set --vault-name "$KV" --name file-encryption-key -o none \
  --value "$(python3 -c 'import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())')" && echo "saved file-encryption-key"
```

```powershell
$KV = ((terraform output -raw key_vault_uri) -replace 'https://','') -replace '.vault.azure.net/',''
function set_secret($name) {
  $s = Read-Host "$name" -AsSecureString
  $v = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
  az keyvault secret set --vault-name $KV --name $name --value $v -o none; if ($?) { "saved $name" }
  Remove-Variable v
}

# Required: the key that encrypts uploaded KYC files. The dev database starts empty, so a fresh key is right.
$bytes = New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$fek = [Convert]::ToBase64String($bytes).Replace('+','-').Replace('/','_')
az keyvault secret set --vault-name $KV --name file-encryption-key --value $fek -o none; if ($?) { "saved file-encryption-key" }
Remove-Variable fek
```

Then run `set_secret <name>` for each key you have. Skip any you don't have yet: that feature stays off until its key
is set.

| Run | What to paste | Where to find it |
|---|---|---|
| `set_secret razorpay-key-id` | Key Id (`rzp_test_...`) | Razorpay Dashboard, Test Mode, Account & Settings, API Keys |
| `set_secret razorpay-key-secret` | Key Secret | same place |
| `set_secret razorpay-webhook-secret` | A strong value you choose; enter the same one on the webhook below | Razorpay, Webhooks |
| `set_secret razorpayx-key-id`, `razorpayx-key-secret`, `razorpayx-account-number` | Payout keys and account number | RazorpayX dashboard |
| `set_secret stripe-api-key` | `sk_test_...` | Stripe Dashboard, Developers, API keys |
| `set_secret stripe-webhook-secret` | `whsec_...` | Stripe, Developers, Webhooks |
| `set_secret cashfree-client-id`, `cashfree-client-secret` | Sandbox app id and secret | Cashfree dashboard |
| `set_secret twilio-account-sid`, `twilio-auth-token` | Account SID and auth token | Twilio Console |
| `set_secret sendgrid-api-key` or `set_secret smtp-password` | Email sending key | SendGrid, or your mail provider |
| `set_secret google-client-id`, `google-client-secret` | OAuth client | Google Cloud Console, APIs & Services, Credentials |
| `set_secret openweather-api-key` | API key | openweathermap.org, API keys |

Addresses to register with the providers (`terraform output -raw api_url` prints the base URL):

- Razorpay webhook: `<api_url>/api/razorpay/webhook`
- Google OAuth redirect URI: `<api_url>/api/auth/google/callback`

Azure OpenAI, Blob storage, Redis and the database need no keys: Terraform created them, and the app signs in to them
with its managed identity.

## 9. First deploy

GitHub, **Actions**, **Deploy to Azure**, **Run workflow**: environment `dev`, leave `image_tag` empty. Or:

```bash
gh workflow run azure-deploy.yml --repo vishal29bhp/AirYatra -f environment=dev
```

When it finishes, open the address printed by `terraform output -raw public_url`.
