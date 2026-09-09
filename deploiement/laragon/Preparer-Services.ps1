<#
.SYNOPSIS
    Installe PostgreSQL et Redis en services Windows — les prerequis de Sentinel.

.DESCRIPTION
    A lancer AVANT Installer-Sentinel.ps1, en console ADMINISTRATEUR.

    PostgreSQL est deploye depuis l'archive binaire deposee a cote, et non par
    l'installateur EDB : la machine n'a pas d'acces Internet, et cette forme se
    pose dans l'arborescence de Laragon (bin\postgresql\, data\) comme les
    autres composants.

    Les deux sont enregistres en SERVICES et non lances a la main. Un service
    demarre avec la machine ; un processus lance a la main meurt a la fermeture
    de session et ne revient pas. C'est exactement ce qui est arrive a l'agent
    du poste de developpement, reste muet six heures.

    Le script est REPRENABLE : relance apres un echec, il constate ce qui est
    deja en place et poursuit. Il repare notamment une grappe creee en
    authentification « trust », sans rien detruire.

.PARAMETER MotDePasseBase
    Mot de passe a poser sur le role cbc_user. Doit etre celui qui figure deja
    dans le .env si Installer-Sentinel.ps1 a deja tourne.

.PARAMETER MotDePasseSuper
    Mot de passe du super-utilisateur postgres. Genere si absent, et affiche a
    la fin — a conserver.

.PARAMETER Port
    Port d'ecoute de PostgreSQL. 5432 par defaut.

.PARAMETER Recommencer
    Efface la grappe et repart de zero. DETRUIT LES DONNEES.

.EXAMPLE
    .\Preparer-Services.ps1 -MotDePasseBase 'postgres'
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $MotDePasseBase,
    [string] $MotDePasseSuper,
    [int]    $Port = 5432,
    [string] $NomService = 'postgresql-sentinel',
    [switch] $Recommencer
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

$Base = $PSScriptRoot
$LaragonRoot = Split-Path (Split-Path $Base -Parent) -Parent

$Archive  = Get-ChildItem $Base -Filter "postgresql-*-windows-x64-binaries.zip" | Select-Object -First 1
$PgRacine = Join-Path $LaragonRoot 'bin\postgresql'
$PgDir    = Join-Path $PgRacine 'postgresql-18.6'
$PgBin    = Join-Path $PgDir 'bin'
$PgData   = Join-Path $LaragonRoot 'data\postgresql-18.6'
$PgHba    = Join-Path $PgData 'pg_hba.conf'
$PgCtl    = Join-Path $PgBin 'pg_ctl.exe'
$Psql     = Join-Path $PgBin 'psql.exe'

$RedisDir = Get-ChildItem (Join-Path $LaragonRoot 'bin\redis') -Directory -ErrorAction SilentlyContinue |
    Select-Object -First 1

function Etape([string] $t) { Write-Host ""; Write-Host "  $t" -ForegroundColor Cyan }
function Ok([string] $t)    { Write-Host "  [ok] $t" -ForegroundColor Green }
function Avert([string] $t) { Write-Host "  [!]  $t" -ForegroundColor Yellow }

function Invoke-Natif {
    <#
      Lance un programme natif sans que sa sortie d'erreur devienne fatale.

      Avec ErrorActionPreference a 'Stop', toute ecriture sur stderr par un
      programme natif devient une exception terminale — meme quand le
      programme rend 0. `initdb` ecrit un avertissement : le script mourait
      dessus apres avoir pourtant cree la grappe.

      La canalisation est conservee a dessein. Mesure sur un programme qui
      laisse un enfant vivant, comme `pg_ctl start` : la canalisation rend la
      main en 0,4 s, la ou `Start-Process -Wait` attend 21 s la descendance
      entiere. L'intuition inverse est fausse.

      Seul le code de retour decide de l'echec.
    #>
    param(
        [Parameter(Mandatory)][string] $Fichier,
        [string[]] $Arguments = @(),
        [string] $Entree,
        [switch] $Muet
    )

    $precedent = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        if ($PSBoundParameters.ContainsKey('Entree')) {
            $lignes = $Entree | & $Fichier @Arguments 2>&1
        } else {
            $lignes = & $Fichier @Arguments 2>&1
        }
        if (-not $Muet) {
            $lignes | Where-Object { $_ -and "$_".Trim() } |
                ForEach-Object { Write-Host "      $_" }
        }
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $precedent
    }
}

