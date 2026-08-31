<#
.SYNOPSIS
  État de l'agent CBC de ce poste, vu depuis la machine.

.DESCRIPTION
  Répond aux trois questions qu'on se pose depuis un terminal : l'agent
  tourne-t-il, la plateforme le voit-elle, et que dit-il en ce moment.

  Le diagnostic vient de l'agent lui-même (`cbc-agent status`), pas d'une
  déduction faite ici : c'est la machine qui sait sous quel compte elle
  tourne et quelle configuration elle a réellement chargée.

.EXAMPLE
  .\scripts\agent-status.ps1
  .\scripts\agent-status.ps1 -Follow
#>
[CmdletBinding()]
param(
    [string] $Config,

    # Suivre le journal en direct (Ctrl+C pour sortir).
    [switch] $Follow,

    # Nombre de lignes de journal affichées.
    [int] $Lines = 12
)

$ErrorActionPreference = 'Stop'

$Repo     = Split-Path -Parent $PSScriptRoot
$AgentSrc = Join-Path $Repo 'agent\src'
$LogFile  = Join-Path $Repo 'agent\logs\windows-agent.log'
$LockFile = Join-Path $env:TEMP 'cbc-agent.pid'

if (-not $Config) { $Config = Join-Path $Repo 'agent\config.lab.yaml' }

# ---- Le processus tourne-t-il ? -------------------------------------------

$pidHeld = if (Test-Path $LockFile) { Get-Content $LockFile -ErrorAction SilentlyContinue | Select-Object -First 1 } else { $null }
$proc    = if ($pidHeld) { Get-Process -Id $pidHeld -ErrorAction SilentlyContinue } else { $null }

Write-Host "PROCESSUS" -ForegroundColor Cyan
if ($proc) {
    $uptime = (Get-Date) - $proc.StartTime
    $cores  = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
    Write-Host ("  en service      PID {0}, depuis {1:hh\:mm\:ss}" -f $proc.Id, $uptime)
    Write-Host ("  mémoire         {0:N1} Mo" -f ($proc.WorkingSet64 / 1MB))
    Write-Host ("  cœurs de l'hôte {0}" -f $cores)
}
else {
    Write-Host "  arrêté" -ForegroundColor Yellow
    Write-Host "  démarrer : .\scripts\agent-start.ps1"
}

# ---- Ce que l'agent dit de lui-même ---------------------------------------

Write-Host ""
Push-Location $AgentSrc
try {
    & python 'agent.py' 'status' '--config' $Config
}
finally { Pop-Location }

# ---- Journal ---------------------------------------------------------------

Write-Host ""
if (-not (Test-Path $LogFile)) {
    Write-Host "Aucun journal : l'agent n'a pas encore tourné en arrière-plan." -ForegroundColor Yellow
    Write-Host "(en mode -Foreground, la sortie va directement dans le terminal)"
    return
}

if ($Follow) {
    Write-Host "JOURNAL — suivi en direct, Ctrl+C pour sortir" -ForegroundColor Cyan
    Get-Content $LogFile -Tail $Lines -Wait
}
else {
    Write-Host "JOURNAL — $Lines dernières lignes" -ForegroundColor Cyan
    Get-Content $LogFile -Tail $Lines
    Write-Host ""
    Write-Host "Suivi en direct : .\scripts\agent-status.ps1 -Follow"
}
