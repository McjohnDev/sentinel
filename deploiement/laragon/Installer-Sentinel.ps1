<#
.SYNOPSIS
    Installe le serveur Sentinel sur la machine Laragon, sans accès Internet.

.DESCRIPTION
    Ce script fait la partie mécanique : environnement Python, dépendances
    depuis le dépôt local, fichier de configuration, vérifications.

    Il s'arrête net et le dit dès qu'une condition manque, plutôt que de
    poursuivre à moitié — une installation à demi faite coûte plus cher à
    diagnostiquer qu'un refus clair.

    Ce qu'il ne fait PAS, et qu'il vous rappellera à la fin : enregistrer le
    service Windows, poser la configuration nginx, ouvrir le pare-feu. Ces
    trois gestes modifient la machine au-delà de ce dossier ; ils méritent
    d'être posés à la main, en connaissance de cause.

.PARAMETER MotDePasseBase
    Mot de passe du rôle PostgreSQL `cbc_user` créé en phase 2.

.PARAMETER Reinstaller
    Recrée l'environnement Python même s'il existe déjà.

.EXAMPLE
    .\Installer-Sentinel.ps1 -MotDePasseBase 'le-mot-de-passe'
#>
[CmdletBinding()]
param(
    [string] $MotDePasseBase,
    [switch] $Reinstaller
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

$Base = $PSScriptRoot
$Paquets = Join-Path $Base 'paquets'
$Requirements = Join-Path $Base 'requirements.txt'
$Venv = Join-Path $Base '.venv'
$VenvPython = Join-Path $Venv 'Scripts\python.exe'
$EnvFichier = Join-Path $Base '.env'
$EnvModele = Join-Path $Base 'config\env.modele'

function Etape([string] $t) { Write-Host ""; Write-Host "  $t" -ForegroundColor Cyan }
function Ok([string] $t)    { Write-Host "  [ok] $t" -ForegroundColor Green }
function Avert([string] $t) { Write-Host "  [!]  $t" -ForegroundColor Yellow }

function Invoke-Natif {
    <#
      Lance un programme natif sans laisser sa sortie d'erreur devenir fatale.

      Avec $ErrorActionPreference = 'Stop', PowerShell transforme toute
      ecriture sur stderr par un programme natif en exception terminale, meme
      quand le programme rend 0. `pip` emet couramment des avertissements sur
      stderr — un paquet retire de PyPI, une version plus recente disponible.
      Le script mourait alors sur une installation reussie.

      Seul le code de retour decide de l'echec.
    #>
    param(
        [Parameter(Mandatory)][string] $Fichier,
        [string[]] $Arguments = @()
    )

    $precedent = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Fichier @Arguments 2>&1 | ForEach-Object { Write-Host "      $_" }
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $precedent
    }
}

Write-Host ""
Write-Host "  Sentinel — installation du serveur" -ForegroundColor Green
Write-Host "  Dossier : $Base"

# ------------------------------------------------------------ 1. Python

Etape "Recherche du Python de Laragon"

# Le script est déposé dans <LARAGON>\usr\sentinel-api : la racine Laragon
# est donc deux niveaux au-dessus. On ne devine pas un chemin en dur, qui
# serait faux dès que Laragon est installé ailleurs.
$LaragonRoot = Split-Path (Split-Path $Base -Parent) -Parent
$Python = Get-ChildItem (Join-Path $LaragonRoot 'bin\python') -Directory -ErrorAction SilentlyContinue |
    ForEach-Object { Join-Path $_.FullName 'python.exe' } |
    Where-Object { Test-Path $_ } |
    Select-Object -First 1

if (-not $Python) {
    throw @"
Python introuvable sous $LaragonRoot\bin\python.

Dans Laragon : Menu > Outils > Python, ou vérifier que le composant est
présent. Ce script attend l'arborescence standard de Laragon.
"@
}
$precedent = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try { $version = (& $Python --version 2>&1) } finally { $ErrorActionPreference = $precedent }
Ok "$version — $Python"

# ------------------------------------------------- 2. Environnement virtuel

Etape "Environnement virtuel"

if ((Test-Path $Venv) -and $Reinstaller) {
    Remove-Item $Venv -Recurse -Force
    Avert "Environnement précédent supprimé (-Reinstaller)."
}

if (-not (Test-Path $VenvPython)) {
    $code = Invoke-Natif -Fichier $Python -Arguments @('-m', 'venv', $Venv)
    if ($code -ne 0) { throw "Création de l'environnement virtuel échouée (code $code)." }
    Ok "Créé : $Venv"
} else {
    Ok "Déjà présent — réutilisé."
}

# ------------------------------------------------------- 3. Dépendances

Etape "Dépendances, depuis le dépôt local (aucun accès Internet requis)"

if (-not (Test-Path $Paquets)) { throw "Dépôt de paquets introuvable : $Paquets" }
if (-not (Test-Path $Requirements)) { throw "requirements.txt introuvable : $Requirements" }

$nb = (Get-ChildItem $Paquets -Filter *.whl).Count
Write-Host "  $nb paquets disponibles hors ligne."

Invoke-Natif -Fichier $VenvPython -Arguments @(
    '-m', 'pip', 'install', '--quiet', '--no-index', '--find-links', $Paquets, '--upgrade', 'pip') | Out-Null
$code = Invoke-Natif -Fichier $VenvPython -Arguments @(
    '-m', 'pip', 'install', '--no-index', '--find-links', $Paquets, '-r', $Requirements)
