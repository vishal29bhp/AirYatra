<#
.SYNOPSIS
    Removes an AirYatra environment (dev or prod) from Azure with Terraform, after checks and a typed confirmation.

.DESCRIPTION
    Deletes everything Terraform created for one environment, and nothing else:
      1. Checks the tools (Azure CLI, Terraform) and signs you in.
      2. Connects to the environment's Terraform state (envs/<env>/backend.hcl, written by deploy-dev.ps1).
      3. Plans the teardown and checks every resource in it lives in that environment's own resource group
         (rg-airyatra-<env>-...). Anything outside it, such as another project's resources on the same
         subscription, stops the script before anything is deleted.
      4. Shows what will go and asks you to type "destroy airyatra-<env>".
      5. Deletes the environment (terraform destroy).
      6. Optionally removes the GitHub environment and the shared Terraform state storage.

    THIS DELETES THE ENVIRONMENT'S DATABASE, FILES AND KEYS. There is no undo for the database or blob files.
    Key Vault keeps the deleted vault for 90 days (purge protection), so the keys can be recovered; the script
    prints the command.

    Safe to run again after a failure: it carries on from what Terraform still tracks.

    Not touched:
      - Subscription-wide Defender for Cloud plans (prod turns them on). They cover every project on the
        subscription, so they are left on unless you pass -DisableDefenderPlans.
      - Resources Terraform does not track, such as anything created by hand in the portal. Dev's resource group
        is removed with whatever is in it; prod's refuses to go while it still holds untracked resources.

.EXAMPLE
    .\infra\scripts\teardown.ps1 -Environment dev -SubscriptionId <your-subscription-id>

.EXAMPLE
    # Dev, and also the GitHub environment "dev"
    .\infra\scripts\teardown.ps1 -Environment dev -SubscriptionId <id> -RemoveGitHubEnvironment

.EXAMPLE
    # Production: needs -ConfirmProduction and the Atlas credentials in MONGODB_ATLAS_CLIENT_ID/_SECRET
    .\infra\scripts\teardown.ps1 -Environment prod -SubscriptionId <id> -ConfirmProduction

.EXAMPLE
    # Everything, including the Terraform state storage, once every environment is gone
    .\infra\scripts\teardown.ps1 -Environment dev -SubscriptionId <id> -RemoveGitHubEnvironment -RemoveStateStorage
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [ValidateSet("dev", "prod")] [string] $Environment,
    [Parameter(Mandatory = $true)] [string] $SubscriptionId,
    [string] $Repo = "vishal29bhp/AirYatra",
    # Required, as well as the typed confirmation, to tear down production.
    [switch] $ConfirmProduction,
    # Also delete the GitHub environment (its variables are useless once Azure is gone).
    [switch] $RemoveGitHubEnvironment,
    # Also delete the Terraform state storage (rg-airyatra-tfstate-cin). Refused while any environment still has
    # resources in it.
    [switch] $RemoveStateStorage,
    # Turn the subscription-wide Defender for Cloud plans off (prod only). Off by default because they cover
    # every project on the subscription.
    [switch] $DisableDefenderPlans,
    # Plan and check only; delete nothing.
    [switch] $PlanOnly
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 3.0

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$TfRoot = Join-Path $RepoRoot "infra\terraform"
$BootstrapDir = Join-Path $TfRoot "bootstrap"
$EnvDir = Join-Path $TfRoot "envs\$Environment"
$PlanFile = "teardown.tfplan"
$Confirmation = "destroy airyatra-$Environment"
$script:ResourceGroup = $null
$script:KeptDefenderPlans = @()

function Write-Step([string] $Text) {
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

# Runs a native command and stops the script if it fails (PowerShell does not do this for .exe/.cmd on its own).
function Invoke-Native {
    $exe = $args[0]; $rest = @($args | Select-Object -Skip 1)
    & $exe @rest
    if ($LASTEXITCODE -ne 0) { throw "'$exe $($rest -join ' ')' failed with exit code $LASTEXITCODE." }
}

function Get-NativeOutput {
    $exe = $args[0]; $rest = @($args | Select-Object -Skip 1)
    $out = & $exe @rest
    if ($LASTEXITCODE -ne 0) { throw "'$exe $($rest -join ' ')' failed with exit code $LASTEXITCODE." }
    return (($out | Out-String).Trim())
}

function Test-Native {
    $exe = $args[0]; $rest = @($args | Select-Object -Skip 1)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & $exe @rest 2>&1 | Out-Null; return ($LASTEXITCODE -eq 0) } finally { $ErrorActionPreference = $previous }
}

