# Platform hardening guide (SEC-008 / FS7-05)

## Compose / host

- Change `SECRET_KEY`, Postgres password, and any demo credentials before production.
- Bind admin ports (Postgres `5433`, Redis, VM, Loki) to management VLAN / localhost only when possible.
- Keep `MESSAGING_ENABLED` off until Mail API credentials are vaulted.
- Never set `ALLOW_LOAD_SIM=true` or `RATE_LIMIT_DISABLED=true` outside controlled load drills.

## Application

- Enforce HTTPS (terminate TLS on reverse proxy or API certs).
- RBAC: Admin / Operator / ReadOnly — use ReadOnly for auditors.
- Rate limits on by default (`slowapi`).
- Audit log for enrolment tokens and privileged actions.
- Retention config for heartbeats/alerts — tune to CBC storage policy.

## Data stores

- Postgres backups per [BACKUP_RESTORE_RUNBOOK.md](./BACKUP_RESTORE_RUNBOOK.md).
- Victoria VictoriaMetrics retention (Compose `--retentionPeriod=13` months) and Loki volume growth.
- No cloud SaaS metrics/logs for Lot 1 (self-hosted VM + Loki only).

## Self-monitoring

- Probe `GET /health/platform` from an external checker (or scrape `/metrics`).
- Dashboard: **Paramètres → Plateforme** shows component health + latency SLOs.
