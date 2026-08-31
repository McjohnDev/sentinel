# FS5 progress — Central config & coverage
**Date:** 2026-08-13  
**Plan:** PLAN-CBC-IMPL-001  

| Story | Status | Artefact |
|---|---|---|
| FS5-01 Config by machine group | **Done** | `MachineGroup` + `ConfigRevision`; `GET/POST /api/groups`, assign, publish, rollback |
| FS5-02 Agent applies remote config | **Done** | Heartbeat ACK `config: {version,payload}`; overlay YAML; `POST /api/agents/config/ack` |
| FS5-03 Coverage plugins | **Done** | `services.collector`, `files.collector` + existing metric collectors marked delivered in DES-004 |
| FS5-04 CBC service/file lists | **Partial** | Lists ride in group config (`services_monitoring` / `files_monitoring`); official CBC inventory still TBD |
| FS5-05 Agent footprint | **Done** | `agent.footprint` metrics + heartbeat fields; Minor alert if > 2% CPU / 300 MB |
| FS5-06 Duplicate-check flagging | **Done** | `CoverageOverlap` + API + Settings → Couverture PS |

## Demo

1. **Paramètres → Groupes & config** → create group `Agence`, assign an agent ID.  
2. Publish JSON with `services_monitoring.services` / thresholds / `heartbeat_interval`.  
3. Next agent heartbeat receives `config`, writes overlay, acks version — no local YAML edit.  
4. Rollback creates a **new** version (immutable history).

## Check

```bash
curl -H "Authorization: Bearer …" http://localhost:8443/api/groups
curl -H "Authorization: Bearer …" http://localhost:8443/api/coverage/map
```

Rebuild: `docker compose up -d --build server dashboard`