# Windows PowerShell 5.1 strips the double quotes in addresses such as x.secret["jwt"] when calling an .exe.
function Format-Address([string] $Address) {
    if ($PSVersionTable.PSVersion -lt [version]"7.3") { return ($Address -replace '"', '\"') }
    return $Address
}

# Windows PowerShell 5.1's ConvertFrom-Json stops at 2 MB, which a large plan can pass.
function ConvertFrom-LargeJson([string] $Json) {
    if ($PSVersionTable.PSVersion.Major -ge 6) { return ($Json | ConvertFrom-Json) }
    Add-Type -AssemblyName System.Web.Extensions
    $serializer = New-Object System.Web.Script.Serialization.JavaScriptSerializer
    $serializer.MaxJsonLength = [int]::MaxValue
    return $serializer.DeserializeObject($Json)
}

function Get-Field($Object, [string] $Name) {
    if ($null -eq $Object) { return $null }
    if ($Object -is [System.Collections.IDictionary]) {
        if ($Object.Contains($Name)) { return $Object[$Name] }
        return $null
    }
    $prop = $Object.PSObject.Properties[$Name]
    if ($prop) { return $prop.Value }
    return $null
}

function Get-StateAddresses {
    Push-Location $EnvDir
    try { return @((Get-NativeOutput terraform state list) -split "`r?`n" | Where-Object { $_ }) } finally { Pop-Location }
}

# Output of a native command, or empty when it fails (stderr hidden; see Test-Native for why EA is relaxed).
function Get-NativeOutputOrEmpty {
    $exe = $args[0]; $rest = @($args | Select-Object -Skip 1)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = & $exe @rest 2>$null
        if ($LASTEXITCODE -ne 0) { return "" }
        return (($out | Out-String).Trim())
    } finally { $ErrorActionPreference = $previous }
}

function Stop-OnProblems([string[]] $Problems) {
    if (-not $Problems -or $Problems.Count -eq 0) { return }
    Write-Host ""
    Write-Host "Stopped: the teardown would do more than delete the AirYatra $Environment environment:" -ForegroundColor Red
    $Problems | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    throw "Nothing was deleted. Paste the lines above in the project thread."
}

# Plans the teardown into $PlanFile and returns the planned deletions after checking each one belongs to this
# environment. Throws, before anything is deleted, if any change is not a delete or any resource is outside the
# environment's resource group. -Final is the plan that is applied: there, a Defender plan still in it is a
# problem unless -DisableDefenderPlans; before that, it is reported as kept, since step 5 has Terraform forget it.
function New-CheckedDestroyPlan([string[]] $ExtraArgs, [switch] $Final) {
    Push-Location $EnvDir
    try {
        # -refresh=false: the plan works from state, so it does not need to reach Key Vault through its firewall
        # (your IP may have changed since the deploy) and does not depend on resources still answering.
        Invoke-Native terraform plan -destroy "-input=false" "-refresh=false" -out $PlanFile @ExtraArgs
        $json = (& terraform show -json $PlanFile) -join "`n"
        if ($LASTEXITCODE -ne 0) { throw "'terraform show -json $PlanFile' failed." }
    } finally { Pop-Location }

    $plan = ConvertFrom-LargeJson $json
    $changes = @(Get-Field $plan "resource_changes" | Where-Object { (Get-Field $_ "mode") -eq "managed" })
    $deletes = @()
    $problems = @()
    $resourceGroup = $null

    foreach ($rc in $changes) {
        $actions = @(Get-Field (Get-Field $rc "change") "actions")
        if ($actions.Count -eq 1 -and ($actions[0] -eq "no-op" -or $actions[0] -eq "read")) { continue }
        $address = Get-Field $rc "address"
        if ($actions.Count -ne 1 -or $actions[0] -ne "delete") {
            $problems += "$address would be $($actions -join '+'), not deleted"
            continue
        }
        $deletes += $rc
        if ((Get-Field $rc "type") -eq "azurerm_resource_group") {
            $resourceGroup = [string](Get-Field (Get-Field (Get-Field $rc "change") "before") "name")
        }
    }

    Stop-OnProblems $problems
    if ($deletes.Count -eq 0) { return @() }
    if (-not $resourceGroup) {
        throw "The plan deletes resources but not the environment's resource group, so the script cannot check where they live. Nothing was deleted. Paste this in the project thread."
    }
    if ($resourceGroup -notmatch "^rg-airyatra-$Environment-[a-z]+$") {
        throw "The state's resource group is '$resourceGroup', which is not an AirYatra $Environment resource group (rg-airyatra-$Environment-...). Nothing was deleted."
    }
    $rgPattern = "/resourceGroups/" + [regex]::Escape($resourceGroup) + "(/|$)"

    foreach ($rc in $deletes) {
        $type = [string](Get-Field $rc "type")
        $address = Get-Field $rc "address"
        $id = [string](Get-Field (Get-Field (Get-Field $rc "change") "before") "id")
        if ($type -like "random_*" -or $type -like "mongodbatlas_*") { continue }
        if ($type -eq "azurerm_security_center_subscription_pricing") {
            if (-not $DisableDefenderPlans) {
                if ($Final) { $problems += "$address turns off a subscription-wide Defender plan" }
                else { $script:KeptDefenderPlans += $address }
            }
            continue
        }
        if ($type -eq "azurerm_key_vault_secret" -and $id -match "^https://[a-z0-9-]+\.vault\.azure\.net/") { continue }
        if ($type -like "azurerm_*" -and $id -match "^/subscriptions/" -and $id -match $rgPattern) { continue }
        $problems += "$address ($type) is not inside $resourceGroup (id: $id)"
    }

    Stop-OnProblems $problems
    if (-not $DisableDefenderPlans) {
        $deletes = @($deletes | Where-Object { (Get-Field $_ "type") -ne "azurerm_security_center_subscription_pricing" })
    }

    Write-Host ""
    Write-Host "Checked: all $($deletes.Count) resources are in $resourceGroup." -ForegroundColor Green
    $script:ResourceGroup = $resourceGroup
    return $deletes
}

