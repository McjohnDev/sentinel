<#
.SYNOPSIS
    Installe, met a jour, reconfigure ou retire l'agent CBC Supervision.

.DESCRIPTION
    Un seul script pour toute la vie de l'agent sur une machine. Quatre
    actions, et l'ordre des gestes compte dans chacune.

      Install    depose le binaire, ecrit la configuration, enrole l'hote,
                 enregistre le service et le demarre.
      Update     remplace le binaire en conservant identite, jetons et
                 historique. Aucun jeton n'est consomme.
      Configure  change l'adresse de la plateforme -- le passage en
                 production -- sans reenroler.
      Uninstall  previent la plateforme, puis retire service et fichiers.

    Le desenrolement est signale AVANT tout effacement local : c'est ce qui
    distingue un retrait voulu d'une panne. Sans lui, l'hote reste « hors
    ligne » dans le parc et continue d'alerter pour une absence decidee --
    un bruit qu'on ne distingue plus d'un vrai incident.

.PARAMETER Action
    Install | Update | Configure | Uninstall | Status

.PARAMETER ServerUrl
    Adresse de la plateforme, par exemple https://sentinel.cbc.cm:8443

.PARAMETER Token
    Jeton d'enrolement a usage unique. Requis pour Install.

.PARAMETER MachineType
    server ou workstation. Determine les seuils herites par defaut.

.PARAMETER NoVerifyTls
    N'exige pas un certificat valide de la plateforme. Reserve aux
    plateformes de laboratoire servant du HTTP en clair.

.PARAMETER Force
    Uninstall : retire meme si la plateforme ne peut pas etre prevenue.
    Install   : reinstalle par-dessus une installation existante.

.EXAMPLE
    .\Install-CbcAgent.ps1 -Action Install -ServerUrl https://sentinel.cbc.cm:8443 -Token A1B2C3D4 -MachineType server

.EXAMPLE
    .\Install-CbcAgent.ps1 -Action Configure -ServerUrl https://sentinel-prod.cbc.cm:8443

.EXAMPLE
    .\Install-CbcAgent.ps1 -Action Uninstall
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Install', 'Update', 'Configure', 'Uninstall', 'Status')]
    [string] $Action,

    [string] $ServerUrl,
    [string] $Token,

    [ValidateSet('server', 'workstation')]
    [string] $MachineType = 'workstation',

    [switch] $NoVerifyTls,
    [switch] $Force,
    [string] $Reason = 'desinstallation demandee par l''exploitant'
)

$ErrorActionPreference = 'Stop'

# L'agent ecrit ses messages en UTF-8. Sans cette ligne la console Windows les
# decode en CP850 et « Hote » s'affiche « H¶te » : l'exploitant doute du
# binaire au moment ou il lit un diagnostic.
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

$InstallDir = Join-Path $env:ProgramFiles 'CBC Agent'
$ConfigPath = Join-Path $InstallDir 'config.yaml'
$ExePath = Join-Path $InstallDir 'cbc-agent.exe'
$ServiceName = 'CBCAgent'
$SourceExe = Join-Path $PSScriptRoot 'cbc-agent.exe'

function Write-Etape([string] $Texte) {
    Write-Host ""
    Write-Host "  $Texte" -ForegroundColor Cyan
}

function Write-Ok([string] $Texte) {
    Write-Host "  [ok] $Texte" -ForegroundColor Green
}

function Write-Avert([string] $Texte) {
    Write-Host "  [!]  $Texte" -ForegroundColor Yellow
}

function Assert-Administrateur {
    # Enregistrer un service et ecrire dans Program Files modifient la
    # machine. Echouer ici, avec un message clair, vaut mieux qu'echouer a
    # mi-parcours en laissant une installation a moitie faite.
    $identite = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identite)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Cette action requiert une console PowerShell ouverte en administrateur."
    }
}

function Test-ServiceInstalle {
    $null -ne (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)
}

function Stop-AgentService {
    if (Test-ServiceInstalle) {
        $svc = Get-Service -Name $ServiceName
        if ($svc.Status -ne 'Stopped') {
            Stop-Service -Name $ServiceName -Force
            # On attend l'arret reel : remplacer un binaire encore ouvert
            # echoue avec une erreur de partage que rien n'explique.
            $svc.WaitForStatus('Stopped', '00:00:30')
            Write-Ok "Service arrete."
        }
    }
}

