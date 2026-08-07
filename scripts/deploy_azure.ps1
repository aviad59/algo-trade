<#
.SYNOPSIS
  Deploy FilingSignal to Azure Container Apps as a single container.

.DESCRIPTION
  Idempotent: run it once to create everything, run it again after any code
  change to ship a new revision.

  The image is built locally with Docker and pushed to Azure Container Registry.
  The tidier `containerapp up --source` path is NOT usable here: it builds via
  ACR Tasks, which Azure for Students subscriptions reject outright with
  TasksOperationsNotAllowed. Docker Desktop must therefore be running.

  The dashboard is served entirely from the committed data/ buffer, so the
  deploy works with no keys at all. Keys are read from .env (never committed)
  and pushed as Container Apps secrets only if present — they enable the live
  extraction demo (POST /digest, /extract).

.EXAMPLE
  ./scripts/deploy_azure.ps1
  ./scripts/deploy_azure.ps1 -MinReplicas 0        # scale to zero, ~free, cold starts
  ./scripts/deploy_azure.ps1 -WhatIfCost           # print the cost estimate and exit
#>
[CmdletBinding()]
param(
    [string]$ResourceGroup = "filingsignal-rg",
    [string]$AppName       = "filingsignal",
    # Azure for Students subscriptions carry a "sys.regionrestriction" policy that
    # whitelists a handful of regions - the default US regions are NOT allowed and
    # fail with RequestDisallowedByAzure. The script verifies this below and prints
    # the permitted list.
    #
    # francecentral is the tested-good default. Of the regions allowed on this
    # subscription: israelcentral offers no Container Apps at all, and
    # germanywestcentral has no environment capacity for student subscriptions
    # (MaxNumberOfEnvironmentsInSubExceeded - which the quota API does NOT reveal;
    # it cheerfully reports 0/1 used). italynorth and uaenorth are untested.
    [string]$Location      = "francecentral",
    [string]$Environment   = "filingsignal-env",

    # 1 = always warm (no cold start, ~$4-6/mo of credit).
    # 0 = scales to zero when idle (~free, ~10s cold start on first hit).
    [ValidateSet(0, 1)]
    [int]$MinReplicas = 1,

    [switch]$WhatIfCost
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Note($msg) { Write-Host "    $msg" -ForegroundColor DarkGray }
function Warn($msg) { Write-Host "    ! $msg" -ForegroundColor Yellow }

# Windows PowerShell wraps a native command's stderr in ErrorRecord objects as
# soon as the stream is redirected, and $ErrorActionPreference='Stop' escalates
# those into fatal errors - so a tool merely PRINTING A WARNING kills the script.
# Every probe that is allowed to fail (or to be chatty) runs through here, which
# drops to Continue, captures both streams, and reports the exit code instead.
function Invoke-Native {
    param([Parameter(Mandatory)][scriptblock]$Command)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = & $Command 2>&1
        return [pscustomobject]@{
            Ok    = ($LASTEXITCODE -eq 0)
            Lines = @($out | Where-Object { $_ -is [string] })
            Text  = (@($out | Where-Object { $_ -is [string] }) -join "`n")
        }
    } finally { $ErrorActionPreference = $prev; $global:LASTEXITCODE = 0 }
}

if ($WhatIfCost) {
    Write-Host @"

FilingSignal on Azure Container Apps -- rough monthly credit burn
-----------------------------------------------------------------
  Container Registry (Basic)      ~`$5.00/mo   fixed, holds the built image
  Container App, min-replicas 1   ~`$3-6/mo    0.5 vCPU / 1 GiB, mostly idle rate
  Container App, min-replicas 0   ~`$0         only pays while serving requests
  Ingress + TLS + FQDN             `$0         included
                                  ---------
  Total, always-warm              ~`$10/mo    => ~10 months of a `$100 student credit
  Total, scale-to-zero            ~`$5/mo     => ~20 months

  Tear everything down with:  az group delete --name $ResourceGroup --yes
"@
    exit 0
}

# ---------------------------------------------------------------- preflight --
# The CLI is resolved by path, not by relying on PATH: the installer edits the
# machine PATH, but shells (and VS Code, which caches its environment at launch)
# keep the stale copy until fully restarted. Looking in the known install
# locations means a freshly-installed CLI works without a reboot.
function Resolve-AzCli {
    $cmd = Get-Command az -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $candidates = @(
        "$env:ProgramFiles\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
        "${env:ProgramFiles(x86)}\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
        "$env:LOCALAPPDATA\Programs\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
    )
    foreach ($c in $candidates) { if (Test-Path $c) { return $c } }

    # Last resort: the machine PATH this process never picked up.
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    foreach ($dir in ($machinePath -split ';')) {
        if ($dir -and (Test-Path (Join-Path $dir "az.cmd"))) { return (Join-Path $dir "az.cmd") }
    }
    return $null
}

Step "Preflight"
$az = Resolve-AzCli
if (-not $az) {
    throw "Azure CLI not found. Install it, then reopen the terminal:`n    winget install -e --id Microsoft.AzureCLI"
}
$azVersion = (& $az version -o json | ConvertFrom-Json).'azure-cli'
Note "az $azVersion ($az)"

