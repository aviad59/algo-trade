<#
.SYNOPSIS
  Register (or remove) the daily 00:00 Windows scheduled task that refreshes
  the cached price CSVs.

.DESCRIPTION
  Wraps scripts/refresh_prices.ps1 in a Task Scheduler entry. The task runs as
  the current user with normal privileges, so no elevation is needed either to
  register it or to run it.

  It refreshes data/prices only. It never deploys and never commits - see the
  header of refresh_prices.ps1.

  Because the task runs interactively as you, it fires only while you are
  logged on. StartWhenAvailable covers the ordinary case of the laptop being
  asleep or shut down at midnight: the run happens once at the next
  opportunity rather than being skipped outright.

.EXAMPLE
  ./scripts/register_price_refresh_task.ps1
  ./scripts/register_price_refresh_task.ps1 -At 03:30
  ./scripts/register_price_refresh_task.ps1 -Unregister
#>
[CmdletBinding()]
param(
    [string]$TaskName = "FilingSignal price refresh",
    [datetime]$At = "00:00",
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$script = Join-Path $repoRoot "scripts\refresh_prices.ps1"

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($Unregister) {
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "removed scheduled task '$TaskName'" -ForegroundColor Yellow
    } else {
        Write-Host "no scheduled task named '$TaskName'" -ForegroundColor DarkGray
    }
    exit 0
}

if (-not (Test-Path $script)) { throw "missing $script" }

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}"' -f $script) `
    -WorkingDirectory $repoRoot

$trigger = New-ScheduledTaskTrigger -Daily -At $At

# StartWhenAvailable is the point of the whole configuration: without it, every
# night the machine is off at midnight is simply lost. The battery settings stop
# Windows from suppressing or killing the run on an unplugged laptop.
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

# Interactive + Limited: runs as you, only while logged on, no elevation and no
# stored password. A network fetch into your own repo needs nothing more.
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

if ($existing) {
    Set-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null
    Write-Host "updated scheduled task '$TaskName'" -ForegroundColor Green
} else {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
        -Description "Refresh FilingSignal cached ETF/SPY price CSVs from yfinance. Does not deploy or commit." | Out-Null
    Write-Host "registered scheduled task '$TaskName'" -ForegroundColor Green
}

$t = Get-ScheduledTask -TaskName $TaskName
$i = $t | Get-ScheduledTaskInfo
Write-Host ("  state    : {0}" -f $t.State)
Write-Host ("  runs at  : {0} daily" -f $At.ToString("HH:mm"))
Write-Host ("  next run : {0}" -f $i.NextRunTime)
Write-Host ("  logs     : {0}" -f (Join-Path $repoRoot "logs\price-refresh"))
Write-Host ""
Write-Host "  run it now :  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "  remove it  :  ./scripts/register_price_refresh_task.ps1 -Unregister"
