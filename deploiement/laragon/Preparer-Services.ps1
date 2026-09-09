<#
.SYNOPSIS
    Installe PostgreSQL et demarre Redis — les deux prerequis de Sentinel.

.DESCRIPTION
    A lancer AVANT Installer-Sentinel.ps1, ou apres l'avoir vu s'arreter sur
    « PostgreSQL NE repond PAS ».

    PostgreSQL est deploye depuis l'archive binaire deposee a cote, et non
    par l'installateur EDB : la machine n'a pas d'acces Internet, et cette
    forme se pose dans l'arborescence de Laragon (bin\postgresql\,
    data\postgresql-18.6\) comme les autres composants, au lieu d'un service
    separe vivant a part.

    Redis est deja fourni par Laragon et correctement configure — lie a
    127.0.0.1, protected-mode actif. Il est simplement desactive
    (Use=-1 dans laragon.ini). Ce script le demarre.

    Le script est REPRENABLE : relance apres un echec, il constate ce qui est
    deja en place et poursuit. Il repare notamment une grappe creee en
    authentification « trust », sans rien detruire.

.PARAMETER MotDePasseBase
    Mot de passe a poser sur le role cbc_user. Doit etre celui qui figure
    deja dans le .env si Installer-Sentinel.ps1 a deja tourne.

.PARAMETER MotDePasseSuper
    Mot de passe du super-utilisateur postgres. Genere si absent, et affiche
    a la fin — a conserver.

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
    [switch] $Recommencer
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

$Base = $PSScriptRoot
$LaragonRoot = Split-Path (Split-Path $Base -Parent) -Parent

$Archive = Get-ChildItem $Base -Filter "postgresql-*-windows-x64-binaries.zip" | Select-Object -First 1
$PgRacine = Join-Path $LaragonRoot 'bin\postgresql'
$PgDir    = Join-Path $PgRacine 'postgresql-18.6'
$PgBin    = Join-Path $PgDir 'bin'
$PgData   = Join-Path $LaragonRoot 'data\postgresql-18.6'
$PgLog    = Join-Path $PgData 'postgresql.log'
$PgHba    = Join-Path $PgData 'pg_hba.conf'

$RedisDir = Get-ChildItem (Join-Path $LaragonRoot 'bin\redis') -Directory -ErrorAction SilentlyContinue |
    Select-Object -First 1

function Etape([string] $t) { Write-Host ""; Write-Host "  $t" -ForegroundColor Cyan }
function Ok([string] $t)    { Write-Host "  [ok] $t" -ForegroundColor Green }
function Avert([string] $t) { Write-Host "  [!]  $t" -ForegroundColor Yellow }

function Invoke-Natif {
    <#
      Lance un programme natif sans laisser sa sortie d'erreur devenir fatale.

      Avec $ErrorActionPreference = 'Stop', PowerShell transforme toute
      ecriture sur stderr par un programme natif en exception terminale —
      meme quand le programme rend 0 et a parfaitement reussi. `initdb` ecrit
      un avertissement sur stderr : le script mourait dessus, apres avoir
      pourtant cree la grappe.

      Seul le code de retour decide de l'echec. C'est le seul signal qu'un
      programme donne reellement sur son succes.
    #>
    param(
        [Parameter(Mandatory)][string] $Fichier,
        [string[]] $Arguments = @(),
        [string] $Entree
    )

    $precedent = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        if ($PSBoundParameters.ContainsKey('Entree')) {
            $Entree | & $Fichier @Arguments 2>&1 | ForEach-Object { Write-Host "      $_" }
        } else {
            & $Fichier @Arguments 2>&1 | ForEach-Object { Write-Host "      $_" }
        }
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $precedent
    }
}

function Teste-Port([string] $hote, [int] $port) {
    $c = New-Object Net.Sockets.TcpClient
    try { $c.Connect($hote, $port); return $true }
    catch { return $false }
    finally { $c.Close() }
}

function Nouveau-MotDePasse {
    $o = New-Object byte[] 24
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($o)
    return (([Convert]::ToBase64String($o) -replace '[^A-Za-z0-9]', '') + 'aA1').Substring(0, 20)
}

Write-Host ""
Write-Host "  Prerequis de Sentinel — PostgreSQL et Redis" -ForegroundColor Green
Write-Host "  Laragon : $LaragonRoot"

# ============================================================== PostgreSQL

Etape "PostgreSQL — binaires"

