<#
.SYNOPSIS
    First deploy of the AirYatra dev (test) environment to Azure, in one script.

.DESCRIPTION
    Does every step of docs/operations/FIRST_DEPLOY_DEV.md:
      1. Checks the tools (Azure CLI, Terraform, GitHub CLI) and signs you in.
      2. Checks you are Owner on the subscription.
      3. Turns on the Azure services AirYatra uses.
      4. Creates the Terraform state storage (once).
      5. Writes terraform.tfvars with your subscription, email and current IP.
      6. Shows the Terraform plan, asks you to confirm, and creates the environment.
      7. Creates the GitHub environment "dev" and adds its variables (none are secret).
      8. Generates the file encryption key and asks for each third-party key (input is hidden; Enter skips).
      9. Starts the "Deploy to Azure" workflow for dev.

    It is safe to run again: finished steps are skipped or are no-ops, and keys already set are kept unless you
    type a new value. No key is written to disk except briefly in your temp folder to hand it to the Azure CLI.

.EXAMPLE
    .\infra\scripts\deploy-dev.ps1 -SubscriptionId <your-subscription-id> -AlertEmail <your-email>

.EXAMPLE
    # Only re-enter keys, skipping everything before step 8
    .\infra\scripts\deploy-dev.ps1 -SubscriptionId <id> -AlertEmail <email> -KeysOnly
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $SubscriptionId,
    [Parameter(Mandatory = $true)] [string] $AlertEmail,
    [string] $Repo = "vishal29bhp/AirYatra",
    [string] $BudgetStartDate = "2026-11-01T00:00:00Z",
    # Your public IP; looked up automatically when left empty.
    [string] $DeployerIp = "",
    [switch] $KeysOnly,
    [switch] $SkipKeys,
    [switch] $SkipDeploy
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 3.0

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$TfRoot = Join-Path $RepoRoot "infra\terraform"
$BootstrapDir = Join-Path $TfRoot "bootstrap"
$DevDir = Join-Path $TfRoot "envs\dev"

function Write-Step([string] $Text) {
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

# Runs a native command and stops the script if it fails (PowerShell does not do this for .exe/.cmd on its own).
# Plain functions with $args, so flags such as -auto-approve pass straight through to the command.
function Invoke-Native {
    $exe = $args[0]; $rest = @($args | Select-Object -Skip 1)
    & $exe @rest
    if ($LASTEXITCODE -ne 0) { throw "'$exe $($rest -join ' ')' failed with exit code $LASTEXITCODE." }
}

# Same, but returns the command's output as one trimmed string.
function Get-NativeOutput {
    $exe = $args[0]; $rest = @($args | Select-Object -Skip 1)
    $out = & $exe @rest
    if ($LASTEXITCODE -ne 0) { throw "'$exe $($rest -join ' ')' failed with exit code $LASTEXITCODE." }
    return (($out | Out-String).Trim())
}

# Runs a command only to see whether it succeeds, hiding its output. Windows PowerShell 5.1 turns redirected
# stderr into terminating errors under ErrorActionPreference=Stop, so this relaxes it for the probe.
function Test-Native {
    $exe = $args[0]; $rest = @($args | Select-Object -Skip 1)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & $exe @rest 2>&1 | Out-Null; return ($LASTEXITCODE -eq 0) } finally { $ErrorActionPreference = $previous }
}

function Confirm-Yes([string] $Question) {
    $answer = Read-Host "$Question Type yes to continue"
    return ($answer -eq "yes")
}

function Get-TerraformOutput([string] $Name) {
    Push-Location $DevDir
    try { return (Get-NativeOutput terraform output -raw $Name) } finally { Pop-Location }
}

# ---------------------------------------------------------------- 1. Tools and sign-in
Write-Step "1/9 Checking tools and signing in"
foreach ($tool in @("az", "terraform", "gh")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        $hint = @{ az = "winget install Microsoft.AzureCLI"; terraform = "winget install Hashicorp.Terraform"; gh = "winget install GitHub.cli" }[$tool]
        throw "'$tool' is not installed. Install it with: $hint, then open a new terminal and run this script again."
    }
}
$tfVersion = (Get-NativeOutput terraform version -json | ConvertFrom-Json).terraform_version
if ([version]$tfVersion -lt [version]"1.9.0") { throw "Terraform $tfVersion is too old; 1.9 or newer is needed (winget upgrade Hashicorp.Terraform)." }
Write-Host "Terraform $tfVersion"

if (-not (Test-Native az account show --only-show-errors)) { Invoke-Native az login --only-show-errors }
Invoke-Native az account set --subscription $SubscriptionId
Write-Host "Azure subscription: $(Get-NativeOutput az account show --query name -o tsv)"

if (-not (Test-Native gh auth status)) { Invoke-Native gh auth login --hostname github.com --git-protocol https --web }

