<#
.SYNOPSIS
  Refresh the cached ETF/SPY price CSVs from yfinance. Nothing else.

.DESCRIPTION
  Intended to run unattended from Task Scheduler at 00:00 (see
  scripts/register_price_refresh_task.ps1). It ONLY touches data/prices/ - it
  does not rebuild the image, redeploy, or commit anything. Publishing what it
  fetches stays a deliberate act:

      powershell -ExecutionPolicy Bypass -File .\scripts\deploy_azure.ps1

  Note that a successful run leaves data/prices/*.csv modified in git. That is
  expected - the CSVs are tracked, and the refreshed rows are only baked into
  the image on the next deploy.

  The prices directory is snapshotted before the fetch and restored if the
  fetch fails or comes back with a shorter series than we already had, so a
  bad night can never leave the repo with worse data than it started with.

.EXAMPLE
  ./scripts/refresh_prices.ps1
  ./scripts/refresh_prices.ps1 -Start 2015-01-01
#>
[CmdletBinding()]
param(
    [string]$Start = "2019-01-01",
    [int]$LogRetentionDays = 30
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$pricesDir = Join-Path $repoRoot "data\prices"
$logDir = Join-Path $repoRoot "logs\price-refresh"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))

function Log($msg) {
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding utf8
}

# Same trap as deploy_azure.ps1: redirecting a native command's stderr in
# Windows PowerShell wraps each line in an ErrorRecord, which ErrorActionPreference
# 'Stop' then escalates into a fatal error - so a tool merely printing a warning
# would kill the run. Capture both streams and judge by exit code instead.
function Invoke-Native {
    param([Parameter(Mandatory)][scriptblock]$Command)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = & $Command 2>&1
        return [pscustomobject]@{
            Ok   = ($LASTEXITCODE -eq 0)
            Text = (@($out | ForEach-Object { $_.ToString() }) -join "`n")
        }
    } finally { $ErrorActionPreference = $prev; $global:LASTEXITCODE = 0 }
}

# Last dated row of each CSV, so the fetch can be judged rather than trusted.
function Get-PriceState {
    $state = @{}
    if (-not (Test-Path $pricesDir)) { return $state }
    foreach ($csv in Get-ChildItem -Path $pricesDir -Filter *.csv) {
        $rows = @(Get-Content $csv.FullName | Where-Object { $_ -match '^\d{4}-\d{2}-\d{2},' })
        if ($rows.Count) {
            $state[$csv.BaseName] = [pscustomobject]@{
                Rows = $rows.Count
                Last = ($rows[-1] -split ',')[0]
            }
        }
    }
    return $state
}

# Task Scheduler hands the process a minimal environment, so PATH cannot be
# trusted to contain the console script. Resolve it, then fall back to driving
# the CLI entrypoint through python directly.
function Resolve-Filingsignal {
    $cmd = Get-Command filingsignal -ErrorAction SilentlyContinue
    if ($cmd) { return @{ Exe = $cmd.Source; Args = @() } }

    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) {
        $guesses = @(
            "C:\Coding Stuff\Python\Python312\python.exe",
            "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
        )
        foreach ($g in $guesses) { if (Test-Path $g) { $py = [pscustomobject]@{ Source = $g }; break } }
    }
    if (-not $py) { return $null }

    $scripts = Join-Path (Split-Path -Parent $py.Source) "Scripts\filingsignal.exe"
    if (Test-Path $scripts) { return @{ Exe = $scripts; Args = @() } }

    # sys.argv[0] is '-c', and argparse only reads sys.argv[1:], so the
    # subcommand and flags land exactly where the console script would put them.
    return @{ Exe = $py.Source; Args = @("-c", "from filingsignal.cli import main; main()") }
}

Log "=== price refresh starting (start=$Start) ==="

$cli = Resolve-Filingsignal
if (-not $cli) {
    Log "FAILED: could not locate filingsignal or python"
    exit 1
}
Log "cli: $($cli.Exe)"

$before = Get-PriceState
Log "before: $($before.Count) CSV(s); latest $(($before.Values | ForEach-Object { $_.Last } | Sort-Object | Select-Object -Last 1))"

# Snapshot to a sibling directory so a failed or truncated fetch is reversible.
$backup = Join-Path $env:TEMP ("filingsignal-prices-{0}" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
if (Test-Path $pricesDir) {
    Copy-Item -Path $pricesDir -Destination $backup -Recurse -Force
    Log "snapshot: $backup"
}

function Restore-Snapshot($reason) {
    Log "RESTORING previous prices - $reason"
    if (Test-Path $backup) {
        Remove-Item -Path $pricesDir -Recurse -Force -ErrorAction SilentlyContinue
        Copy-Item -Path $backup -Destination $pricesDir -Recurse -Force
        Log "restored from $backup"
    } else {
        Log "no snapshot to restore from"
    }
}

# fetch-prices resolves data/prices relative to the process working directory.
Push-Location $repoRoot
try {
    $run = Invoke-Native { & $cli.Exe @($cli.Args) fetch-prices --start $Start }
} finally { Pop-Location }

foreach ($line in ($run.Text -split "`n")) { if ($line.Trim()) { Log "  | $line" } }

if (-not $run.Ok) {
    Restore-Snapshot "fetch-prices exited non-zero"
    Log "=== price refresh FAILED ==="
    exit 1
}

# A zero-exit fetch that silently returned fewer rows than we already had is
# still a regression - yfinance can answer with a truncated series.
$after = Get-PriceState
$regressed = @()
foreach ($ticker in $before.Keys) {
    if (-not $after.ContainsKey($ticker)) { $regressed += "$ticker vanished"; continue }
    if ($after[$ticker].Rows -lt $before[$ticker].Rows) {
        $regressed += ("{0} shrank {1} -> {2} rows" -f $ticker, $before[$ticker].Rows, $after[$ticker].Rows)
    }
}

if ($regressed.Count) {
    foreach ($r in $regressed) { Log "REGRESSION: $r" }
    Restore-Snapshot "fetch returned a shorter series than the cache already held"
    Log "=== price refresh FAILED ==="
    exit 1
}

foreach ($ticker in ($after.Keys | Sort-Object)) {
    $gained = if ($before.ContainsKey($ticker)) { $after[$ticker].Rows - $before[$ticker].Rows } else { $after[$ticker].Rows }
    Log ("  {0,-6} {1,5} rows (+{2})  through {3}" -f $ticker, $after[$ticker].Rows, $gained, $after[$ticker].Last)
}

Remove-Item -Path $backup -Recurse -Force -ErrorAction SilentlyContinue

Get-ChildItem -Path $logDir -Filter *.log -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$LogRetentionDays) } |
    Remove-Item -Force -ErrorAction SilentlyContinue

Log "=== price refresh OK - data/prices is now dirty in git; deploy to publish ==="
exit 0
