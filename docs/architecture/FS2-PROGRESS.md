# FS2 progress — TSDB + metric plugins
**Date:** 2026-08-13  
**Plan:** PLAN-CBC-IMPL-001  

## Wired: self-hosted metrics (no signup)

VictoriaMetrics runs in Docker. The platform writes and queries it over HTTP on the local network. No Grafana Cloud, no Influx Cloud, no API key.

| Piece | Location |
|---|---|
| TSDB container | `docker/docker-compose.yml` → `victoria-metrics` `:8428` |
| Writer + query | `server/src/tsdb_service.py` |
| Ingest persist | `POST /api/ingest/metrics` writes `metric.v1` |
| Heartbeat mirror | `POST /api/agents/heartbeat` also writes CPU/RAM/disk % |
| History API | `GET /api/agents/{id}/metrics/history` |
| Health | `GET /health/tsdb` |
| Dashboard chart | Agent detail → onglet Métriques |

## Plugins

| Plugin | Status |
|---|---|
| `cpu.collector` | Done (FS1) |
| `memory.collector` | Done (FS2) |
| `disk.collector` | Done (FS2, per mount) |
| `network.collector` | Done (FS2-03) |
| `process.collector` | Done (FS2-03, Top-5 + watched) |

## Start locally

```bash
cd docker
docker compose up -d postgres redis victoria-metrics loki
# then server (or full stack)
docker compose up -d --build server dashboard
```

Check TSDB:

```bash
curl http://localhost:8428/health
curl http://localhost:8443/health/tsdb
```

## Still open in FS2

- Native `.msi` needs WiX on the build PC (PyInstaller `cbc-agent.exe` is the Windows binary; CI builds exe on 3 OS)
- Silent `.deb` / `.rpm` / `.pkg` still built on native OS (scripts in `agent/packaging/`)
- VM OSS keeps 13 months via `--retentionPeriod=13`; query-time `step` on history API is the Lot 1 rollup. Downsampling flags are Enterprise-only.