# `az account show` exits non-zero when nobody is logged in - an expected state
# here, not a failure. Its stderr must be handled carefully: in Windows
# PowerShell, redirecting a native command's stderr wraps each line in an
# ErrorRecord, which $ErrorActionPreference='Stop' then escalates into a fatal
# error. So drop to Continue, merge the streams, and keep only the stdout lines.
$probe = Invoke-Native { & $az account show -o json }
$account = $probe.Text
$loggedIn = $probe.Ok

if (-not $loggedIn) {
    Note "not logged in - opening browser"
    & $az login | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "az login failed (exit $LASTEXITCODE)" }
    $account = & $az account show -o json
}
$sub = $account | ConvertFrom-Json
Note "subscription: $($sub.name)"
if ($sub.name -notmatch 'Student') {
    Warn "this is not a 'Azure for Students' subscription - charges may hit a real payment method"
}

# Fail fast on a disallowed region: otherwise the error only surfaces minutes
# later, from deep inside `containerapp up`, as an opaque RequestDisallowedByAzure.
$policy = Invoke-Native { & $az policy assignment show --name "sys.regionrestriction" -o json }
if ($policy.Ok -and $policy.Text) {
    $allowed = ($policy.Text | ConvertFrom-Json).parameters.listOfAllowedLocations.value
    if ($allowed -and ($allowed -notcontains $Location)) {
        throw "Region '$Location' is blocked by your subscription's region policy.`n" +
              "  Allowed: $($allowed -join ', ')`n" +
              "  Rerun with e.g. -Location $($allowed[0])"
    }
    if ($allowed) { Note "region '$Location' permitted by sys.regionrestriction" }
}

# A group's own location is just metadata for where its record lives - the
# resources inside it are free to sit in any region - so a mismatch is worth
# noting but never worth deleting anything over.
$groupProbe = Invoke-Native { & $az group show --name $ResourceGroup --query location -o tsv }
$existing = if ($groupProbe.Ok) { $groupProbe.Text.Trim() } else { $null }
if ($existing -and ($existing -ne $Location)) {
    Note "resource group record lives in '$existing'; deploying resources to '$Location' (fine - group location is metadata only)"
}

Note "ensuring the containerapp extension + resource providers"
& $az extension add --name containerapp --upgrade --only-show-errors | Out-Null
# All three are required: App = the container app + environment,
# OperationalInsights = the environment's log workspace,
# ContainerRegistry = the registry that the cloud build pushes the image into.
foreach ($ns in @("Microsoft.App", "Microsoft.OperationalInsights", "Microsoft.ContainerRegistry")) {
    & $az provider register --namespace $ns --wait | Out-Null
    Note "  provider $ns registered"
}

# ------------------------------------------------------- config from .env ----
# Parsed locally and sent to Azure; .env itself is git-ignored and is NOT part
# of the image (see .dockerignore), so this is the only path a key travels.
Step "Reading config from .env"
$envFile = Join-Path $repoRoot ".env"
$cfg = @{}
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
        $k, $v = $line -split '=', 2
        $cfg[$k.Trim()] = $v.Trim().Trim('"').Trim("'")
    }
    Note "loaded $($cfg.Count) setting(s)"
} else {
    Warn ".env not found - deploying the read-only dashboard with no live extraction"
}

