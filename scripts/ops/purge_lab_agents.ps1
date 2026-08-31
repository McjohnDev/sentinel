# FS7 / ops — purge simulator & load-test agents (keep real enrolled hosts)
# Usage (from repo root, stack running):
#   powershell -File scripts/ops/purge_lab_agents.ps1
#   powershell -File scripts/ops/purge_lab_agents.ps1 -Apply
#   powershell -File scripts/ops/purge_lab_agents.ps1 -Apply -DeleteAll -KeepHostname sentinel-agent

param(
  [string]$BaseUrl = "http://localhost:8443",
  [string]$Username = "admin",
  [string]$Password = "Admin123!",
  [switch]$Apply,
  [switch]$DeleteAll,
  [string[]]$KeepHostname = @()
)

$ErrorActionPreference = "Stop"

$login = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/auth/login" -ContentType "application/x-www-form-urlencoded" -Body @{
  username = $Username
  password = $Password
}
$token = $login.access_token
if (-not $token) { throw "Login failed — no access_token" }

$headers = @{ Authorization = "Bearer $token" }
$body = @{
  dry_run = -not $Apply.IsPresent
  delete_all = $DeleteAll.IsPresent
  keep_hostnames = @($KeepHostname)
} | ConvertTo-Json

$result = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/platform/purge-lab-agents" -Headers $headers -ContentType "application/json" -Body $body

if ($result.dry_run) {
  Write-Host "DRY RUN — would delete $($result.would_delete) agent(s):"
} else {
  Write-Host "DELETED $($result.deleted) agent(s):"
}
($result.agents | Format-Table -AutoSize | Out-String).Trim() | Write-Host