# ---------------------------------------------------------------- 1. Tools and sign-in
Write-Step "1/6 Checking tools and signing in"
if ($Environment -eq "prod" -and -not $ConfirmProduction) {
    throw "Tearing down production also needs -ConfirmProduction. Nothing was done."
}
foreach ($tool in @("az", "terraform")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "'$tool' is not installed." }
}
if ($RemoveGitHubEnvironment -and -not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "'gh' is not installed (needed for -RemoveGitHubEnvironment): winget install GitHub.cli"
}
$tfVersion = (Get-NativeOutput terraform version -json | ConvertFrom-Json).terraform_version
if ([version]$tfVersion -lt [version]"1.9.0") { throw "Terraform $tfVersion is too old; 1.9 or newer is needed." }

if (-not (Test-Native az account show --only-show-errors)) { Invoke-Native az login --only-show-errors }
Invoke-Native az account set --subscription $SubscriptionId
$SubscriptionName = Get-NativeOutput az account show --query name -o tsv
Write-Host "Azure subscription: $SubscriptionName ($SubscriptionId)"

if ($Environment -eq "prod" -and -not ($env:MONGODB_ATLAS_CLIENT_ID -or $env:MONGODB_ATLAS_PUBLIC_KEY)) {
    throw "Production's database is on MongoDB Atlas: set MONGODB_ATLAS_CLIENT_ID and MONGODB_ATLAS_CLIENT_SECRET (or the PUBLIC_KEY/PRIVATE_KEY pair) in this terminal first."
}

# ---------------------------------------------------------------- 2. State
Write-Step "2/6 Connecting to the $Environment Terraform state"
$backendFile = Join-Path $EnvDir "backend.hcl"
if (-not (Test-Path $backendFile)) {
    throw "$backendFile is missing, so there is no state to read. Either the state storage was already removed (then there is nothing left to tear down), or $Environment was deployed from another machine: copy backend.hcl.example and fill it from the bootstrap outputs."
}
if (-not (Test-Path (Join-Path $EnvDir "terraform.tfvars"))) {
    throw "$EnvDir\terraform.tfvars is missing. Terraform needs it even to delete; copy terraform.tfvars.example and fill it in."
}
Push-Location $EnvDir
try { Invoke-Native terraform init "-input=false" "-backend-config=backend.hcl" } finally { Pop-Location }

$addresses = Get-StateAddresses
$managed = @($addresses | Where-Object { $_ -notmatch "(^|\.)data\." })
$KeyVaultName = $null
$EnvGone = ($managed.Count -eq 0)

# ---------------------------------------------------------------- 3. Plan and check
Write-Step "3/6 Planning the teardown and checking it stays inside AirYatra $Environment"
$prodVars = @()
if ($Environment -eq "prod") { $prodVars = @("-var", "atlas_termination_protection=false") }

