# Backup & restore runbook (STO-006 / FS7-04)

**RPO target:** ≤ 24 hours  
**Scope:** PostgreSQL (`cbc_supervision`) — primary operational state (agents, alerts, users, config).  
TSDB (VictoriaMetrics) and Loki are best-effort; re-collect from agents after restore if needed.

## Daily backup

From repo root (Git Bash / WSL / Linux):

```bash
bash scripts/ops/backup_postgres.sh
```

Windows PowerShell equivalent:

```powershell
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
New-Item -ItemType Directory -Force backups | Out-Null
docker compose -f docker/docker-compose.yml exec -T postgres `
  pg_dump -U cbc_user -d cbc_supervision |
  gzip > "backups/cbc_supervision_$stamp.sql.gz"
```

Store `backups/` on a volume outside the DB container (or copy to NAS). Retention script keeps ~8 days.

## Restore drill (quarterly + before pilot)

1. Stop writers if possible: `docker compose -f docker/docker-compose.yml stop agent server`
2. Restore:

```bash
bash scripts/ops/restore_postgres.sh backups/cbc_supervision_YYYYMMDD_HHMMSS.sql.gz
```

3. Start stack: `docker compose -f docker/docker-compose.yml up -d`
4. Verify: login UI, agent list present, `/health/platform` healthy.

## Evidence for FS7

Record date, dump size, restore wall-clock, and verification checklist in the pilot review notes. Meeting **RPO ≤ 24 h** means at least one successful backup younger than 24 h before any simulated failure.
