<#
.SYNOPSIS
    Signe cbc-agent.exe, et verifie que la signature tient.

.DESCRIPTION
    Mesure faite sur un poste CBC sous Symantec Endpoint Protection 14.3 :
    le binaire NON signe se voit refuser toute socket -- WinError 10013, une
    erreur qui ne nomme jamais sa cause -- et cela reste vrai apres un
    changement d'empreinte, donc ce n'est pas une liste noire de hachage.
    Le meme binaire SIGNE passe, y compris avec un certificat auto-signe dont
    l'autorite n'est reconnue par personne : c'est l'absence de signature que
    SEP refuse.

    La signature sert aussi a ce qu'un exploitant puisse verifier que le
    binaire qu'il installe vient bien de la DSI et n'a pas ete remplace en
    chemin -- ce qu'un auto-signe, lui, n'atteste pas.

    Trois sources de certificat, par ordre de preference :

      -PfxPath      fichier .pfx remis par l'autorite de certification
      -Thumbprint   certificat deja present dans le magasin de la machine
      -SelfSigned   certificat cree a la volee -- LABORATOIRE UNIQUEMENT

    L'horodatage n'est pas optionnel. Sans lui, la signature devient invalide
    le jour ou le certificat expire, y compris sur les binaires deja
    installes : un parc entier cesserait de demarrer a une date connue
    d'avance et pour une raison que personne ne relierait a la signature.

.PARAMETER ExePath
    Binaire a signer. Par defaut cbc-agent.exe a cote de ce script.

.PARAMETER PfxPath
    Certificat de signature au format PFX.

.PARAMETER PfxPassword
    Mot de passe du PFX. Demande de facon masquee s'il est omis.

.PARAMETER Thumbprint
    Empreinte d'un certificat du magasin (Cert:\CurrentUser\My ou LocalMachine).

.PARAMETER SelfSigned
    Fabrique un certificat auto-signe. Suffit a debloquer un essai -- SEP
    accepte toute signature -- mais n'atteste de rien : SmartScreen avertira
    l'utilisateur, et une politique durcie exigerait un editeur reconnu.
    Pour un deploiement, utiliser la PKI interne CBC ou une autorite
    publique.

.PARAMETER TimestampServer
    Service d'horodatage RFC3161.

.EXAMPLE
    .\Sign-CbcAgent.ps1 -PfxPath .\cbc-codesign.pfx

.EXAMPLE
    .\Sign-CbcAgent.ps1 -Thumbprint 8A9F2C1B4E7D...

.EXAMPLE
    .\Sign-CbcAgent.ps1 -SelfSigned      # laboratoire