if ($Recommencer -and (Test-Path $PgData)) {
    if (Test-Path (Join-Path $PgBin 'pg_ctl.exe')) {
        Invoke-Natif -Fichier (Join-Path $PgBin 'pg_ctl.exe') -Arguments @('-D', $PgData, 'stop', '-m', 'fast') | Out-Null
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
    $racineArchive = Join-Path $tmp 'pgsql'
    if (-not (Test-Path $racineArchive)) {
        $racineArchive = (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName
    }
    Move-Item $racineArchive $PgDir -Force
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Ok "Binaires deployes : $PgDir"
} else {
    Ok "Binaires deja presents."
}

# --------------------------------------------------------- la grappe

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
        # ne sert a rien.
        $code = Invoke-Natif -Fichier (Join-Path $PgBin 'initdb.exe') -Arguments @(
            "--pgdata=$PgData",
            "--username=postgres",
            "--pwfile=$fichierMdp",
            "--auth-local=scram-sha-256",
            "--auth-host=scram-sha-256",
            "--encoding=UTF8",
            "--locale=C"
        )
        if ($code -ne 0) { throw "initdb a echoue (code $code)." }
    } finally {
        Remove-Item $fichierMdp -Force -ErrorAction SilentlyContinue
    }
    $grappeNeuve = $true
    Ok "Grappe creee en authentification scram-sha-256."

    # Ecoute locale uniquement : seul le serveur FastAPI, sur cette machine,
    # accede a la base.
    Add-Content (Join-Path $PgData 'postgresql.conf') `
        "`r`n# Sentinel : ecoute locale uniquement.`r`nlisten_addresses = '127.0.0.1'`r`nport = 5432`r`n"
    Ok "Ecoute restreinte a 127.0.0.1."
} else {
    Ok "Grappe deja initialisee."
}

# --------------------------------------------------------- demarrage

Etape "PostgreSQL — demarrage"

if (Teste-Port '127.0.0.1' 5432) {
    Ok "Deja en ecoute sur 5432."
} else {
    $code = Invoke-Natif -Fichier (Join-Path $PgBin 'pg_ctl.exe') `
        -Arguments @('-D', $PgData, '-l', $PgLog, '-w', 'start')
    if (-not (Teste-Port '127.0.0.1' 5432)) {
        throw "PostgreSQL n'ecoute pas apres demarrage (code $code). Le journal dit pourquoi : $PgLog"
    }
    Ok "Demarre sur 127.0.0.1:5432."
}

# ------------------------------------------- reparation « trust » eventuelle

$psql = Join-Path $PgBin 'psql.exe'
$hbaEnTrust = $false
if (Test-Path $PgHba) {
    $hbaEnTrust = (Get-Content $PgHba | Where-Object { $_ -notmatch '^\s*#' -and $_ -match '\btrust\b' }).Count -gt 0
}

if ($hbaEnTrust) {
    Etape "Reparation : la grappe est en authentification « trust »"
    Avert @"
Tout compte de cette machine peut se connecter en super-utilisateur sans mot
de passe. C'est l'etat qu'une version precedente de ce script laissait, faute
de passer --auth-* a initdb.
"@

    # Trust est encore actif : on en profite pour poser un mot de passe connu
    # sur postgres AVANT de fermer la porte. Sinon la grappe deviendrait
    # inaccessible, le mot de passe pose par --pwfile n'ayant jamais ete
    # affiche.
    if (-not $MotDePasseSuper) { $MotDePasseSuper = Nouveau-MotDePasse }
    $s = $MotDePasseSuper.Replace("'", "''")

    $code = Invoke-Natif -Fichier $psql -Arguments @(
        '-U', 'postgres', '-h', '127.0.0.1', '-d', 'postgres',
        '-v', 'ON_ERROR_STOP=1',
        '-c', "ALTER ROLE postgres WITH PASSWORD '$s'"
    )
    if ($code -ne 0) { throw "Impossible de poser le mot de passe du super-utilisateur (code $code)." }
    Ok "Mot de passe du super-utilisateur repose."
    $reparationHba = $true
} else {
    $reparationHba = $false
    if (-not $grappeNeuve -and -not $MotDePasseSuper) {
        $MotDePasseSuper = Read-Host "  Mot de passe du super-utilisateur postgres"
    }
}

# ------------------------------------------------------- role et base

Etape "Role et base de Sentinel"

$env:PGPASSWORD = $MotDePasseSuper
$mdp = $MotDePasseBase.Replace("'", "''")

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

