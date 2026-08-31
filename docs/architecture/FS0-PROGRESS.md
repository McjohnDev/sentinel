# FS0 + FS1 progress — Lot 1 foundations
**Date:** 2026-08-13  
**Plan:** PLAN-CBC-IMPL-001  

## FS0

| Story | Status | Artefact |
|---|---|---|
| FS0-01 Freeze contracts | **Done** | `shared/protocols/`, `shared/schemas/`, `shared/fixtures/`, tests |
| FS0-07 ADR TSDB/log store | **Done** | ADR-001 → VictoriaMetrics + Loki |
| FS0-06 Compose + TSDB | **Done** | `docker/docker-compose.yml` |
| FS0-05 Coverage map v0 | **Done** (template) | DES-004 — CBC inventory still TBD |
| FS0-02 / FS0-03 DES stubs | **Done** (outline) | DES-001 / DES-002 |
| FS0-09 Simulator | **Done** | `tools/agent_simulator/` |
| FS0-04 | **Done** (v1.0 draft) | DES-003 interface dossier — IA, Studio Agent, n8n playbooks |
| FS0-08 | **Done** | `.github/workflows/ci.yml` — Linux tests + Win/macOS/Linux agent smoke + PyInstaller |

## FS1

| Story | Status | Artefact |
|---|---|---|
| FS1-01 Plugin framework | **Done** (skeleton) | `agent/src/plugins/` |
| FS1-02 Instance lock | **Done** | `agent/src/instance_lock.py` wired in `__main__` |
| FS1-07 CPU golden plugin | **Done** (v1) | `plugins/collectors/cpu.py` — total + per-core |
| FS1-06 Schema validate + DLQ | **Done** | ingest + file DLQ + `GET /api/ingest/dlq` + platform health `metrics_dlq` |
| FS1-03 TLS verify | **Done** | default `tls_verify: true`; lab override in `agent/config.yaml` |
| FS1-04 Durable 24h/500MB buffer | **Done** | `agent/src/durable_buffer.py` JSONL queue, prune by age/size |
| FS1-08 task.v1 reject | **Done** | L0 reject + `POST /api/agents/tasks/results`; heartbeat ACK `tasks: []` |

## Verify

```bash
pip install -r shared/requirements.txt -r agent/requirements.txt
python -m shared.protocols.export_schemas
pytest shared/tests agent/tests server/tests/test_protocol_ingest.py -q
python tools/agent_simulator/simulate.py --hosts 3
cd docker && docker compose up -d postgres redis victoria-metrics loki
```

## Next

FS2 leftovers: silent 3-OS packages. FS3 log subsystem. Rebuild server after pull:

`docker compose up -d --build server`  