function Write-Configuration([string] $Url, [bool] $VerifierTls) {
    $verif = if ($VerifierTls) { 'true' } else { 'false' }
    # Aucun jeton n'est ecrit ici : ce fichier reste sur disque et serait lu
    # par quiconque passe sur la machine. Le jeton ne sert qu'a l'enrolement,
    # une seule fois, et cede la place a une cle propre a cet hote.
    $contenu = @"
# Configuration de l'agent CBC Supervision.
# Ecrit par Install-CbcAgent.ps1 -- modifiable, mais preferer
#   cbc-agent.exe configure --server-url <adresse>
# qui conserve l'identite de l'hote et son historique.
server:
  url: $Url
  tls_verify: $verif
agent:
  machine_type: $MachineType
  timeout_seconds: 15
"@
    Set-Content -Path $ConfigPath -Value $contenu -Encoding UTF8
    Write-Ok "Configuration ecrite : $ConfigPath"
}

function Invoke-Agent([string[]] $Arguments) {
    # La sortie de l'agent part vers la console, et la fonction ne rend que le
    # code de retour.
    #
    # Sans le `Out-Host`, PowerShell verse tout le flux de sortie dans la
    # valeur de retour : `$code` valait alors les lignes affichees par l'agent
    # SUIVIES du code, et le message d'echec devenait
    # « Enrolement refuse (code Hote : ... 1) ». Illisible au seul moment ou
    # on a besoin de le lire.
    & $ExePath @Arguments | Out-Host
    return $LASTEXITCODE
}

function Get-AgentOutput([string[]] $Arguments) {
    # Rend la sortie de l'agent, pour les commandes qu'on interroge plutot
    # que d'en surveiller le code de retour (`version`).
    return (& $ExePath @Arguments 2>$null)
}

# ---------------------------------------------------------------- Status

if ($Action -eq 'Status') {
    if (-not (Test-Path $ExePath)) {
        Write-Avert "Agent non installe ($InstallDir introuvable)."
        exit 1
    }
    Write-Etape "Etat de l'agent"
    [void](Invoke-Agent @('--config', $ConfigPath, 'status'))
    if (Test-ServiceInstalle) {
        $svc = Get-Service -Name $ServiceName
        Write-Host "  Service       : $($svc.Status)"
    } else {
        Write-Host "  Service       : non enregistre"
    }
    exit 0
}

Assert-Administrateur

# --------------------------------------------------------------- Install

if ($Action -eq 'Install') {
    if (-not $ServerUrl) { throw "-ServerUrl est requis pour l'installation." }
    if (-not $Token) { throw "-Token est requis : l'enrolement consomme un jeton a usage unique." }
    if (-not (Test-Path $SourceExe)) {
        throw "cbc-agent.exe introuvable a cote du script ($SourceExe). Deballer l'archive complete."
    }
    if ((Test-Path $ExePath) -and -not $Force) {
        throw "Agent deja installe. Utiliser -Action Update pour le mettre a jour, ou -Force pour reinstaller."
    }

    Write-Etape "Installation de l'agent CBC Supervision"
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    Stop-AgentService
    Copy-Item $SourceExe $ExePath -Force
    Write-Ok "Binaire depose : $ExePath"

    Write-Configuration -Url $ServerUrl -VerifierTls (-not $NoVerifyTls)

    Write-Etape "Enrolement aupres de la plateforme"
    $code = Invoke-Agent @('--config', $ConfigPath, 'enroll', '--token', $Token, '--server-url', $ServerUrl)
    if ($code -ne 0) {
        # On n'enregistre pas un service qui ne saurait pas a qui parler.
        # Le laisser demarrer ferait un agent qui echoue en boucle, et la
        # cause resterait dans un journal que personne ne lira.
        throw "Enrolement refuse (code $code). Ni service ni demarrage : rien n'est laisse a moitie fait."
    }
    Write-Ok "Hote enrole."

    Write-Etape "Enregistrement du service Windows"
    $binPath = "`"$ExePath`" --config `"$ConfigPath`" run"
    sc.exe create $ServiceName binPath= $binPath start= auto DisplayName= "CBC Supervision Agent" | Out-Null
    sc.exe description $ServiceName "Agent de supervision CBC : remonte metriques, services et fichiers surveilles." | Out-Null
    # Redemarrage automatique : un agent qui meurt et ne revient pas laisse
    # l'hote muet, et le parc l'affiche « hors ligne » sans qu'aucune panne
    # reelle ne le justifie.
    sc.exe failure $ServiceName reset= 86400 actions= restart/5000/restart/15000/restart/60000 | Out-Null
    Start-Service -Name $ServiceName
    Write-Ok "Service enregistre et demarre."

    Write-Host ""
    Write-Host "  Installation terminee." -ForegroundColor Green
    Write-Host "  Plateforme : $ServerUrl"
    Write-Host "  Verifier   : .\Install-CbcAgent.ps1 -Action Status"
    exit 0
}

