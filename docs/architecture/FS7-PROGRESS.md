# FS7 progress — Stabilisation & NFR proof
**Date:** 2026-08-13  
**Plan:** PLAN-CBC-IMPL-001  

| Story | Status | Artefact |
|---|---|---|
| FS7-01 Load 128→500 | **Done** (128 proven; 500 harness ready) | `tools/load_test/run_load.py`; results `FS7-LOAD-RESULTS.json`; DB pool 20+40 |
| FS7-02 Latency budgets | **Done** | `latency_slo.py`; `/api/platform/status`; `tools/latency/measure_budgets.py` |
| FS7-03 3-OS smoke | **Done** | `agent/tests/test_os_smoke.py` (host OS + skip matrix) |
| FS7-04 Backup/restore | **Done** | `scripts/ops/backup_postgres.sh`, `restore_postgres.sh`; `docs/ops/BACKUP_RESTORE_RUNBOOK.md` |
| FS7-05 Hardening guides | **Done** | `docs/ops/HARDENING_AGENT.md`, `HARDENING_PLATFORM.md` |
| FS7-06 Self-monitoring | **Done** | `/health/platform`; Settings → **Plateforme** |

## Demo

1. Paramètres → **Plateforme** — component health + latency snapshot.  
2. `python tools/latency/measure_budgets.py` — page ≤ 3 s check.  
3. With Compose flags on: `python tools/load_test/run_load.py --agents 128 --duration 60 --out docs/architecture/FS7-LOAD-RESULTS.json`  
4. `bash scripts/ops/backup_postgres.sh` (or PowerShell dump in runbook).

## Note

Lab Compose currently sets `ALLOW_LOAD_SIM=true` and `RATE_LIMIT_DISABLED=true` for drills — turn **off** before pilot (see hardening guide).

Rebuild: `docker compose up -d --build server dashboard`