if ($EnvGone) {
    Write-Host "Terraform tracks nothing for ${Environment}: it is already torn down."
} else {
    $deletes = @(New-CheckedDestroyPlan $prodVars)
    if ($deletes.Count -eq 0) {
        Write-Host "Nothing to delete."
        $EnvGone = $true
    } else {
        Push-Location $EnvDir
        try { $kvUri = Get-NativeOutputOrEmpty terraform output -raw key_vault_uri } finally { Pop-Location }
        if ($kvUri) { $KeyVaultName = ($kvUri -replace "^https://", "" -replace "\.vault\.azure\.net/?$", "") }

        $byType = $deletes | Group-Object { [string](Get-Field $_ "type") } | Sort-Object Count -Descending
        Write-Host ""
        Write-Host "To be deleted from $($script:ResourceGroup) on '$SubscriptionName':" -ForegroundColor Yellow
        foreach ($g in $byType) { Write-Host ("  {0,3}  {1}" -f $g.Count, $g.Name) }
        if ($script:KeptDefenderPlans.Count -gt 0) {
            Write-Host "Kept on (subscription-wide, pass -DisableDefenderPlans to turn off): $($script:KeptDefenderPlans.Count) Defender for Cloud plans"
        }
    }
}

if ($PlanOnly) {
    Push-Location $EnvDir; Remove-Item $PlanFile -ErrorAction SilentlyContinue; Pop-Location
    Write-Host ""
    Write-Host "Plan only: nothing was deleted." -ForegroundColor Green
    return
}

# ---------------------------------------------------------------- 4. Confirm
Write-Step "4/6 Confirm"
Write-Host "This permanently deletes:" -ForegroundColor Red
if (-not $EnvGone) {
    Write-Host "  - the AirYatra $Environment environment in $($script:ResourceGroup): site, API, database (every user," -ForegroundColor Red
    Write-Host "    booking, payment and document record), uploaded files, cache, AI model and monitoring" -ForegroundColor Red
    if ($Environment -eq "prod") {
        Write-Host "  - the production MongoDB Atlas cluster AND its backups (termination protection is turned off first)" -ForegroundColor Red
    }
    if ($DisableDefenderPlans) { Write-Host "  - the subscription-wide Defender for Cloud plans (every project on '$SubscriptionName')" -ForegroundColor Red }
}
if ($RemoveGitHubEnvironment) { Write-Host "  - the GitHub environment '$Environment' on $Repo and its variables" -ForegroundColor Red }
if ($RemoveStateStorage) { Write-Host "  - the Terraform state storage (only if no environment is left in it)" -ForegroundColor Red }
if ($EnvGone -and -not $RemoveGitHubEnvironment -and -not $RemoveStateStorage) {
    Write-Host "  nothing: ${Environment} is already gone." -ForegroundColor Green
    return
}
$typed = Read-Host "Type '$Confirmation' to continue"
if ($typed -cne $Confirmation) {
    Push-Location $EnvDir; Remove-Item $PlanFile -ErrorAction SilentlyContinue; Pop-Location
    throw "Not confirmed. Nothing was deleted."
}

# ---------------------------------------------------------------- 5. Destroy
if (-not $EnvGone) {
    Write-Step "5/6 Deleting AirYatra $Environment (can take 20 to 40 minutes; Front Door and the database are slow)"
    # These go when their parent goes, and deleting them one by one needs data-plane access through the Key Vault
    # and storage firewalls, so Terraform just forgets them.
    $forget = @($managed | Where-Object { $_ -match "azurerm_key_vault_secret\." -or $_ -match "azurerm_storage_account_static_website\." })
    # Subscription-wide Defender plans stay on unless asked; Terraform forgets them instead of turning them off.
    if (-not $DisableDefenderPlans) { $forget += @($managed | Where-Object { $_ -match "azurerm_security_center_subscription_pricing\." }) }
    if ($forget.Count -gt 0) {
        Push-Location $EnvDir
        try {
            foreach ($address in $forget) { Invoke-Native terraform state rm (Format-Address $address) }
        } finally { Pop-Location }
    }

    # Atlas refuses to delete a cluster with termination protection on; turn it off on the cluster alone.
    $cluster = @($managed | Where-Object { $_ -match "mongodbatlas_advanced_cluster\." })
    if ($Environment -eq "prod" -and $cluster.Count -gt 0) {
        Write-Host "Turning off termination protection on the production database"
        Push-Location $EnvDir
        try {
            $targets = @($cluster | ForEach-Object { "-target=$(Format-Address $_)" })
            Invoke-Native terraform apply "-input=false" -auto-approve @targets @prodVars
        } finally { Pop-Location }
    }

    # The plan from step 3 is stale once state changed, so plan and check again; this is the one applied.
    Write-Host "Planning the final teardown"
    $null = New-CheckedDestroyPlan $prodVars -Final

    Push-Location $EnvDir
    try {
        & terraform apply "-input=false" $PlanFile
        $failed = ($LASTEXITCODE -ne 0)
        Remove-Item $PlanFile -ErrorAction SilentlyContinue
    } finally { Pop-Location }
    if ($failed) {
        Write-Host ""
        Write-Host "The teardown stopped part way. Run the script again: it carries on with what is left." -ForegroundColor Yellow
        if (Test-Native az group show --name $script:ResourceGroup) {
            Write-Host "Still in ${script:ResourceGroup}:"
            & az resource list --resource-group $script:ResourceGroup --query "[].{name:name, type:type}" -o table
        }
        throw "terraform destroy failed. If it fails again, paste the error in the project thread."
    }
    Write-Host "AirYatra $Environment is deleted." -ForegroundColor Green
} else {
    Write-Step "5/6 AirYatra $Environment is already deleted"
}