if (-not $KeysOnly) {
    # ------------------------------------------------------------ 2. Owner check
    Write-Step "2/9 Checking you are Owner on the subscription"
    $me = Get-NativeOutput az ad signed-in-user show --query id -o tsv
    $roles = Get-NativeOutput az role assignment list --all --assignee $me --query "[?contains(scope, '$SubscriptionId')].roleDefinitionName" -o tsv
    if ($roles -notmatch "\bOwner\b") {
        throw "You are not Owner on subscription $SubscriptionId (roles found: '$roles'). Terraform creates role assignments, so Owner is needed."
    }
    Write-Host "Owner: yes"

    # ------------------------------------------------------------ 3. Resource providers
    Write-Step "3/9 Turning on the Azure services AirYatra uses (first time can take a few minutes)"
    $providers = @("Microsoft.App", "Microsoft.ContainerRegistry", "Microsoft.DocumentDB", "Microsoft.Cache",
        "Microsoft.KeyVault", "Microsoft.CognitiveServices", "Microsoft.Cdn", "Microsoft.Network", "Microsoft.Storage",
        "Microsoft.OperationalInsights", "Microsoft.Insights", "Microsoft.ManagedIdentity", "Microsoft.Security",
        "Microsoft.LoadTestService", "Microsoft.PolicyInsights", "Microsoft.Consumption")
    foreach ($p in $providers) {
        $state = Get-NativeOutput az provider show --namespace $p --query registrationState -o tsv
        if ($state -ne "Registered") {
            Write-Host "Registering $p"
            Invoke-Native az provider register --namespace $p --wait --only-show-errors
        }
    }
    Write-Host "All services registered"

    # ------------------------------------------------------------ 4. State storage
    Write-Step "4/9 Terraform state storage"
    $backendFile = Join-Path $DevDir "backend.hcl"
    if (Test-Path $backendFile) {
        Write-Host "Already set up ($backendFile exists)"
    } else {
        Push-Location $BootstrapDir
        try {
            Invoke-Native terraform init "-input=false"
            Invoke-Native terraform apply "-input=false" -auto-approve -var "subscription_id=$SubscriptionId"
            $backend = Get-NativeOutput terraform output -raw backend_config
        } finally { Pop-Location }
        Set-Content -Path $backendFile -Encoding ascii -Value ($backend + "`nkey = `"airyatra-dev.tfstate`"")
        Write-Host "Created. Keep infra\terraform\bootstrap\terraform.tfstate: it is git-ignored and holds the state storage's own state."
    }

    # ------------------------------------------------------------ 5. tfvars
    Write-Step "5/9 Writing terraform.tfvars"
    $myIp = $DeployerIp
    if (-not $myIp) { $myIp = (Invoke-RestMethod -Uri "https://api.ipify.org").ToString().Trim() }
    $tfvars = @"
subscription_id   = "$SubscriptionId"
alert_email       = "$AlertEmail"
deployer_ip_cidrs = ["$myIp/32"]
budget_start_date = "$BudgetStartDate"
"@
    Set-Content -Path (Join-Path $DevDir "terraform.tfvars") -Encoding ascii -Value $tfvars
    Write-Host "Your public IP $myIp is allowed through the Key Vault firewall."

    # ------------------------------------------------------------ 6. Plan and apply
    Write-Step "6/9 Creating the dev environment"
    Push-Location $DevDir
    try {
        # Your access to the state storage is granted in step 4 and Azure takes a few minutes to apply it,
        # so a fresh setup can get "403 AuthorizationPermissionMismatch" here at first. Wait and retry.
        for ($attempt = 1; $attempt -le 10; $attempt++) {
            & terraform init "-input=false" "-backend-config=backend.hcl"
            if ($LASTEXITCODE -eq 0) { break }
            if ($attempt -eq 10) { throw "'terraform init' still failed after 10 tries. Paste the error in the project thread." }
            Write-Host "Azure may still be applying your access to the state storage. Trying again in 60 seconds ($attempt/10)..." -ForegroundColor Yellow
            Start-Sleep -Seconds 60
        }
        Invoke-Native terraform plan "-input=false" -out dev.tfplan
        if (-not (Confirm-Yes "Review the plan above. The last line says how many resources will be created.")) {
            throw "Stopped before creating anything. Run the script again when ready."
        }
        Invoke-Native terraform apply "-input=false" dev.tfplan
        Remove-Item dev.tfplan -ErrorAction SilentlyContinue
    } finally { Pop-Location }

    # ------------------------------------------------------------ 7. GitHub environment
    Write-Step "7/9 Connecting GitHub to the environment"
    Invoke-Native gh api -X PUT "repos/$Repo/environments/dev" --silent
    Push-Location $DevDir
    try { $vars = Get-NativeOutput terraform output -json github_actions_variables | ConvertFrom-Json } finally { Pop-Location }
    foreach ($prop in $vars.PSObject.Properties) {
        Invoke-Native gh variable set $prop.Name --env dev --body ([string]$prop.Value) --repo $Repo
    }
    Write-Host "Added $(@($vars.PSObject.Properties).Count) variables to the GitHub environment 'dev'."
}

# ---------------------------------------------------------------- 8. Keys
$KeyVault = (Get-TerraformOutput "key_vault_uri") -replace "^https://", "" -replace "\.vault\.azure\.net/?$", ""

# Hands a value to the Azure CLI through a temp file, because Windows' az.cmd mangles values containing & | ^ % < >.
function Set-VaultSecret([string] $Name, [string] $Value) {
    $tmp = [System.IO.Path]::GetTempFileName()
    try {
        [System.IO.File]::WriteAllText($tmp, $Value)
        Invoke-Native az keyvault secret set --vault-name $KeyVault --name $Name --file $tmp --encoding utf-8 -o none --only-show-errors
    } finally { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
}

function Test-VaultSecretIsPlaceholder([string] $Name) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $value = & az keyvault secret show --vault-name $KeyVault --name $Name --query value -o tsv --only-show-errors 2>$null
        if ($LASTEXITCODE -ne 0) { return $true }
        return (($value | Out-String).Trim() -eq "set-me")
    } finally { $ErrorActionPreference = $previous }
}

if (-not $SkipKeys) {
    Write-Step "8/9 Putting keys into Key Vault ($KeyVault)"
    Write-Host "If this fails with 'Forbidden' or 'not authorized', your IP changed: run the script again without -KeysOnly."

    if (Test-VaultSecretIsPlaceholder "file-encryption-key") {
        $bytes = New-Object byte[] 32
        [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
        $fek = [Convert]::ToBase64String($bytes).Replace("+", "-").Replace("/", "_")
        Set-VaultSecret "file-encryption-key" $fek
        Remove-Variable fek
        Write-Host "Generated file-encryption-key (the dev database starts empty, so a fresh key is right)."
    } else {
        Write-Host "file-encryption-key is already set; keeping it."
    }

    Write-Host ""
    Write-Host "Use TEST-MODE keys only (Razorpay rzp_test_..., Stripe sk_test_..., Cashfree sandbox)."
    Write-Host "Typing is hidden. Press Enter to skip a key: that feature stays off until it is set."
    $keys = [ordered]@{
        "razorpay-key-id"          = "Razorpay Key Id (rzp_test_...)  [Dashboard > Test Mode > Account & Settings > API Keys]"
        "razorpay-key-secret"      = "Razorpay Key Secret"
        "razorpay-webhook-secret"  = "Razorpay webhook secret (a strong value you choose; enter the same on the webhook)"
        "razorpayx-key-id"         = "RazorpayX Key Id"
        "razorpayx-key-secret"     = "RazorpayX Key Secret"
        "razorpayx-account-number" = "RazorpayX account number"
        "stripe-api-key"           = "Stripe secret key (sk_test_...)"
        "stripe-webhook-secret"    = "Stripe webhook signing secret (whsec_...)"
        "cashfree-client-id"       = "Cashfree sandbox app id"
        "cashfree-client-secret"   = "Cashfree sandbox secret"
        "twilio-account-sid"       = "Twilio Account SID"
        "twilio-auth-token"        = "Twilio Auth Token"
        "sendgrid-api-key"         = "SendGrid API key (or skip and use SMTP below)"
        "smtp-password"            = "SMTP password"
        "google-client-id"         = "Google OAuth client id"
        "google-client-secret"     = "Google OAuth client secret"
        "openweather-api-key"      = "OpenWeather API key"
    }
    foreach ($name in $keys.Keys) {
        $status = if (Test-VaultSecretIsPlaceholder $name) { "not set" } else { "already set; Enter keeps it" }
        $secure = Read-Host "$($keys[$name]) [$status]" -AsSecureString
        $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try { $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
        if ($plain) {
            Set-VaultSecret $name $plain
            Write-Host "  saved $name" -ForegroundColor Green
        }
        $plain = $null
    }

    $apiUrl = Get-TerraformOutput "api_url"
    Write-Host ""
    Write-Host "Register these with the providers:"
    Write-Host "  Razorpay webhook:          $apiUrl/api/razorpay/webhook"
    Write-Host "  Google OAuth redirect URI: $apiUrl/api/auth/google/callback"
}

# ---------------------------------------------------------------- 9. Deploy
if (-not $SkipDeploy) {
    Write-Step "9/9 Starting the 'Deploy to Azure' workflow for dev"
    Invoke-Native gh workflow run azure-deploy.yml --repo $Repo --ref main -f environment=dev
    Write-Host "Started. Follow it with: gh run watch --repo $Repo"
}

Write-Host ""
Write-Host "Done. The site will be at: $(Get-TerraformOutput 'public_url')" -ForegroundColor Green
