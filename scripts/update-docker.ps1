<#
.SYNOPSIS
    Rebuilds the local Sentinel Docker stack from the current working tree.

.DESCRIPTION
    Pushes local source into the running lab containers: rebuilds the API
    and dashboard images, then recreates those services. Postgres, Redis,
    VictoriaMetrics and Loki keep their volumes.

    Use this after changing server/ or src/ so http://localhost:3000 and
    http://127.0.0.1:8443 serve the code on disk rather than an old image.

.PARAMETER Pull
    Also docker compose pull for published images (postgres, redis, …).

.PARAMETER NoCache
    Rebuild server and dashboard without the Docker layer cache.

.EXAMPLE
    .\scripts\update-docker.ps1

.EXAMPLE
    .\scripts\update-docker.ps1 -NoCache
#>
[CmdletBinding()]
param(
    [switch] $Pull,
    [switch] $NoCache
)

$ErrorActionPreference = "Stop"

$Repo = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $Repo "docker\docker-compose.yml"
$DockerBin = "C:\Program Files\Docker\Docker\resources\bin"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    if (Test-Path "$DockerBin\docker.exe") {
        $env:Path = "$DockerBin;" + $env:Path
    } else {
        Write-Error "Docker introuvable. Demarrer Docker Desktop, puis relancer."
        exit 1
    }
}

if (-not (Test-Path $ComposeFile)) {
    Write-Error "Compose introuvable : $ComposeFile"
    exit 1
}

$ready = $false
for ($i = 1; $i -le 18; $i++) {
    docker info 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    if ($i -eq 1) { Write-Host "Attente du moteur Docker..." -ForegroundColor Cyan }
    Start-Sleep -Seconds 5
}
if (-not $ready) {
    Write-Error "Le moteur Docker ne repond pas. Ouvrir Docker Desktop et reessayer."
    exit 1
}

Set-Location $Repo

$compose = @("compose", "-f", $ComposeFile)

if ($Pull) {
    Write-Host "Pull des images publiees..." -ForegroundColor Cyan
    docker @compose pull
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$buildArgs = @("build")
if ($NoCache) { $buildArgs += "--no-cache" }
$buildArgs += @("server", "dashboard")

Write-Host "Reconstruction de server et dashboard depuis le depot..." -ForegroundColor Cyan
docker @compose @buildArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Recreation des conteneurs (volumes conserves)..." -ForegroundColor Cyan
docker @compose up -d --force-recreate --no-deps server dashboard
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker @compose up -d postgres redis victoria-metrics loki
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
docker @compose ps
Write-Host ""
Write-Host "Dashboard : http://localhost:3000" -ForegroundColor Green
Write-Host "API       : http://127.0.0.1:8443/docs"
Write-Host "Hard-refresh le dashboard (Ctrl+F5) apres une reconstruction."