$code = Invoke-Natif -Fichier $psql -Entree $sqlRole -Arguments @(
    '-U', 'postgres', '-h', '127.0.0.1', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1', '-f', '-')
if ($code -ne 0) { throw "Creation du role cbc_user echouee (code $code)." }
Ok "Role cbc_user pose."

$existe = ''
$precedent = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $existe = (& $psql -U postgres -h 127.0.0.1 -d postgres -tAc `
        "SELECT 1 FROM pg_database WHERE datname='cbc_supervision'" 2>$null) -join ''
} finally { $ErrorActionPreference = $precedent }

if ($existe.Trim() -ne '1') {
    $code = Invoke-Natif -Fichier $psql -Arguments @(
        '-U', 'postgres', '-h', '127.0.0.1', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1',
        '-c', 'CREATE DATABASE cbc_supervision OWNER cbc_user')
    if ($code -ne 0) { throw "Creation de la base echouee (code $code)." }
    Ok "Base cbc_supervision creee."
} else {
    Ok "Base cbc_supervision deja presente."
}

# Depuis PostgreSQL 15, le schema public n'est plus inscriptible par un role
# qui n'en est pas proprietaire. Sans ce GRANT, le serveur demarre puis echoue
# a creer ses tables, sur une erreur qui ne nomme meme pas le schema.
$code = Invoke-Natif -Fichier $psql -Arguments @(
    '-U', 'postgres', '-h', '127.0.0.1', '-d', 'cbc_supervision', '-v', 'ON_ERROR_STOP=1',
    '-c', 'GRANT ALL ON SCHEMA public TO cbc_user')
if ($code -ne 0) { throw "GRANT sur le schema public echoue (code $code)." }
Ok "Droits poses sur le schema public."

# ------------------------------------------- fermeture de « trust »

if ($reparationHba) {
    Etape "Fermeture de l'authentification « trust »"

    # Seule la derniere colonne (METHOD) des lignes non commentees change.
    $lignes = Get-Content $PgHba | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -notmatch '\btrust\s*$') { $_ }
        else { $_ -replace '\btrust\s*$', 'scram-sha-256' }
    }
    Set-Content $PgHba $lignes -Encoding UTF8

    $code = Invoke-Natif -Fichier (Join-Path $PgBin 'pg_ctl.exe') -Arguments @('-D', $PgData, 'reload')
    if ($code -ne 0) { throw "Rechargement de la configuration echoue (code $code)." }
    Start-Sleep -Seconds 2

    # Verification reelle : une connexion sans mot de passe doit desormais
    # echouer. L'affirmer sans l'eprouver ne vaudrait rien.
    $env:PGPASSWORD = 'mot-de-passe-volontairement-faux'
    $precedent = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $psql -U postgres -h 127.0.0.1 -d postgres -tAc 'SELECT 1' 2>&1 | Out-Null
        $refuse = ($LASTEXITCODE -ne 0)
    } finally { $ErrorActionPreference = $precedent }
    $env:PGPASSWORD = $MotDePasseSuper

    if ($refuse) {
        Ok "Verifie : une connexion sans le bon mot de passe est refusee."
    } else {
        Avert "La grappe accepte encore une connexion sans mot de passe. Verifier $PgHba."
    }
}
$env:PGPASSWORD = $null

# =================================================================== Redis

Etape "Redis"

if (Teste-Port '127.0.0.1' 6379) {
    Ok "Deja en ecoute sur 6379."
} elseif (-not $RedisDir) {
    Avert "Redis introuvable sous $LaragonRoot\bin\redis — la plateforme demarrera sans cache."
} else {
    $redisExe  = Join-Path $RedisDir.FullName 'redis-server.exe'
    $redisConf = Join-Path $RedisDir.FullName 'redis.windows.conf'

    Start-Process -FilePath $redisExe -ArgumentList "`"$redisConf`"" -WindowStyle Hidden
    Start-Sleep -Seconds 3

    if (Teste-Port '127.0.0.1' 6379) {
        Ok "Redis demarre sur 127.0.0.1:6379 ($($RedisDir.Name))."
        Avert @"
Demarre comme simple processus : il ne repartira pas au redemarrage de la
machine. Pour le rendre permanent, depuis $($RedisDir.FullName) en console
administrateur :
    redis-server.exe --service-install redis.windows-service.conf
    redis-server.exe --service-start
"@
    } else {
        Avert "Redis n'a pas demarre. La plateforme fonctionnera sans cache."
    }
}

# ================================================================== Bilan

Write-Host ""
Write-Host "  Prerequis en place." -ForegroundColor Green
Write-Host ""
Write-Host ("    PostgreSQL  127.0.0.1:5432  {0}" -f $(if (Teste-Port '127.0.0.1' 5432) { 'repond' } else { 'MUET' }))
Write-Host ("    Redis       127.0.0.1:6379  {0}" -f $(if (Teste-Port '127.0.0.1' 6379) { 'repond' } else { 'muet' }))

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
