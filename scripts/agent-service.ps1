<#
.SYNOPSIS
  Installe, retire ou pilote l'agent CBC en tant que service Windows.

.DESCRIPTION
  Un service démarre avec la machine, tourne sans session ouverte et survit
  au redémarrage — ce qu'un agent lancé en console ne fait pas.

  Nécessite une console PowerShell ouverte en administrateur : enregistrer un
  service modifie la configuration de la machine.

.PARAMETER Action
  install    enregistre le service et le démarre
  remove     arrête et désenregistre le service
  start      démarre le service installé
  stop       arrête le service installé
  status     état du service et de l'agent

.EXAMPLE
  .\scripts\agent-service.ps1 install
  .\scripts\agent-service.ps1 install -Config "C:\Program Files\CBC Agent\config.yaml"
  .\scripts\agent-service.ps1 status
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('install', 'remove', 'start', 'stop', 'status')]
    [string] $Action = 'status',

    [string] $Config
)

$ErrorActionPreference = 'Stop'

$Repo        = Split-Path -Parent $PSScriptRoot
$AgentSrc    = Join-Path $Repo 'agent\src'
$ServiceFile = Join-Path $AgentSrc 'windows_service.py'
$ServiceName = 'CBCAgent'

if (-not $Config) { $Config = Join-Path $Repo 'agent\config.lab.yaml' }

function Test-Elevated {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Require-Elevation {
    if (-not (Test-Elevated)) {
        Write-Host "Droits administrateur requis." -ForegroundColor Red
        Write-Host ""
        Write-Host "Ouvrez PowerShell en administrateur, puis :"
        Write-Host "  cd $Repo"
        Write-Host "  .\scripts\agent-service.ps1 $Action"
        exit 1
    }
}

function Show-Status {
    $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    Write-Host "SERVICE $ServiceName" -ForegroundColor Cyan
    if ($svc) {
        Write-Host "  état          : $($svc.Status)"
        Write-Host "  démarrage     : $($svc.StartType)"
        $wmi = Get-CimInstance Win32_Service -Filter "Name='$ServiceName'" -ErrorAction SilentlyContinue
        if ($wmi) {
            Write-Host "  compte        : $($wmi.StartName)"
            Write-Host "  commande      : $($wmi.PathName)"
        }
    }
    else {
        Write-Host "  non installé" -ForegroundColor Yellow
        Write-Host "  installer : .\scripts\agent-service.ps1 install   (en administrateur)"
    }

    Write-Host ""
    Push-Location $AgentSrc
    try { & python 'agent.py' 'status' '--config' $Config }
    finally { Pop-Location }
}

switch ($Action) {

    'install' {
        Require-Elevation

        # pywin32 fournit le dialogue avec le gestionnaire de services. Sans
        # lui, le binaire ne peut pas se déclarer et Windows échoue en 1053.
        & python -c "import win32serviceutil" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "pywin32 manquant. Installez-le :" -ForegroundColor Red
            Write-Host "  python -m pip install pywin32"
            exit 1
        }

        if (-not (Test-Path $Config)) {
            Write-Host "Configuration introuvable : $Config" -ForegroundColor Red
            exit 1
        }

        # Un service démarre dans C:\Windows\System32 : il ne trouverait pas
        # un config.yaml désigné par un chemin relatif. On fixe donc le chemin
        # absolu au niveau machine, lisible par le compte LocalSystem.
        $abs = (Resolve-Path $Config).Path
        [Environment]::SetEnvironmentVariable('CBC_AGENT_CONFIG', $abs, 'Machine')
        Write-Host "Configuration du service : $abs"

        Push-Location $AgentSrc
        try {
            & python $ServiceFile '--startup' 'auto' 'install'
            if ($LASTEXITCODE -ne 0) { throw "l'enregistrement du service a échoué (code $LASTEXITCODE)" }
        }
        finally { Pop-Location }

        # Redémarrage automatique après incident : sans cela, un agent tombé
        # reste tombé jusqu'à la prochaine intervention humaine.
        & sc.exe failure $ServiceName reset= 86400 actions= restart/60000/restart/60000/restart/300000 | Out-Null

        Start-Service -Name $ServiceName
        Start-Sleep -Seconds 5
        Write-Host ""
        Show-Status
    }

    'remove' {
        Require-Elevation
        $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if (-not $svc) { Write-Host "Service non installé."; exit 0 }

        if ($svc.Status -ne 'Stopped') { Stop-Service -Name $ServiceName -Force; Start-Sleep -Seconds 3 }

        Push-Location $AgentSrc
        try { & python $ServiceFile 'remove' }
        finally { Pop-Location }

        [Environment]::SetEnvironmentVariable('CBC_AGENT_CONFIG', $null, 'Machine')
        Write-Host "Service retiré." -ForegroundColor Green
        Write-Host "L'agent reste enrôlé. Pour le retirer du parc :"
        Write-Host "  .\scripts\agent-stop.ps1 -Uninstall"
    }

    'start'  { Require-Elevation; Start-Service -Name $ServiceName; Start-Sleep -Seconds 4; Show-Status }
    'stop'   { Require-Elevation; Stop-Service -Name $ServiceName -Force; Write-Host "Service arrêté." }
    'status' { Show-Status }
}
