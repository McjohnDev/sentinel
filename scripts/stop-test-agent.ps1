<#
.SYNOPSIS
    Arrête et désinstalle l'agent de démonstration lancé sur ce poste.

.DESCRIPTION
    Pendant du script `run-test-agent.ps1`. Trois gestes, dans cet ordre, et
    l'ordre compte :

      1. arrêter le processus qui bat encore, s'il tourne ;
      2. **signaler le désenrôlement** à la plateforme — c'est ce qui
         distingue un retrait voulu d'une panne. Sans lui, l'hôte reste
         « hors ligne » dans le parc et continue d'alerter pour une absence
         décidée, bruit qu'on ne distingue pas d'un vrai incident ;
      3. effacer l'état local.

    L'identité machine est conservée par défaut : une nouvelle démonstration
    sur ce poste retombera alors sur le **même** hôte et son historique, au
    lieu d'en créer un second. `-Purge` l'efface aussi, pour repartir d'un
    poste réellement inconnu de la plateforme.

.PARAMETER ServerUrl
    Plateforme à prévenir. Par défaut http://127.0.0.1:8443.

.PARAMETER Reason
    Motif transmis et conservé dans l'audit de la plateforme.

.PARAMETER Purge
    Efface aussi l'identité machine et le répertoire d'état.

.PARAMETER Force
    Désinstalle même si la plateforme ne peut pas être prévenue. À réserver
    à une machine qui ne rejoindra pas le réseau : l'hôte restera affiché
    hors ligne jusqu'à son retrait manuel depuis l'interface.

.EXAMPLE
    .\scripts\stop-test-agent.ps1

.EXAMPLE
    .\scripts\stop-test-agent.ps1 -Purge -Reason "fin de la demonstration"
#>

[CmdletBinding()]
param(
    [string]$ServerUrl = "http://127.0.0.1:8443",
    [string]$Reason = "fin de demonstration",
    [switch]$Purge,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$script:wasEnrolled = $true

$repo = Split-Path -Parent $PSScriptRoot
$agentSrc = Join-Path $repo "agent\src"
$cli = Join-Path $agentSrc "cli.py"
$stateDir = Join-Path $env:LOCALAPPDATA "CBC Agent Demo"

if (-not (Test-Path $cli)) {
    Write-Error "Agent introuvable : $cli. Lancer ce script depuis le dépôt Sentinel."
}

$env:CBC_AGENT_STATE_DIR = $stateDir

function Get-Python {
    foreach ($candidate in @("python", "py")) {
        $found = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($found) { return $found.Source }
    }
    Write-Error "Python introuvable dans le PATH."
}
$python = Get-Python

Write-Host ""
Write-Host "  Arrêt de l'agent de démonstration" -ForegroundColor Cyan
Write-Host "  État : $stateDir"
Write-Host ""

if (-not (Test-Path $stateDir)) {
    Write-Host "  Aucun agent de démonstration sur ce poste — rien à faire." -ForegroundColor Green
    Write-Host ""
    exit 0
}

# --- 1. Arrêter le processus qui bat encore ------------------------------
# Le verrou d'instance porte le PID du détenteur : on s'en sert pour viser
# le bon processus plutôt que de tuer tout Python qui traîne sur le poste.
$lock = Join-Path $stateDir "agent.lock"
if (Test-Path $lock) {
    $held = (Get-Content $lock -Raw).Trim()
    $pidValue = 0
    if ([int]::TryParse($held, [ref]$pidValue) -and $pidValue -gt 0) {
        $proc = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "  Arrêt du processus $pidValue…" -ForegroundColor Yellow
            Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 700
        }
        else {
            Write-Host "  Verrou périmé (processus $pidValue absent)." -ForegroundColor Gray
        }
    }
    Remove-Item $lock -Force -ErrorAction SilentlyContinue
}
else {
    Write-Host "  Aucun agent en cours d'exécution." -ForegroundColor Gray
}

# --- 2. Prévenir la plateforme -------------------------------------------
Push-Location $agentSrc
try {
    $args = @($cli, "uninstall", "--reason", $Reason, "--server-url", $ServerUrl)
    if ($Force) { $args += "--force" }

    Write-Host "  Signalement du désenrôlement…" -ForegroundColor Cyan
    $output = & $python @args 2>&1 | Out-String
    $code = $LASTEXITCODE
    Write-Host $output.TrimEnd()
    # Distinguer « prévenu » de « rien à prévenir » : annoncer un
    # désenrôlement qui n'a pas eu lieu décrirait un état que la plateforme
    # ne connaît pas.
    $script:wasEnrolled = $output -notmatch "n'est pas enrôlé"

    if ($code -ne 0 -and -not $Force) {
        Write-Host ""
        Write-Host "  La plateforme n'a pas été prévenue : les jetons sont conservés." -ForegroundColor Red
        Write-Host "  L'hôte resterait affiché « hors ligne » et continuerait d'alerter." -ForegroundColor Red
        Write-Host "  Relancer quand la plateforme répond, ou forcer :" -ForegroundColor Gray
        Write-Host "     .\scripts\stop-test-agent.ps1 -Force" -ForegroundColor Gray
        Write-Host ""
        exit 1
    }
}
finally {
    Pop-Location
}

# --- 3. Effacer l'état local ---------------------------------------------
if ($Purge) {
    Remove-Item -Recurse -Force $stateDir -ErrorAction SilentlyContinue
    Write-Host ""
    Write-Host "  État local effacé, identité machine comprise." -ForegroundColor Green
    Write-Host "  Une prochaine démonstration créera un hôte entièrement nouveau."
}
elseif ($script:wasEnrolled) {
    Write-Host ""
    Write-Host "  Hôte marqué désinstallé sur la plateforme." -ForegroundColor Green
    Write-Host "  L'identité machine est conservée : une prochaine démonstration"
    Write-Host "  retrouvera le même hôte et son historique."
    Write-Host "  Utiliser -Purge pour repartir d'un poste inconnu de la plateforme." -ForegroundColor Gray
}
else {
    Write-Host ""
    Write-Host "  Ce poste n'était pas enrôlé : rien n'a été signalé." -ForegroundColor Green
}
Write-Host ""
