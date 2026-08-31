<#
.SYNOPSIS
  Arrête l'agent CBC qui tourne sur ce poste.

.DESCRIPTION
  Arrêt seul par défaut : l'agent reste enrôlé et la plateforme le verra
  passer hors ligne, ce qui est le comportement attendu d'une machine
  simplement éteinte.

  Avec -Uninstall, l'agent prévient d'abord la plateforme de son retrait
  définitif, puis efface son identité locale. À réserver au retrait réel d'un
  poste du parc — pas à un arrêt de maintenance.

.EXAMPLE
  .\scripts\agent-stop.ps1
  .\scripts\agent-stop.ps1 -Uninstall -Reason "poste remplacé"
#>
[CmdletBinding()]
param(
    [string] $Config,

    # Signaler le désenrôlement à la plateforme et effacer l'identité locale.
    [switch] $Uninstall,

    [string] $Reason
)

$ErrorActionPreference = 'Stop'

$Repo     = Split-Path -Parent $PSScriptRoot
$AgentSrc = Join-Path $Repo 'agent\src'
$LockFile = Join-Path $env:TEMP 'cbc-agent.pid'

if (-not $Config) { $Config = Join-Path $Repo 'agent\config.lab.yaml' }

# Le désenrôlement se fait AVANT l'arrêt : il a besoin de la clé
# d'authentification que l'agent conserve localement, et prévenir après avoir
# tout effacé n'est plus possible.
if ($Uninstall) {
    Push-Location $AgentSrc
    try {
        $args = @('agent.py', 'uninstall', '--config', $Config)
        if ($Reason) { $args += @('--reason', $Reason) }
        & python @args
    }
    finally { Pop-Location }
    Write-Host ""
}

# Cible : le PID inscrit dans le verrou d'instance. Chercher par ligne de
# commande attrape aussi le script qui fait la recherche — un filtre trop
# large finit par se tuer lui-même.
$targets = @()
if (Test-Path $LockFile) {
    $held = Get-Content $LockFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($held) { $targets += [int]$held }
}

# Repli si le verrou a disparu : on vise les interpréteurs Python lancés sur
# une configuration d'agent, en excluant explicitement le processus courant.
$fallback = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -like 'python*' -and
        $_.CommandLine -like '*agent.py*' -and
        $_.ProcessId -ne $PID
    }
foreach ($p in $fallback) { if ($targets -notcontains $p.ProcessId) { $targets += $p.ProcessId } }

if (-not $targets) {
    Write-Host "Aucun agent en cours d'exécution." -ForegroundColor Yellow
    exit 0
}

foreach ($id in $targets) {
    $proc = Get-Process -Id $id -ErrorAction SilentlyContinue
    if (-not $proc) { continue }

    # Les lanceurs (PyManager) tiennent le vrai interpréteur en enfant :
    # arrêter le parent seul laisserait l'agent orphelin mais vivant.
    Get-CimInstance Win32_Process -Filter "ParentProcessId = $id" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like 'python*' } |
        ForEach-Object {
            Write-Host "  arrêt du processus enfant $($_.ProcessId)"
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }

    Write-Host "  arrêt de l'agent $id"
    Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 2

$restants = Get-CimInstance Win32_Process |
    Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*agent.py*' -and $_.ProcessId -ne $PID }

if ($restants) {
    Write-Host "Processus encore vivants : $($restants.ProcessId -join ', ')" -ForegroundColor Red
    exit 1
}

# Le verrou est normalement retiré par l'agent lui-même à la sortie ; après un
# arrêt forcé il peut subsister et empêcherait un redémarrage.
if (Test-Path $LockFile) { Remove-Item $LockFile -Force -ErrorAction SilentlyContinue }

Write-Host "Agent arrêté." -ForegroundColor Green
if (-not $Uninstall) {
    Write-Host "Il reste enrôlé : la plateforme le verra passer hors ligne."
}