function Cfg($key, $fallback) {
    if ($cfg.ContainsKey($key) -and $cfg[$key]) { return $cfg[$key] }
    return $fallback
}

# The image bakes BACKTEST_SINCE="2024 Q1"; the published 14-quarter result is
# "2023 Q1", so it is always set explicitly here rather than inherited.
$backtestSince = Cfg "FILINGSIGNAL_BACKTEST_SINCE" "2023 Q1"
$llmProvider   = Cfg "FILINGSIGNAL_LLM_PROVIDER"   "claude"
$llmModel      = Cfg "FILINGSIGNAL_LLM_MODEL"      "claude-sonnet-5"
$secIdentity   = Cfg "FILINGSIGNAL_SEC_IDENTITY"   ""
$anthropicKey  = Cfg "ANTHROPIC_API_KEY"           ""
$apiKey        = Cfg "FILINGSIGNAL_API_KEY"        ""

# --------------------------------------------------------------- resources ---
Step "Resource group"
# Creating an existing group with a different location is an error, not a no-op,
# so only create it when it is genuinely absent.
if ($existing) {
    Note "$ResourceGroup already exists (record in '$existing')"
} else {
    & $az group create --name $ResourceGroup --location $Location --only-show-errors -o none
    Note "$ResourceGroup created ($Location)"
}

# ----------------------------------------------------------------- registry --
# The image is built HERE with Docker and pushed, rather than by `containerapp up
# --source`: that path uses ACR Tasks, which Azure for Students subscriptions are
# refused with TasksOperationsNotAllowed. Building locally sidesteps it entirely
# and reuses the local layer cache, so redeploys only push what changed.
Step "Container registry"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is required to build the image (ACR Tasks is not available on this subscription). Start Docker Desktop and rerun."
}
if (-not (Invoke-Native { docker info }).Ok) {
    throw "Docker is installed but not running. Start Docker Desktop and rerun."
}

$acrProbe = Invoke-Native { & $az acr list --resource-group $ResourceGroup --query "[0].name" -o tsv }
$acr = if ($acrProbe.Ok -and $acrProbe.Text) { $acrProbe.Text.Trim() } else { $null }
if (-not $acr) {
    # Registry names are globally unique and alphanumeric-only.
    $acr = "filingsignal" + -join ((48..57) + (97..122) | Get-Random -Count 8 | ForEach-Object { [char]$_ })
    Note "creating registry $acr"
    & $az acr create --name $acr --resource-group $ResourceGroup --location $Location `
        --sku Basic --admin-enabled true --only-show-errors -o none
    if ($LASTEXITCODE -ne 0) { throw "acr create failed (exit $LASTEXITCODE)" }
} else {
    Note "using existing registry $acr"
    & $az acr update --name $acr --admin-enabled true --only-show-errors -o none | Out-Null
}

$server = "$acr.azurecr.io"
$creds  = (& $az acr credential show --name $acr -o json | ConvertFrom-Json)
$acrUser = $creds.username
$acrPass = $creds.passwords[0].value

Step "Build and push image"
# A unique tag per deploy: Container Apps keys new revisions off the image
# reference, so a moving :latest tag can silently keep serving the old image.
$tag   = "v" + (Get-Date -Format "yyyyMMdd-HHmmss")
$image = "$server/filingsignal:$tag"

Note "docker build (cached layers make redeploys fast)"
docker build -t $image $repoRoot
if ($LASTEXITCODE -ne 0) { throw "docker build failed (exit $LASTEXITCODE)" }

Note "authenticating docker to $server"
# `az acr login` mints a short-lived AAD token and hands it to Docker - more
# robust than the admin password, which must not be piped via --password-stdin:
# PowerShell terminates piped input with CRLF, and the stray carriage return
# becomes part of the password, yielding a baffling UNAUTHORIZED.
& $az acr login --name $acr
if ($LASTEXITCODE -ne 0) {
    Note "  token login failed - falling back to admin credentials"
    docker login $server --username $acrUser --password $acrPass
    if ($LASTEXITCODE -ne 0) { throw "docker login to $server failed" }
}

Note "pushing $image (first push uploads ~300 MB; later ones only changed layers)"
docker push $image
if ($LASTEXITCODE -ne 0) { throw "docker push failed (exit $LASTEXITCODE)" }

# ------------------------------------------------------------- the app -------
Step "Container app"
$appProbe = Invoke-Native { & $az containerapp show --name $AppName --resource-group $ResourceGroup -o json }
$appExists = ($appProbe.Ok -and $appProbe.Text)

if ($appExists) {
    Note "updating existing app to $tag"
    & $az containerapp registry set --name $AppName --resource-group $ResourceGroup `
        --server $server --username $acrUser --password $acrPass --only-show-errors -o none
    & $az containerapp update --name $AppName --resource-group $ResourceGroup `
        --image $image --only-show-errors -o none
    if ($LASTEXITCODE -ne 0) { throw "containerapp update failed (exit $LASTEXITCODE)" }
} else {
    Note "creating app from $tag"
    & $az containerapp create --name $AppName --resource-group $ResourceGroup `
        --environment $Environment `
        --image $image `
        --target-port 8000 --ingress external `
        --registry-server $server --registry-username $acrUser --registry-password $acrPass `
        --only-show-errors -o none
    if ($LASTEXITCODE -ne 0) { throw "containerapp create failed (exit $LASTEXITCODE)" }
}