#>
[CmdletBinding(DefaultParameterSetName = 'Pfx')]
param(
    [string] $ExePath = (Join-Path $PSScriptRoot 'cbc-agent.exe'),

    [Parameter(ParameterSetName = 'Pfx')]
    [string] $PfxPath,

    [Parameter(ParameterSetName = 'Pfx')]
    [System.Security.SecureString] $PfxPassword,

    [Parameter(ParameterSetName = 'Store', Mandatory = $true)]
    [string] $Thumbprint,

    [Parameter(ParameterSetName = 'SelfSigned', Mandatory = $true)]
    [switch] $SelfSigned,

    [string] $TimestampServer = 'http://timestamp.digicert.com'
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

function Write-Etape([string] $Texte) { Write-Host ""; Write-Host "  $Texte" -ForegroundColor Cyan }
function Write-Ok([string] $Texte)    { Write-Host "  [ok] $Texte" -ForegroundColor Green }
function Write-Avert([string] $Texte) { Write-Host "  [!]  $Texte" -ForegroundColor Yellow }

if (-not (Test-Path $ExePath)) {
    throw "Binaire introuvable : $ExePath. Le construire avec build.py, ou passer -ExePath."
}

# ------------------------------------------------------- choix du certificat

$certificat = $null

switch ($PSCmdlet.ParameterSetName) {
    'Store' {
        Write-Etape "Certificat depuis le magasin"
        $certificat = Get-ChildItem -Path Cert:\CurrentUser\My, Cert:\LocalMachine\My -CodeSigningCert `
            -ErrorAction SilentlyContinue | Where-Object { $_.Thumbprint -eq $Thumbprint } | Select-Object -First 1
        if (-not $certificat) {
            throw "Aucun certificat de signature d'empreinte $Thumbprint dans Cert:\CurrentUser\My ni Cert:\LocalMachine\My."
        }
    }

    'SelfSigned' {
        Write-Etape "Certificat auto-signe (laboratoire)"
        Write-Avert "Suffit a debloquer un essai, pas a deployer :"
        Write-Avert "il n'atteste de rien et SmartScreen avertira l'utilisateur."
        $certificat = New-SelfSignedCertificate `
            -Subject 'CN=CBC Supervision (laboratoire), O=Commercial Bank Cameroun' `
            -Type CodeSigningCert `
            -KeyUsage DigitalSignature `
            -KeyAlgorithm RSA `
            -KeyLength 3072 `
            -CertStoreLocation Cert:\CurrentUser\My
        Write-Ok "Empreinte : $($certificat.Thumbprint)"
    }

    default {
        if (-not $PfxPath) {
            throw "Indiquer -PfxPath, -Thumbprint ou -SelfSigned. Voir Get-Help .\Sign-CbcAgent.ps1 -Detailed."
        }
        if (-not (Test-Path $PfxPath)) { throw "PFX introuvable : $PfxPath" }
        Write-Etape "Certificat depuis $PfxPath"
        if (-not $PfxPassword) {
            # Lu de facon masquee et jamais ecrit : un mot de passe de cle de
            # signature passe en clair sur la ligne de commande se retrouve
            # dans l'historique PowerShell et dans les journaux de processus.
            $PfxPassword = Read-Host -AsSecureString -Prompt "  Mot de passe du PFX"
        }
        $certificat = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new(
            (Resolve-Path $PfxPath).Path,
            $PfxPassword,
            'Exportable,PersistKeySet'
        )
    }
}

if (-not $certificat.HasPrivateKey) {
    throw "Ce certificat ne porte pas de cle privee : il peut verifier une signature, pas en produire."
}

Write-Host "  Sujet     : $($certificat.Subject)"
Write-Host "  Expire le : $($certificat.NotAfter.ToString('yyyy-MM-dd'))"
if ($certificat.NotAfter -lt (Get-Date)) {
    throw "Certificat expire le $($certificat.NotAfter.ToString('yyyy-MM-dd')). Signer avec lui produirait une signature invalide."
}

# -------------------------------------------------------------- signature

Write-Etape "Signature de $(Split-Path $ExePath -Leaf)"

$parametres = @{
    FilePath      = $ExePath
    Certificate   = $certificat
    HashAlgorithm = 'SHA256'
}

# L'horodatage prouve que la signature a ete apposee pendant la validite du
# certificat. Sans lui, tout le parc devient invalide a l'expiration.
$horodate = $true
try {
    $resultat = Set-AuthenticodeSignature @parametres -TimestampServer $TimestampServer
    if ($resultat.Status -ne 'Valid') { throw $resultat.StatusMessage }
} catch {
    Write-Avert "Horodatage impossible ($TimestampServer) : $($_.Exception.Message)"
    Write-Avert "Signature sans horodatage : elle deviendra invalide a l'expiration du certificat."
    $horodate = $false
    $resultat = Set-AuthenticodeSignature @parametres
}

# ------------------------------------------------------------ verification

Write-Etape "Verification"
$verif = Get-AuthenticodeSignature $ExePath

Write-Host "  Etat        : $($verif.Status)"
Write-Host "  Signataire  : $($verif.SignerCertificate.Subject)"
Write-Host "  Horodatage  : $(if ($horodate -and $verif.TimeStamperCertificate) { $verif.TimeStamperCertificate.Subject } else { 'aucun' })"

switch ($verif.Status) {
    'Valid' {
        Write-Ok "Binaire signe et la chaine est reconnue par ce poste."
    }
    'UnknownError' {
        # Etat attendu d'un auto-signe : la signature est bien apposee, mais
        # l'autorite n'est pas dans le magasin de confiance.
        Write-Avert "Signature apposee, mais l'autorite n'est pas reconnue par ce poste."
        Write-Avert "Attendu pour un certificat auto-signe ou une PKI interne non deployee."
    }
    default {
        throw "Signature refusee : $($verif.Status) -- $($verif.StatusMessage)"
    }
}

Write-Host ""
Write-Host "  Signature posee." -ForegroundColor Cyan
Write-Host ""
Write-Host "  Mesure faite sur un poste CBC sous Symantec Endpoint Protection"
Write-Host "  14.3 : le binaire NON signe se voit refuser toute socket"
Write-Host "  (WinError 10013), avec ou sans changement d'empreinte, tandis que"
Write-Host "  le meme binaire SIGNE passe -- y compris avec un certificat"
Write-Host "  auto-signe dont l'autorite n'est reconnue par personne. C'est"
Write-Host "  donc l'absence de signature que SEP refuse, pas l'editeur."
Write-Host ""
Write-Host "  Un certificat auto-signe debloque donc un essai, mais reste"
Write-Host "  insuffisant pour un deploiement : il n'atteste de rien, SmartScreen"
Write-Host "  avertira l'utilisateur, et une politique SEP durcie exigerait un"
Write-Host "  editeur reconnu. Pour la production, un certificat de la PKI"
Write-Host "  interne CBC ou d'une autorite publique."
Write-Host ""
Write-Host "  Empreinte du binaire, si l'equipe securite prefere une exception"
Write-Host "  explicite :"
Write-Host "    SHA256 : $((Get-FileHash $ExePath -Algorithm SHA256).Hash)"
Write-Host ""