if ($code -ne 0) {
    throw @"
Installation des dépendances échouée.

Si le message cite un paquet absent, c'est que le dépôt a été construit pour
un autre Python. Vérifier que la version ci-dessus est bien une 3.13.
"@
}
Ok "Dépendances installées."

# --------------------------------------------------------- 4. Configuration

Etape "Fichier de configuration"

if (Test-Path $EnvFichier) {
    Ok ".env déjà présent — laissé tel quel."
} else {
    if (-not (Test-Path $EnvModele)) { throw "Modèle introuvable : $EnvModele" }
    if (-not $MotDePasseBase) {
        throw @"
Il manque -MotDePasseBase.

C'est le mot de passe du rôle PostgreSQL cbc_user créé en phase 2. Le script
ne l'invente pas : il doit correspondre à ce qui a été posé dans la base.
"@
    }

    # Clé de signature propre à cette machine. Reprendre celle d'un autre
    # environnement ferait accepter ici un jeton émis ailleurs.
    $octets = New-Object byte[] 48
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($octets)
    $cle = [Convert]::ToBase64String($octets)

    (Get-Content $EnvModele -Raw -Encoding UTF8).
        Replace('A_REMPLACER', $MotDePasseBase).
        Replace('A_GENERER', $cle) |
        Set-Content $EnvFichier -Encoding UTF8 -NoNewline

    Ok ".env écrit, clé de signature générée."
    Avert "Ce fichier porte le mot de passe de la base : ne pas le remettre dans le dépôt."
}

# ------------------------------------------------------- 5. Vérifications

Etape "Ce qui doit déjà tourner"

function Teste-Port([string] $hote, [int] $port, [string] $nom) {
    $c = New-Object Net.Sockets.TcpClient
    try {
        $c.Connect($hote, $port)
        Ok "$nom répond sur ${hote}:${port}"
        return $true
    } catch {
        Avert "$nom NE répond PAS sur ${hote}:${port}"
        return $false
    } finally { $c.Close() }
}

$pg = Teste-Port '127.0.0.1' 5432 'PostgreSQL'
$rd = Teste-Port '127.0.0.1' 6379 'Redis'

if (-not $pg) {
    throw @"
PostgreSQL est obligatoire : le serveur crée son schéma au démarrage et
échouera sans lui. Installer PostgreSQL 18.6, créer le rôle et la base
(phase 2 du plan), puis relancer ce script.
"@
}
if (-not $rd) {
    Avert @"
Redis absent. La plateforme démarre quand même — le cache est facultatif,
chaque appel est enveloppé — mais vous avez demandé Redis pour cette
version. Le démarrer depuis Laragon : Menu > Redis > Démarrer.
"@
}

# --------------------------------------------------------- 6. Essai à blanc

Etape "Essai de démarrage"

# On importe l'application sans servir : cela crée le schéma et prouve que
# la configuration tient, sans ouvrir de port ni laisser de processus.
Push-Location $Base
try {
    $code = Invoke-Natif -Fichier $VenvPython -Arguments @(
        '-c', "import src.main; print('application chargee, schema en place')")
    if ($code -ne 0) {
        throw "L'application n'a pas pu se charger. Le message ci-dessus dit pourquoi."
    }
} finally { Pop-Location }
Ok "L'application se charge et la base répond."

# ------------------------------------------------------------- 7. Comptes

Etape "Comptes initiaux"

$reponse = Read-Host "  Creer les comptes par defaut (admin/operator/readonly) ? [o/N]"
if ($reponse -match '^[oOyY]') {
    Push-Location $Base
    try { Invoke-Natif -Fichier $VenvPython -Arguments @('init_users.py') | Out-Null }
    finally { Pop-Location }
    Write-Host ""
    Avert @"
Les mots de passe de ces comptes sont ecrits en clair dans init_users.py
(Admin123! ...). Se connecter et les changer AVANT d'ouvrir le pare-feu.
"@
} else {
    Write-Host "  Ignore. A faire plus tard : .venv\Scripts\python init_users.py"
}

# --------------------------------------------------------------- Ce qui reste

Write-Host ""
Write-Host "  Installation terminee." -ForegroundColor Green
Write-Host ""
Write-Host "  Il reste trois gestes, en console administrateur :" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. Le service Windows — sans lui, rien ne repart au redemarrage"
Write-Host "       copier WinSW.exe ici sous le nom sentinel-api.exe"
Write-Host "       copier config\sentinel-api.xml a cote"
Write-Host "       .\sentinel-api.exe install ; .\sentinel-api.exe start"
Write-Host ""
Write-Host "  2. nginx — servir le tableau de bord et relayer l'API"
Write-Host "       adapter <LARAGON> dans config\sentinel.conf"
Write-Host "       le copier dans $LaragonRoot\etc\nginx\sites-enabled\"
Write-Host "       copier le contenu de tableau-de-bord\ dans $LaragonRoot\www\sentinel\"
Write-Host "       puis recharger nginx depuis Laragon"
Write-Host ""
Write-Host "  3. Le pare-feu — une seule ouverture entrante suffit"
Write-Host "       New-NetFirewallRule -DisplayName 'Sentinel - HTTP 80' ``"
Write-Host "         -Direction Inbound -Protocol TCP -LocalPort 80 ``"
Write-Host "         -Action Allow -Profile Domain,Private"
Write-Host ""
Write-Host "  Et surtout : changer les mots de passe par defaut avant le point 3."
Write-Host ""