# ------------------------------------------------------ secrets + env vars ---
Step "Secrets and environment"
$envVars = @(
    "FILINGSIGNAL_BACKTEST_SINCE=$backtestSince",
    "FILINGSIGNAL_LLM_PROVIDER=$llmProvider",
    "FILINGSIGNAL_LLM_MODEL=$llmModel"
)
if ($secIdentity) { $envVars += "FILINGSIGNAL_SEC_IDENTITY=$secIdentity" }

# Both keys are required for the live demo: the provider key spends money, and
# FILINGSIGNAL_API_KEY is the shared gate in front of it. Without the gate the
# endpoint returns 503 by design, so never ship the provider key alone.
if ($anthropicKey -and $apiKey) {
    & $az containerapp secret set --name $AppName --resource-group $ResourceGroup `
        --secrets "anthropic-key=$anthropicKey" "fs-api-key=$apiKey" --only-show-errors -o none
    $envVars += "ANTHROPIC_API_KEY=secretref:anthropic-key"
    $envVars += "FILINGSIGNAL_API_KEY=secretref:fs-api-key"
    Note "live extraction ENABLED (gated by FILINGSIGNAL_API_KEY)"
} else {
    Warn "live extraction DISABLED - /digest and /extract will return 503"
    if ($anthropicKey -and -not $apiKey) { Warn "  reason: FILINGSIGNAL_API_KEY empty; refusing to expose an ungated provider key" }
}

& $az containerapp update --name $AppName --resource-group $ResourceGroup `
    --set-env-vars @envVars --only-show-errors -o none

# max-replicas is pinned to 1 on purpose: each replica gets its own copy of the
# baked SQLite buffer, so extraction writes would diverge across replicas.
Step "Scale + resources"
& $az containerapp update --name $AppName --resource-group $ResourceGroup `
    --min-replicas $MinReplicas --max-replicas 1 `
    --cpu 0.5 --memory 1.0Gi --only-show-errors -o none
Note "min=$MinReplicas max=1, 0.5 vCPU / 1 GiB"

# ----------------------------------------------------------------- verify ----
Step "Verify"
$fqdn = & $az containerapp show --name $AppName --resource-group $ResourceGroup `
    --query properties.configuration.ingress.fqdn -o tsv
$url = "https://$fqdn"

$ok = $false
foreach ($attempt in 1..10) {
    try {
        $health = Invoke-RestMethod -Uri "$url/api/v1/health" -TimeoutSec 20
        $ok = $true
        break
    } catch {
        Note "health check $attempt/10 - waiting for the revision to come up"
        Start-Sleep -Seconds 10
    }
}

Write-Host ""
if ($ok) {
    Write-Host "  LIVE  $url" -ForegroundColor Green
    Note "health: $($health | ConvertTo-Json -Compress)"
    Note "paste this URL into README.md, then commit and push"
} else {
    Warn "deployed, but /api/v1/health did not answer yet: $url"
    Note "check logs: az containerapp logs show -n $AppName -g $ResourceGroup --follow"
}