# ---------------------------------------------------------------- Update

if ($Action -eq 'Update') {
    if (-not (Test-Path $ExePath)) { throw "Agent non installe. Utiliser -Action Install." }
    if (-not (Test-Path $SourceExe)) { throw "cbc-agent.exe introuvable a cote du script ($SourceExe)." }

    Write-Etape "Mise a jour de l'agent"
    $avant = Get-AgentOutput @('version')
    Stop-AgentService

    # Le binaire sortant est conserve jusqu'au demarrage reussi du nouveau :
    # une mise a jour qui echoue ne doit pas laisser la machine sans agent.
    $sauvegarde = "$ExePath.precedent"
    Copy-Item $ExePath $sauvegarde -Force
    try {
        Copy-Item $SourceExe $ExePath -Force
        if (Test-ServiceInstalle) { Start-Service -Name $ServiceName }
        $apres = Get-AgentOutput @('version')
        Write-Ok "Version $avant -> $apres"
        Remove-Item $sauvegarde -Force -ErrorAction SilentlyContinue
    } catch {
        Write-Avert "Mise a jour echouee : retour a la version precedente."
        Copy-Item $sauvegarde $ExePath -Force
        if (Test-ServiceInstalle) { Start-Service -Name $ServiceName -ErrorAction SilentlyContinue }
        throw
    }

    # Ni reenrolement ni jeton : l'hote garde son identifiant, son historique
    # et ses seuils. Une mise a jour qui creerait une seconde ligne dans le
    # parc ferait perdre la trace de la premiere.
    Write-Host ""
    Write-Host "  Mise a jour terminee. Identite et historique conserves." -ForegroundColor Green
    exit 0
}

# ------------------------------------------------------------- Configure

if ($Action -eq 'Configure') {
    if (-not $ServerUrl) { throw "-ServerUrl est requis." }
    if (-not (Test-Path $ExePath)) { throw "Agent non installe." }

    Write-Etape "Changement d'adresse de la plateforme"
    $arguments = @('--config', $ConfigPath, 'configure', '--server-url', $ServerUrl)
    if ($NoVerifyTls) { $arguments += '--no-tls-verify' } else { $arguments += '--tls-verify' }
    $code = Invoke-Agent $arguments
    if ($code -ne 0) { throw "Changement refuse (code $code)." }

    # Le service relit sa configuration au demarrage seulement : sans
    # redemarrage, le reglage s'afficherait comme applique tout en laissant
    # l'agent parler a l'ancienne plateforme.
    if (Test-ServiceInstalle) {
        Restart-Service -Name $ServiceName
        Write-Ok "Service redemarre : le changement est effectif."
    } else {
        Write-Avert "Service non enregistre : demarrer l'agent pour appliquer."
    }
    exit 0
}

# ------------------------------------------------------------- Uninstall

if ($Action -eq 'Uninstall') {
    if (-not (Test-Path $ExePath)) {
        Write-Avert "Agent non installe."
        exit 0
    }

    Write-Etape "Signalement du desenrolement a la plateforme"
    # D'abord prevenir, ensuite effacer. L'inverse laisserait un hote que la
    # plateforme croit en panne, et qui alerterait pour une absence decidee.
    $arguments = @('--config', $ConfigPath, 'uninstall', '--reason', $Reason)
    if ($Force) { $arguments += '--force' }
    $code = Invoke-Agent $arguments
    if ($code -ne 0 -and -not $Force) {
        throw @"
Plateforme injoignable : le desenrolement n'a pas ete signale (code $code).

Retirer l'agent maintenant laisserait un hote affiche « hors ligne » dans le
parc, alertant pour une absence pourtant decidee. Retablir la liaison, ou
relancer avec -Force en assumant d'aller nettoyer la fiche a la main.
"@
    }
    if ($code -eq 0) { Write-Ok "Desenrolement signale." }

    Write-Etape "Retrait du service et des fichiers"
    Stop-AgentService
    if (Test-ServiceInstalle) {
        sc.exe delete $ServiceName | Out-Null
        Write-Ok "Service retire."
    }
    Remove-Item $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Ok "Fichiers retires : $InstallDir"

    # L'etat local part avec le reste : y laisser une identite ferait
    # ressusciter le meme hote a la prochaine installation, avec des jetons
    # que la plateforme a deja revoques.
    $etat = Join-Path $env:ProgramData 'CBC Agent'
    if (Test-Path $etat) {
        Remove-Item $etat -Recurse -Force -ErrorAction SilentlyContinue
        Write-Ok "Etat local efface : $etat"
    }

    Write-Host ""
    Write-Host "  Desinstallation terminee." -ForegroundColor Green
    exit 0
}