# ---------------------------------------------------------------- 6. GitHub and state storage
Write-Step "6/6 Clean-up outside the environment"
if ($RemoveGitHubEnvironment) {
    if (-not (Test-Native gh auth status)) { Invoke-Native gh auth login --hostname github.com --git-protocol https --web }
    if (Test-Native gh api "repos/$Repo/environments/$Environment") {
        Invoke-Native gh api -X DELETE "repos/$Repo/environments/$Environment" --silent
        Write-Host "Removed the GitHub environment '$Environment'."
    } else {
        Write-Host "GitHub environment '$Environment' is already gone."
    }
} else {
    Write-Host "GitHub environment '$Environment' kept (pass -RemoveGitHubEnvironment to remove it)."
}

if ($RemoveStateStorage) {
    $backend = @{}
    foreach ($line in Get-Content $backendFile) {
        if ($line -match '^\s*([a-z_]+)\s*=\s*"([^"]*)"') { $backend[$Matches[1]] = $Matches[2] }
    }
    $account = $backend["storage_account_name"]
    $container = $backend["container_name"]
    if ($backend["resource_group_name"] -notmatch "^rg-airyatra-tfstate-") {
        throw "backend.hcl names resource group '$($backend["resource_group_name"])', which is not AirYatra's state storage. Not removing it."
    }

    # Every state file left in the container must be empty: an environment with resources would be orphaned.
    $blobs = @((Get-NativeOutput az storage blob list --account-name $account --container-name $container --auth-mode login --query "[].name" -o tsv) -split "`r?`n" | Where-Object { $_ })
    $busy = @()
    foreach ($blob in $blobs) {
        $tmp = [System.IO.Path]::GetTempFileName()
        try {
            Invoke-Native az storage blob download --account-name $account --container-name $container --name $blob --file $tmp --auth-mode login -o none --only-show-errors
            $state = ConvertFrom-LargeJson ([System.IO.File]::ReadAllText($tmp))
            $count = @(Get-Field $state "resources" | Where-Object { (Get-Field $_ "mode") -eq "managed" }).Count
            if ($count -gt 0) { $busy += "$blob ($count resources)" }
        } finally { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
    }
    if ($busy.Count -gt 0) {
        throw "State storage kept: these environments still have resources: $($busy -join ', '). Tear them down first, then run again with -RemoveStateStorage."
    }

    if (-not (Test-Path (Join-Path $BootstrapDir "terraform.tfstate"))) {
        throw "infra\terraform\bootstrap\terraform.tfstate is not on this machine, so Terraform cannot remove the state storage. Every environment is gone, so you can delete resource group $($backend["resource_group_name"]) in the portal."
    }
    Push-Location $BootstrapDir
    try {
        Invoke-Native terraform init "-input=false"
        Invoke-Native terraform destroy "-input=false" -auto-approve -var "subscription_id=$SubscriptionId"
    } finally { Pop-Location }
    # deploy-dev.ps1 creates the state storage again when backend.hcl is missing.
    Get-ChildItem (Join-Path $TfRoot "envs") -Directory | ForEach-Object {
        Remove-Item (Join-Path $_.FullName "backend.hcl") -ErrorAction SilentlyContinue
    }
    Write-Host "Removed the Terraform state storage."
} else {
    Write-Host "Terraform state storage kept (pass -RemoveStateStorage to remove it once every environment is gone)."
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
if ($KeyVaultName) {
    Write-Host "Key Vault $KeyVaultName is kept as deleted for 90 days and cannot be purged sooner (purge protection)."
    Write-Host "To get its keys back within that time: az keyvault recover --name $KeyVaultName"
}
if ($Environment -eq "dev") { Write-Host "To deploy dev again later, run .\infra\scripts\deploy-dev.ps1 (new resource names are generated)." }