function Sortie-Natif {
    <# Rend la sortie d'un programme, pour les commandes qu'on interroge. #>
    param([Parameter(Mandatory)][string] $Fichier, [string[]] $Arguments = @())
    $precedent = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $texte = (& $Fichier @Arguments 2>&1 | Out-String)
        return [pscustomobject]@{ Code = $LASTEXITCODE; Sortie = $texte }
    } finally {
        $ErrorActionPreference = $precedent
    }
}

function Teste-Port([int] $port) {
    $c = New-Object Net.Sockets.TcpClient
    try { $c.Connect('127.0.0.1', $port); return $true }
    catch { return $false }
    finally { $c.Close() }
}

function Attends-Port([int] $port, [int] $secondes = 30) {
    for ($i = 0; $i -lt $secondes; $i++) {
        if (Teste-Port $port) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Nouveau-MotDePasse {
    $o = New-Object byte[] 24
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($o)
    return (([Convert]::ToBase64String($o) -replace '[^A-Za-z0-9]', '') + 'aA1').Substring(0, 20)
}

function Assert-Administrateur {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $pr = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Enregistrer un service exige une console PowerShell ouverte en administrateur."
    }
}

Write-Host ""
Write-Host "  Prerequis de Sentinel — PostgreSQL et Redis" -ForegroundColor Green
Write-Host "  Laragon : $LaragonRoot"
Assert-Administrateur

# ================================================== PostgreSQL — binaires

Etape "PostgreSQL — binaires"

if ($Recommencer -and (Test-Path $PgData)) {
    if (Get-Service $NomService -ErrorAction SilentlyContinue) {
        Stop-Service $NomService -Force -ErrorAction SilentlyContinue
        Invoke-Natif -Fichier $PgCtl -Arguments @('unregister', '-N', $NomService) -Muet | Out-Null
    }
    Avert "Suppression de la grappe existante (-Recommencer)."
    Remove-Item $PgData -Recurse -Force
}

if (-not (Test-Path (Join-Path $PgBin 'initdb.exe'))) {
    if (-not $Archive) {
        throw @"
Archive PostgreSQL introuvable dans $Base.

Attendu un fichier postgresql-*-windows-x64-binaries.zip depose a cote de ce
script. La machine n'ayant pas d'acces Internet, il doit venir du poste de
developpement.
"@
    }
    Write-Host "  Extraction de $($Archive.Name) ($([math]::Round($Archive.Length/1MB)) Mo)..."
    New-Item -ItemType Directory -Path $PgRacine -Force | Out-Null

    $tmp = Join-Path $env:TEMP ("pg-" + [Guid]::NewGuid().ToString('N'))
    Expand-Archive -Path $Archive.FullName -DestinationPath $tmp -Force
    $racine = Join-Path $tmp 'pgsql'
    if (-not (Test-Path $racine)) {
        $racine = (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName
    }
    Move-Item $racine $PgDir -Force
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Ok "Binaires deployes : $PgDir"
} else {
    Ok "Binaires deja presents."
}

# ==================================================== PostgreSQL — grappe

Etape "PostgreSQL — grappe"

$grappeNeuve = $false
if (-not (Test-Path (Join-Path $PgData 'PG_VERSION'))) {
    if (-not $MotDePasseSuper) { $MotDePasseSuper = Nouveau-MotDePasse }

    New-Item -ItemType Directory -Path $PgData -Force | Out-Null
    $fichierMdp = Join-Path $env:TEMP 'pg-init.txt'
    try {
        [IO.File]::WriteAllText($fichierMdp, $MotDePasseSuper, [Text.UTF8Encoding]::new($false))

        # --auth-* n'est pas facultatif. Sans lui, initdb cree la grappe en
        # « trust » : tout compte de la machine s'y connecte en
        # super-utilisateur sans mot de passe, et celui qu'on vient de poser
        # ne sert a rien. initdb le signale — dans l'avertissement meme qui,
        # ecrit sur stderr, tuait la version precedente de ce script.
        $code = Invoke-Natif -Fichier (Join-Path $PgBin 'initdb.exe') -Arguments @(
            "--pgdata=$PgData", "--username=postgres", "--pwfile=$fichierMdp",
            "--auth-local=scram-sha-256", "--auth-host=scram-sha-256",
            "--encoding=UTF8", "--locale=C")
        if ($code -ne 0) { throw "initdb a echoue (code $code)." }
    } finally {
        Remove-Item $fichierMdp -Force -ErrorAction SilentlyContinue
    }
    $grappeNeuve = $true
    Ok "Grappe creee en authentification scram-sha-256."

    # Ecoute locale uniquement : seul le serveur FastAPI, sur cette machine,
    # accede a la base.
    Add-Content (Join-Path $PgData 'postgresql.conf') `
        "`r`n# Sentinel : ecoute locale uniquement.`r`nlisten_addresses = '127.0.0.1'`r`nport = $Port`r`n"
    Ok "Ecoute restreinte a 127.0.0.1:$Port."
} else {
    Ok "Grappe deja initialisee."
}

# =================================================== PostgreSQL — service

Etape "PostgreSQL — service Windows"

if (Teste-Port $Port) {
    Ok "Deja en ecoute sur $Port."
} else {
    $service = Get-Service $NomService -ErrorAction SilentlyContinue
    if (-not $service) {
        # Enregistre plutot que lance a la main : un service demarre avec la
        # machine. Un `pg_ctl start` meurt avec la session, et Sentinel avec
        # lui au prochain redemarrage.
        $code = Invoke-Natif -Fichier $PgCtl -Arguments @(
            'register', '-N', $NomService, '-D', $PgData, '-S', 'auto')
        if ($code -ne 0) { throw "Enregistrement du service echoue (code $code)." }
        Ok "Service $NomService enregistre, demarrage automatique."
        Start-Sleep -Seconds 2
    } else {
        Ok "Service $NomService deja enregistre."
    }

    # Start-Service est une applet PowerShell : elle attend le service, jamais
    # un descripteur herite par un processus fils.
    Write-Host "      demarrage du service..."
    Start-Service $NomService -ErrorAction Stop
    if (-not (Attends-Port $Port 30)) {
        throw @"
Le service a demarre mais rien n'ecoute sur $Port.

Le journal de la grappe dit pourquoi : $PgData\log\
"@
    }
    Ok "PostgreSQL en ecoute sur 127.0.0.1:$Port."
}

# =========================================== reparation « trust » eventuelle

$hbaEnTrust = $false
if (Test-Path $PgHba) {
    $lignesTrust = @(Get-Content $PgHba | Where-Object { $_ -notmatch '^\s*#' -and $_ -match '\btrust\s*$' })
    $hbaEnTrust = $lignesTrust.Count -gt 0
}

$reparationHba = $false
if ($hbaEnTrust) {
    Etape "Reparation : la grappe est en authentification « trust »"
    Avert @"
Tout compte de cette machine peut s'y connecter en super-utilisateur sans mot
de passe. C'est l'etat qu'une version precedente de ce script laissait, faute
de passer --auth-* a initdb.
"@

    # « trust » est encore actif : on en profite pour poser un mot de passe
    # connu sur postgres AVANT de fermer la porte. Sinon la grappe deviendrait
    # inaccessible — le mot de passe pose par --pwfile n'ayant jamais ete
    # affiche, le script precedent etant mort avant.
    if (-not $MotDePasseSuper) { $MotDePasseSuper = Nouveau-MotDePasse }
    $s = $MotDePasseSuper.Replace("'", "''")

    $code = Invoke-Natif -Fichier $Psql -Arguments @(
        '-U', 'postgres', '-h', '127.0.0.1', '-p', "$Port", '-d', 'postgres',
        '-v', 'ON_ERROR_STOP=1', '-c', "ALTER ROLE postgres WITH PASSWORD '$s'")
    if ($code -ne 0) { throw "Impossible de poser le mot de passe du super-utilisateur (code $code)." }
    Ok "Mot de passe du super-utilisateur repose."
    $reparationHba = $true
} elseif (-not $grappeNeuve -and -not $MotDePasseSuper) {
    throw @"
La grappe existe deja et son mot de passe super-utilisateur n'est pas connu
de ce script.

Le repasser explicitement :
    .\Preparer-Services.ps1 -MotDePasseBase '...' -MotDePasseSuper '...'

Ou repartir de zero — ceci DETRUIT la base :
    .\Preparer-Services.ps1 -MotDePasseBase '...' -Recommencer
"@
}

# ==================================================== role et base

Etape "Role et base de Sentinel"

$env:PGPASSWORD = $MotDePasseSuper
$mdp = $MotDePasseBase.Replace("'", "''")
$commun = @('-U', 'postgres', '-h', '127.0.0.1', '-p', "$Port", '-v', 'ON_ERROR_STOP=1')

$sqlRole = @"
DO `$`$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'cbc_user') THEN
      CREATE ROLE cbc_user LOGIN PASSWORD '$mdp';
   ELSE
      ALTER ROLE cbc_user WITH LOGIN PASSWORD '$mdp';
   END IF;
END
`$`$;
"@

Write-Host "      creation du role..."
$code = Invoke-Natif -Fichier $Psql -Entree $sqlRole -Arguments ($commun + @('-d', 'postgres', '-f', '-'))
if ($code -ne 0) { throw "Creation du role cbc_user echouee (code $code)." }
Ok "Role cbc_user pose."

$r = Sortie-Natif -Fichier $Psql -Arguments ($commun + @(
    '-d', 'postgres', '-tAc', "SELECT 1 FROM pg_database WHERE datname='cbc_supervision'"))
if ($r.Sortie.Trim() -ne '1') {
    $code = Invoke-Natif -Fichier $Psql -Arguments ($commun + @(
        '-d', 'postgres', '-c', 'CREATE DATABASE cbc_supervision OWNER cbc_user'))
    if ($code -ne 0) { throw "Creation de la base echouee (code $code)." }
    Ok "Base cbc_supervision creee."
} else {
    Ok "Base cbc_supervision deja presente."
}

# Depuis PostgreSQL 15, le schema public n'est plus inscriptible par un role
# qui n'en est pas proprietaire. Sans ce GRANT, le serveur demarre puis echoue
# a creer ses tables, sur une erreur qui ne nomme meme pas le schema.
$code = Invoke-Natif -Fichier $Psql -Arguments ($commun + @(
    '-d', 'cbc_supervision', '-c', 'GRANT ALL ON SCHEMA public TO cbc_user'))
if ($code -ne 0) { throw "GRANT sur le schema public echoue (code $code)." }
Ok "Droits poses sur le schema public."

# ============================================ fermeture de « trust »

if ($reparationHba) {
    Etape "Fermeture de l'authentification « trust »"

    # Seule la derniere colonne (METHOD) des lignes non commentees change.
    $lignes = Get-Content $PgHba | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -notmatch '\btrust\s*$') { $_ }
        else { $_ -replace '\btrust\s*$', 'scram-sha-256' }
    }
    Set-Content $PgHba $lignes -Encoding UTF8

    $code = Invoke-Natif -Fichier $PgCtl -Arguments @('-D', $PgData, 'reload') -Muet
    if ($code -ne 0) { throw "Rechargement de la configuration echoue (code $code)." }
    Start-Sleep -Seconds 2

    # Verification reelle : une connexion avec un mauvais mot de passe doit
    # desormais echouer. L'affirmer sans l'eprouver ne vaudrait rien.
    $env:PGPASSWORD = 'mot-de-passe-volontairement-faux'
    $essai = Sortie-Natif -Fichier $Psql -Arguments @(
        '-U', 'postgres', '-h', '127.0.0.1', '-p', "$Port", '-d', 'postgres', '-tAc', 'SELECT 1')
    $env:PGPASSWORD = $MotDePasseSuper

    if ($essai.Code -ne 0) {
        Ok "Verifie : une connexion sans le bon mot de passe est refusee."
    } else {
        Avert "La grappe accepte encore une connexion sans mot de passe. Verifier $PgHba."
    }
}
$env:PGPASSWORD = $null

# =================================================================== Redis

Etape "Redis — service Windows"

if (Teste-Port 6379) {
    Ok "Deja en ecoute sur 6379."
} elseif (-not $RedisDir) {
    Avert "Redis introuvable sous $LaragonRoot\bin\redis — la plateforme demarrera sans cache."
} else {
    $redisExe  = Join-Path $RedisDir.FullName 'redis-server.exe'
    $redisConf = Join-Path $RedisDir.FullName 'redis.windows-service.conf'
    if (-not (Test-Path $redisConf)) {
        $redisConf = Join-Path $RedisDir.FullName 'redis.windows.conf'
    }

    $svcRedis = Get-Service 'Redis' -ErrorAction SilentlyContinue
    if (-not $svcRedis) {
        $code = Invoke-Natif -Fichier $redisExe -Arguments @('--service-install', $redisConf)
        if ($code -ne 0) {
            Avert "Enregistrement du service Redis echoue (code $code). La plateforme fonctionnera sans cache."
        } else {
            Ok "Service Redis enregistre."
        }
    } else {
        Ok "Service Redis deja enregistre."
    }

    if (Get-Service 'Redis' -ErrorAction SilentlyContinue) {
        Start-Service 'Redis' -ErrorAction SilentlyContinue
        if (Attends-Port 6379 15) {
            Ok "Redis en ecoute sur 127.0.0.1:6379 ($($RedisDir.Name))."
        } else {
            Avert "Redis n'ecoute pas. La plateforme fonctionnera sans cache."
        }
    }
}

# ================================================================== Bilan

Write-Host ""
Write-Host "  Prerequis en place." -ForegroundColor Green
Write-Host ""
Write-Host ("    PostgreSQL  127.0.0.1:{0}  {1}" -f $Port, $(if (Teste-Port $Port) { 'repond' } else { 'MUET' }))
Write-Host ("    Redis       127.0.0.1:6379  {0}" -f $(if (Teste-Port 6379) { 'repond' } else { 'muet' }))
Write-Host ""
Write-Host "  Les deux sont des services : ils repartiront au redemarrage."

if ($MotDePasseSuper) {
    Write-Host ""
    Write-Host "  ------------------------------------------------------------" -ForegroundColor Yellow
    Write-Host "  Mot de passe du super-utilisateur postgres :" -ForegroundColor Yellow
    Write-Host "      $MotDePasseSuper" -ForegroundColor Yellow
    Write-Host "  A noter maintenant. Il ne sera plus reaffiche." -ForegroundColor Yellow
    Write-Host "  ------------------------------------------------------------" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  Suite :"
Write-Host "    .\Installer-Sentinel.ps1 -MotDePasseBase '<le meme mot de passe>'"
Write-Host ""
