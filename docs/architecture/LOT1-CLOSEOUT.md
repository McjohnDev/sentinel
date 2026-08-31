# Lot 1 close-out (engineering)

**Date:** 2026-08-14  
**Goal:** Close remaining **code** gaps in FS0–FS8. CBC-owned items stay open.

## Closed in this pass

| Gap | What changed |
|---|---|
| FS0-08 CI 3-OS | `.github/workflows/ci.yml` — Linux full tests + Win/macOS/Linux agent smoke + PyInstaller artifact |
| FS1-06 DLQ inspect | `GET /api/ingest/dlq` (admin); `DeadLetterQueue.tail/size`; platform health `metrics_dlq` |
| FS2-04 rollups | VictoriaMetrics `--retentionPeriod=13` months + history API `step` (OSS). Enterprise downsampling not used. |
| FS2-06 packaging | `agent/packaging/agent.spec` includes plugins + `shared`; Windows lab config + `scripts/run_windows_agent.ps1`. Frozen exe on this PC is blocked by Windows Defender file lock (CI still builds). |
| Lab vs prod flags | `docker/docker-compose.prod.yml` turns off `ALLOW_LOAD_SIM` / rate-limit bypass |
| Lab multi-agent enroll | `demo-token-123` stays reusable; generated tokens remain one-time |
| CBC lists (demo) | `docs/ops/CBC_WATCH_LISTS.md` + `agent/config.lab.yaml` placeholders |
| Demo playbook | `docs/ops/LOT1_DEMO_SCENARIOS.md` |

## Still CBC / ops (not closable in repo)

| Open point | Why |
|---|---|
| 1c PowerShell inventory | DES-004 legacy paths TBD — extinction cannot hit zero Musts without CBC workshop |
| CBC-A / CBC-B | Official SWIFT/service/file lists |
| CBC-C | Official workstation offline threshold (lab = 7200 s) |
| INT-001 live | Mail API URL + key for real emails |
| M4 sign-off | `cbc_ops` / `tech_lead` / `sponsor` on acceptance pack |
| Silent MSI on this PC | WiX Toolset not assumed; PyInstaller exe is the Windows Lot 1 binary. `.deb`/`.rpm`/`.pkg` build on their native OS (CI matrix) |

## Prod reminder

Lab compose still sets `ALLOW_LOAD_SIM=true` and `RATE_LIMIT_DISABLED=true`. For a pilot-like run:

```powershell
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
```
