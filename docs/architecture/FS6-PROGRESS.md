# FS6 progress — Dashboards, reports, i18n, perimeter
**Date:** 2026-08-13  
**Plan:** PLAN-CBC-IMPL-001  

| Story | Status | Artefact |
|---|---|---|
| FS6-01 Custom dashboards | **Done** | `CustomDashboard` + `/api/dashboards`; UI `/dashboards` (widgets + share) |
| FS6-02 Reports CSV/PDF | **Done** | `report_service` + schedules `/api/reports/*`; UI `/reports` |
| FS6-03 i18n FR + EN | **Done** | `src/i18n.tsx`; Header language toggle; Sidebar nav keys |
| FS6-04 SNMP/ICMP perimeter | **Done** | `network_probe` + `NetworkDevice` + `/api/network/*`; UI `/network` |
| FS6-05 Docker connector | **Done** | `connector_service` + `ExternalConnector` + `/api/connectors/*` |

## Demo

1. Header **EN/FR** toggle — nav labels switch.  
2. **Tableaux perso.** → create board, add widgets, share.  
3. **Rapports** → download CSV/PDF; Admin can add a schedule.  
4. **Réseau** → add host, Probe (ICMP + SNMPv2c sysDescr); Admin adds Docker connector and Probe.

## Check

```bash
cd server && python -m pytest tests/test_fs6_perimeter.py -q
curl -H "Authorization: Bearer …" http://localhost:8443/api/dashboards
curl -H "Authorization: Bearer …" http://localhost:8443/api/network/devices
```

Rebuild: `docker compose up -d --build server dashboard`
