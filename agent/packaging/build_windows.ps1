<#
.SYNOPSIS
    Fabrique le paquet d'installation Windows de l'agent CBC.

.DESCRIPTION
    Produit un dossier autonome, puis une archive ZIP a copier sur les
    machines a equiper. Le paquet contient trois choses et rien d'autre :

      cbc-agent.exe          l'agent gele, sans dependance Python
      Install-CbcAgent.ps1   installation, mise a jour, bascule, retrait
      LISEZ-MOI.txt          la marche a suivre, hors de tout navigateur

    **Reecrit.** Le script precedent construisait un « MSI » qui n'en etait
    pas un -- il assemblait une arborescence de fichiers sans jamais appeler
    d'outil de packaging -- et ecrivait dans la configuration livree un
    `enrollment_token: your-token-here` qui aurait ete diffuse avec chaque
    installation. Le jeton arrive desormais a l'enrolement, une seule fois.

.PARAMETER Version
    Etiquette du paquet. Par defaut, la version declaree par l'agent.

.PARAMETER SkipBuild
    Reutilise l'executable deja gele. Utile pour retoucher l'installateur
    sans repayer les deux minutes de PyInstaller.

.EXAMPLE
    .\build_windows.ps1
#>
[CmdletBinding()]
param(
    [string] $Version,
    [switch] $SkipBuild
)

$ErrorActionPreference = 'Stop'

$PackagingDir = $PSScriptRoot
$AgentDir = Split-Path -Parent $PackagingDir
$RepoRoot = Split-Path -Parent $AgentDir
$DistDir = Join-Path $PackagingDir 'dist'
$BuildDir = Join-Path $PackagingDir 'build'

function Write-Etape([string] $Texte) {
    Write-Host ""
    Write-Host "  $Texte" -ForegroundColor Cyan
}

if (-not $Version) {
    $ligne = Select-String -Path (Join-Path $AgentDir 'src\enrollment.py') -Pattern 'AGENT_VERSION\s*=\s*"([^"]+)"'
    $Version = if ($ligne) { $ligne.Matches[0].Groups[1].Value } else { '0.0.0' }
}

Write-Host ""
Write-Host "  Paquet agent CBC Supervision $Version" -ForegroundColor Green

$Bundle = Join-Path $DistDir "cbc-agent-$Version-windows"

if (-not $SkipBuild) {
    Write-Etape "Gel de l'agent (PyInstaller)"
    if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
        throw "pyinstaller introuvable. Installer : pip install pyinstaller"
    }
    Remove-Item $BuildDir -Recurse -Force -ErrorAction SilentlyContinue
    Push-Location $RepoRoot
    try {
        pyinstaller --noconfirm --clean `
            --distpath (Join-Path $PackagingDir 'exe') `
            --workpath $BuildDir `
            (Join-Path $PackagingDir 'agent.spec')
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller a echoue (code $LASTEXITCODE)." }
    } finally {
        Pop-Location
    }
}

$Exe = Join-Path $PackagingDir 'exe\cbc-agent.exe'
if (-not (Test-Path $Exe)) {
    throw "Executable introuvable : $Exe. Relancer sans -SkipBuild."
}

Write-Etape "Assemblage du paquet"
Remove-Item $Bundle -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $Bundle -Force | Out-Null

Copy-Item $Exe (Join-Path $Bundle 'cbc-agent.exe')
Copy-Item (Join-Path $PackagingDir 'Install-CbcAgent.ps1') $Bundle

# Le mode d'emploi voyage avec le paquet : celui qui installe est rarement
# celui qui a lu la documentation, et il n'a pas toujours le depot sous la
# main -- ni meme un navigateur, sur un serveur de production.
$Lisez = @"
AGENT CBC SUPERVISION $Version
===============================================================

Ouvrir PowerShell EN ADMINISTRATEUR dans ce dossier.

1. INSTALLER
   Reclamer un jeton d'enrolement dans la plateforme
   (Parametres > Jetons d'enrolement). Il ne sert qu'une fois.

   .\Install-CbcAgent.ps1 -Action Install ``
       -ServerUrl https://sentinel.cbc.cm:8443 ``
       -Token <le-jeton> ``
       -MachineType server

   -MachineType vaut « server » ou « workstation » : il determine les
   seuils herites par defaut.

   Plateforme de laboratoire en HTTP clair : ajouter -NoVerifyTls.

2. VERIFIER
   .\Install-CbcAgent.ps1 -Action Status

   Affiche l'identifiant de l'hote, la plateforme jointe, l'etat de la
   liaison et celui du service.

3. METTRE A JOUR
   Deballer le nouveau paquet, puis :
   .\Install-CbcAgent.ps1 -Action Update

   L'hote garde son identifiant, son historique et ses seuils. Aucun
   jeton n'est consomme. En cas d'echec, la version precedente est
   remise en place automatiquement.

4. CHANGER DE PLATEFORME (passage en production)
   .\Install-CbcAgent.ps1 -Action Configure ``
       -ServerUrl https://sentinel-prod.cbc.cm:8443

   L'adresse change, l'identite reste. Ni reenrolement, ni jeton, ni
   perte d'historique -- ce qui compte quand on bascule deux cents
   machines.

5. DESINSTALLER
   .\Install-CbcAgent.ps1 -Action Uninstall

   La plateforme est prevenue AVANT tout effacement : c'est ce qui
   distingue un retrait voulu d'une panne. Sans ce signalement, l'hote
   resterait affiche « hors ligne » et alerterait pour une absence
   pourtant decidee.

   Si la plateforme est injoignable, le retrait s'arrete et le dit.
   -Force passe outre, a charge d'aller nettoyer la fiche a la main.

===============================================================
CE QUE L'AGENT REMONTE
  - processeur, memoire, disques et partitions
  - services Windows designes par la plateforme
  - presence et date de fichiers surveilles
  - inventaire des applications et pilotes installes

CE QU'IL N'EMPORTE JAMAIS
  - aucun contenu de fichier, seulement leur presence et leur date
  - aucun mot de passe : le jeton d'enrolement cede la place a une cle
    propre a cet hote, des le premier contact

OU VIT QUOI
  Programme      : %ProgramFiles%\CBC Agent
  Etat et cles   : %ProgramData%\CBC Agent
  Service        : CBCAgent (demarrage automatique, relance sur echec)
"@
Set-Content -Path (Join-Path $Bundle 'LISEZ-MOI.txt') -Value $Lisez -Encoding UTF8

Write-Etape "Archive"
$Zip = "$Bundle.zip"
Remove-Item $Zip -Force -ErrorAction SilentlyContinue
Compress-Archive -Path "$Bundle\*" -DestinationPath $Zip

$taille = [math]::Round((Get-Item $Zip).Length / 1MB, 1)
Write-Host ""
Write-Host "  Paquet pret : $Zip ($taille Mo)" -ForegroundColor Green
Write-Host "  Copier l'archive sur la machine a equiper, la deballer,"
Write-Host "  puis suivre LISEZ-MOI.txt."
Write-Host ""
