<#
.SYNOPSIS
  Démarre l'agent CBC sur ce poste Windows.

.DESCRIPTION
  Deux modes :

    -Foreground   la sortie s'affiche dans le terminal, Ctrl+C arrête l'agent.
                  C'est le mode à utiliser pour garder un œil dessus depuis
                  un terminal (Cursor, VS Code, PowerShell).

    par défaut    l'agent part en arrière-plan, sa sortie va dans un fichier
                  journal, et le terminal reste libre.

  Dans les deux cas l'agent n'est PAS un service Windows : il ne survit ni à
  une fermeture de session, ni à un redémarrage. Pour cela, voir
  `agent-service.ps1 install`.

.EXAMPLE
  .\scripts\agent-start.ps1
  .\scripts\agent-start.ps1 -Foreground
  .\scripts\agent-start.ps1 -Config .\agent\config.yaml
#>
[CmdletBinding()]
param(
    # Fichier de configuration. Par défaut celui du laboratoire, qui vise la
    # pile Docker locale sur http://127.0.0.1:8443.
    [string] $Config,

    # Rester attaché au terminal et y afficher la sortie de l'agent.
    [switch] $Foreground,

    # Démarrer même si la configuration comporte un défaut bloquant.
    [switch] $Force
)

$ErrorActionPreference = 'Stop'

$Repo      = Split-Path -Parent $PSScriptRoot
$AgentSrc  = Join-Path $Repo 'agent\src'
$LogDir    = Join-Path $Repo 'agent\logs'
$LogFile   = Join-Path $LogDir 'windows-agent.log'

if (-not $Config) { $Config = Join-Path $Repo 'agent\config.lab.yaml' }
if (-not (Test-Path $Config)) {
    Write-Error "Configuration introuvable : $Config"
    exit 1
}

# Un agent déjà en service ne doit pas être doublé. On interroge le verrou
# d'instance plutôt que la liste des processus : c'est la source de vérité de
# l'agent lui-même, et une correspondance sur la ligne de commande finit par
# attraper le script qui la cherche.
$LockFile = Join-Path $env:TEMP 'cbc-agent.pid'
if (Test-Path $LockFile) {
    $existing = (Get-Content $LockFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($existing -and (Get-Process -Id $existing -ErrorAction SilentlyContinue)) {
        Write-Host "Un agent tourne déjà (PID $existing)." -ForegroundColor Yellow
        Write-Host "Arrêtez-le d'abord : .\scripts\agent-stop.ps1"
        exit 1
    }
}

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

$verb = @('run', '--config', $Config)
if ($Force) { $verb += '--force' }

Push-Location $AgentSrc
try {
    if ($Foreground) {
        Write-Host "Agent CBC — mode console, Ctrl+C pour arrêter" -ForegroundColor Cyan
        Write-Host "Configuration : $Config`n"
        & python 'agent.py' @verb
    }
    else {
        # -RedirectStandardError : l'agent journalise sur stderr.
        $proc = Start-Process -FilePath 'python' `
            -ArgumentList (@('agent.py') + $verb) `
            -WorkingDirectory $AgentSrc `
            -WindowStyle Hidden `
            -RedirectStandardError $LogFile `
            -RedirectStandardOutput (Join-Path $LogDir 'windows-agent.out.log') `
            -PassThru

        Start-Sleep -Seconds 6

        # Le PID rendu par Start-Process peut être celui d'un lanceur (PyManager
        # notamment) : le verrou porte celui du processus qui travaille vraiment.
        $real = if (Test-Path $LockFile) { Get-Content $LockFile | Select-Object -First 1 } else { $proc.Id }

        if (Get-Process -Id $real -ErrorAction SilentlyContinue) {
            Write-Host "Agent démarré (PID $real)" -ForegroundColor Green
            Write-Host "Configuration : $Config"
            Write-Host "Journal       : $LogFile"
            Write-Host ""
            Write-Host "Suivre en direct : .\scripts\agent-status.ps1 -Follow"
            Write-Host "Arrêter          : .\scripts\agent-stop.ps1"
        }
        else {
            Write-Host "L'agent s'est arrêté immédiatement. Dernières lignes :" -ForegroundColor Red
            if (Test-Path $LogFile) { Get-Content $LogFile -Tail 15 }
            exit 1
        }
    }
}
finally {
    Pop-Location
}
