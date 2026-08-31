# FS3 progress — Log subsystem
**Date:** 2026-08-13  
**Plan:** PLAN-CBC-IMPL-001  

Self-hosted **Grafana Loki** in Docker (port 3100). No Grafana Cloud / signup.

| Story | Status | Artefact |
|---|---|---|
| FS3-01 File tail + offsets | **Done** | `agent/src/log_collector.py` |
| FS3-02 journald / Event Log | **Done** | `JournaldCollector` + `WinEventLogCollector`; cursor/bookmark; no historical backfill |
| FS3-03 Parsers | **Done** | raw / json / syslog |
| FS3-04 Filters | **Done** | severity floor, include/exclude regex |
| FS3-05 Multiline | **Done** | `multiline_start` regex |
| FS3-06 Rate limit 5 MB/min | **Done** | shared limiter across sources + spill file |
| FS3-07 Loki + UI search | **Done** | `POST /api/ingest/logs`, `GET /api/logs/search`, view `/logs` (filter host/severity/source) |
| FS3-08 Pattern → event | **Partial** | `alert_patterns` collected; platform alert engine later (FS4) |

## Enable on an agent

```yaml
logs:
  enabled: true
  files: ["/var/log/syslog"]   # optional
  parser: raw
  journald:
    enabled: auto              # Linux: on; Windows: off
    units: []                  # empty = system journal
  winevt:
    enabled: auto              # Windows: System + Application
    channels: ["System", "Application"]
```

First poll **seeds a cursor/bookmark** and does not dump the whole journal. Subsequent polls ship only new entries.

## Check

```bash
curl http://localhost:3100/ready
curl http://localhost:8443/health/logs
```

Rebuild after this change: `docker compose up -d --build server dashboard`
