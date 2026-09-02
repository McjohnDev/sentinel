<#
.SYNOPSIS
    Lance un agent CBC Supervision de démonstration sur ce poste.

.DESCRIPTION
    Enrôle ce poste auprès d'une plateforme de test, puis fait battre l'agent
    jusqu'à Ctrl+C. Destiné à voir le produit fonctionner sur une machine
    réelle — pas à installer un agent de production.

    Trois précautions, parce que ce script tourne sur un poste de travail :

      * l'état vit dans un répertoire à part (par défaut sous %LOCALAPPDATA%),
        jamais dans ProgramData. Le poste n'est donc pas « enrôlé » au sens
        d'une installation, et tout s'efface en supprimant un dossier ;
      * le mode d'exécution est déclaré « console », pour que la fiche d'hôte
        dise la vérité : un agent lancé à la main disparaît à la fermeture de
        session ;
      * le jeton n'est jamais écrit dans un fichier du dépôt.

.PARAMETER ServerUrl
    URL de la plateforme. Par défaut http://127.0.0.1:8443 (pile Docker locale).

.PARAMETER Token
    Jeton d'enrôlement émis depuis Paramètres → Jetons d'enrôlement.
    En laboratoire, la pile Docker accepte « demo-token-123 ».

.PARAMETER Interval
    Secondes entre deux battements. 10 pour une démonstration ; 30 en usage réel.

.PARAMETER Reset
    Oublie l'enrôlement de démonstration précédent et repart de zéro.

.EXAMPLE
    .\scripts\run-test-agent.ps1 -Token demo-token-123

.EXAMPLE
    .\scripts\run-test-agent.ps1 -ServerUrl https://supervision.cbc.local:8443 -Token a1b2c3d4e5 -Interval 10
#>

[CmdletBinding()]
param(
    [string]$ServerUrl = "http://127.0.0.1:8443",
    [string]$Token,
    [int]$Interval = 10,
    [switch]$Reset
)

$ErrorActionPreference = "Stop"
$script:started = $false

$repo = Split-Path -Parent $PSScriptRoot
$agentSrc = Join-Path $repo "agent\src"
$cli = Join-Path $agentSrc "cli.py"

if (-not (Test-Path $cli)) {
    Write-Error "Agent introuvable : $cli. Lancer ce script depuis le dépôt Sentinel."
}

# État isolé : ce poste n'est pas « installé », il est prêté à une démonstration.
$stateDir = Join-Path $env:LOCALAPPDATA "CBC Agent Demo"
$env:CBC_AGENT_STATE_DIR = $stateDir
# La fiche d'hôte dira « console » : un agent lancé à la main s'arrête avec
# la session, et cela doit se voir plutôt que de ressembler à une panne.
$env:CBC_AGENT_RUN_MODE = "console"

if ($Reset -and (Test-Path $stateDir)) {
    Remove-Item -Recurse -Force $stateDir
    Write-Host "État de démonstration précédent effacé." -ForegroundColor Yellow
}
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

function Get-Python {
    foreach ($candidate in @("python", "py")) {
        $found = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($found) { return $found.Source }
    }
    Write-Error "Python introuvable dans le PATH."
}
$python = Get-Python

Write-Host ""
Write-Host "  Agent de démonstration CBC Supervision" -ForegroundColor Cyan
Write-Host "  Plateforme : $ServerUrl"
Write-Host "  État       : $stateDir"
Write-Host "  Cadence    : $Interval s"
Write-Host ""

# Les dépendances de l'agent, vérifiées avant d'annoncer quoi que ce soit :
# échouer après le message d'accueil laisse croire que l'enrôlement a commencé.
& $python -c "import psutil, requests, yaml" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Dépendances manquantes. Installation…" -ForegroundColor Yellow
    & $python -m pip install -q -r (Join-Path $repo "agent\requirements.txt")
    if ($LASTEXITCODE -ne 0) { Write-Error "Installation des dépendances impossible." }
}

Push-Location $agentSrc
try {
    $status = & $python $cli status 2>&1 | Out-String
    $alreadyEnrolled = $status -match "Enrôlement\s*:\s*[0-9A-F]{6}"

    if (-not $alreadyEnrolled) {
        if (-not $Token) {
            Write-Host "  Aucun jeton fourni." -ForegroundColor Red
            Write-Host "  Émettre un jeton dans Paramètres → Jetons d'enrôlement, puis :"
            Write-Host "     .\scripts\run-test-agent.ps1 -Token <jeton>" -ForegroundColor Gray
            Write-Host "  En laboratoire Docker, « demo-token-123 » est accepté."
            exit 2
        }

        Write-Host "  Enrôlement…" -ForegroundColor Cyan
        & $python $cli enroll --token $Token --server-url $ServerUrl
        if ($LASTEXITCODE -ne 0) {
            Write-Host ""
            Write-Host "  Enrôlement refusé. Vérifier que la plateforme répond sur $ServerUrl" -ForegroundColor Red
            Write-Host "  et que le jeton n'a pas déjà été consommé (ils sont à usage unique)." -ForegroundColor Red
            exit 1
        }
    }
    else {
        Write-Host "  Ce poste est déjà enrôlé pour la démonstration." -ForegroundColor Green
        Write-Host "  Relancer avec -Reset pour repartir de zéro."
    }

    Write-Host ""
    & $python $cli status
    Write-Host ""
    $script:started = $true
    Write-Host "  Battement en cours — Ctrl+C pour arrêter." -ForegroundColor Cyan
    Write-Host "  L'hôte doit apparaître « actif » dans Parc dans les secondes qui suivent."
    Write-Host ""

    & $python $cli run --server-url $ServerUrl --interval $Interval
}
finally {
    Pop-Location
    # L'épilogue ne s'affiche que si l'agent a réellement battu : annoncer
    # « hôte hors ligne » après un refus d'enrôlement décrirait un état qui
    # n'a jamais existé.
    if ($script:started) {
    Write-Host ""
    Write-Host "  Agent arrêté. L'hôte passera « hors ligne » après le délai de la plateforme." -ForegroundColor Yellow
    Write-Host "  Pour le retirer proprement du parc :" -ForegroundColor Gray
    Write-Host "     `$env:CBC_AGENT_STATE_DIR='$stateDir'; python `"$cli`" uninstall --reason 'fin de demonstration'" -ForegroundColor Gray
    Write-Host "  Pour tout effacer localement :" -ForegroundColor Gray
    Write-Host "     Remove-Item -Recurse -Force `"$stateDir`"" -ForegroundColor Gray
    Write-Host ""
    }
}
