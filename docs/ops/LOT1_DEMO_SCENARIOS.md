# Lot 1 — How to see the platform work

**Audience:** operators, testers, demo to CBC  
**Stack:** Docker Compose lab on this machine  
**URLs:** Dashboard http://localhost:3000 · API http://localhost:8443/docs  

Demo logins:

| Role | Email | Password |
|---|---|---|
| Admin | `admin@cbc.cm` | `Admin123!` |
| Operator | `operator@cbcam.cm` | `Operator123!` |
| Viewer | `readonly@cbcam.cm` | `Readonly123!` |

Start (from repo root):

```powershell
docker compose -f docker/docker-compose.yml up -d --build
```

Hard-refresh the dashboard after a rebuild (Ctrl+F5).

---

## 0. Build and run an agent (required for most scenarios)

You already have a Linux agent in Docker (`sentinel-agent`). To also run **this Windows host**:

### A. From source (fastest)

```powershell
.\scripts\run_windows_agent.ps1
```

Uses `agent/config.lab.yaml` → `http://127.0.0.1:8443` with token `demo-token-123`.

### B. Frozen exe (Lot 1 packaging)

```powershell
python -m pip install pyinstaller -r agent\requirements.txt -r shared\requirements.txt
python -m PyInstaller --clean --noconfirm --distpath agent\packaging\dist --workpath agent\packaging\build agent\packaging\agent.spec
.\agent\packaging\dist\cbc-agent\cbc-agent.exe agent\config.lab.yaml
```

If Windows Defender locks the exe, run from source instead (option A) or add an exclusion for `agent\packaging\dist`.

Silent install commands (once `.msi` / `.deb` / `.rpm` / `.pkg` exist) are in `agent/packaging/DISTRIBUTION.md`.

### C. Docker agent only

If you skip the Windows host, use the container already named `sentinel-agent` (hostname `sentinel-agent`, type **server**).

After ~30 s the host should appear on **Agents** as online, with CPU/RAM/disk.

---

## Family 1 — Fleet onboarding

### S1. Login and roles
1. Open http://localhost:3000  
2. Log in as Admin, then log out and try Operator and Viewer.  
3. Confirm Viewer cannot change settings or generate tokens.

### S2. Dashboard overview
1. Admin → **Dashboard**.  
2. Check fleet KPIs (online / offline / alerts).  
3. Check **notification channel** badge (OK / Degraded / Error / Disabled). Mail is often Disabled in lab (`MESSAGING_ENABLED=false`).

### S3. Enrol a new agent
1. **Paramètres → Jetons** → generate a token (or use `demo-token-123` in lab).  
2. Put it in `agent/config.lab.yaml` → `server.enrollment_token`.  
3. Start the agent (scenario 0).  
4. **Agents** → new hostname, status **En ligne**, OS/version, IP.

### S4. Agent detail + live metrics
1. Click the agent.  
2. See CPU, RAM, disk, last heartbeat.  
3. Open **Métriques** — history chart from VictoriaMetrics.  
4. Wait 1–2 minutes; chart should grow.

### S5. CSV export
1. **Agents** and **Alertes** → export CSV.

---

## Family 2 — Metrics, logs, history

### S6. Plugin metrics (CPU / RAM / disk / net / process)
1. Agent detail → metrics tab.  
2. Confirm series such as `cpu.total.utilization`, `memory.used.percent`, `disk.used.percent`.  
3. On Windows lab config, watched processes include `explorer` / `python`.

### S7. Log search (Loki)
1. Lab config has `logs.enabled: true` and Windows Event Log (`System`, `Application`).  
2. Open **Journaux / Logs**.  
3. Filter by host, severity, time.  
4. New Event Log lines should appear within ~60 s.

### S8. History range
1. Agent detail → change time range if the UI exposes it (or wait).  
2. Confirm points persist after refreshing the page (TSDB, not only RAM).

### S9. Invalid payload → DLQ (admin)
1. From Swagger http://localhost:8443/docs login, or:

```powershell
# After agent enrolled, this is easier via Swagger POST /api/ingest/metrics
# with a broken body, then:
# GET /api/ingest/dlq  (Admin JWT)
```

2. **Paramètres → Plateforme** — `metrics_dlq` count > 0 shows **degraded**.

---

## Family 3 — Alerting end-to-end

### S10. Duration threshold (spike does **not** alert)
1. **Paramètres → Seuils** — `durationSeconds` default **300**.  
2. Briefly stress CPU (Task Manager or `python -c "while True: pass"` for 10 s).  
3. Confirm **no** CPU alert.  
4. Keep the stress **> 5 min** → **Major** CPU alert appears.

### S11. Ack → resolve → timeline
1. Open the alert.  
2. Operator **Acquitter**.  
3. Stop the stress; wait for auto-resolve, or **Résoudre**.  
4. Timeline shows opened / ack / resolved.

### S12. Four severities
1. **Alertes** filters: Info / Minor / Major / Critical.  
2. Footprint over 2% CPU / 300 MB RAM → Minor (agent self-watch).

### S13. Offline detection (server vs workstation)
1. Stop the Docker agent: `docker stop sentinel-agent`.  
2. Wait ~90 s (server timeout) → agent **Hors ligne** + offline alert.  
3. `docker start sentinel-agent` → back online, alert resolves.  
4. For a **workstation** (Windows lab agent), default offline is **2 h** unless you set a lower `offline_threshold_seconds` in availability policy.

### S14. Availability windows (workstation)
1. **Paramètres → Fenêtres Horaires** — enable, set e.g. Monday 08:00–18:00.  
2. Assign to the workstation agent (or global).  
3. Outside the window, stopping the agent must **not** raise offline.

### S15. Maintenance window
1. Create a maintenance window for the agent (settings / API `/api/maintenance`).  
2. Stress CPU during the window → metric alerts **suppressed** (timeline `suppressed`).  
3. Delete the window.

### S16. Escalation
1. Leave a Major/Critical **unacked**.  
2. After `escalateAfterMinutes` (default 15) severity becomes Critical and a re-notify is attempted.

### S17. Log-pattern alert
1. Lab `alert_patterns` includes `error` / `failed`.  
2. Generate a matching Windows event or drop a line in a tailed file.  
3. Alert type `log_pattern` appears.

### S18. Mail + webhook (needs CBC Mail API)
Lab compose has `MESSAGING_ENABLED=false`. To demo notify:

1. Set mail API URL + key in **Paramètres → Notifications**.  
2. Set webhook URL + HMAC secret.  
3. Raise a Major/Critical (S10).  
4. Alert shows `mail_status` / `webhook_status`.  
5. Receiver must see `X-CBC-Signature: sha256=…`.

---

## Family 4 — Resilience

### S19. Platform outage → durable buffer
1. `docker stop sentinel-server`.  
2. Keep the **host** agent running 2–5 min (heartbeats fail, buffer fills under `data/agent-buffer`).  
3. `docker start sentinel-server` — wait until healthy.  
4. Metrics catch up; no crash loop.

### S20. Single-instance lock
1. With one agent running, start a second process with the same lock.  
2. Second process exits with a lock error.

### S21. TLS verify
Production default is `tls_verify: true`. Lab HTTP uses `false` in `config.lab.yaml`. Pointing a verify=true agent at HTTP must fail clearly.

---

## Family 5 — Config, coverage, reports, perimeter

### S22. Group config push (no SSH)
1. **Paramètres → Groupes & config** → create group e.g. `Agence`.  
2. Assign the Windows agent ID.  
3. Publish JSON, for example:

```json
{
  "agent": { "heartbeat_interval": 20 },
  "services_monitoring": { "enabled": true, "services": ["Spooler"] }
}
```

4. Next heartbeat: agent logs `Applied remote config`; platform receives ack.  
5. **Rollback** creates a new immutable version.

### S23. Coverage map / PowerShell extinction
1. **Pilot & UAT** or **Paramètres → Couverture PS**.  
2. Rows PS-001–PS-008 are `delivered`.  
3. Admin: bulk verify → decommission (CBC still owes real script paths).  
4. Overlaps: flag a host where legacy script + plugin both run.

### S24. Custom dashboard
1. **Tableaux perso.** → create board, add widgets, share.

### S25. Reports
1. **Rapports** → on-demand CSV/PDF.  
2. Admin: add a schedule.

### S26. i18n
1. Header **FR / EN** toggle — nav labels switch.

### S27. Network ICMP/SNMP
1. **Réseau** → add `127.0.0.1` or a LAN printer.  
2. **Probe** — ICMP ping; SNMPv2c `sysDescr` if a community is set.

### S28. Docker connector
1. Admin → connectors → Docker host probe (if Docker API reachable).

### S29. Platform self-health
1. **Paramètres → Plateforme**.  
2. Postgres, Redis, VictoriaMetrics, Loki, API, metrics DLQ.  
3. http://localhost:8443/health/platform

---

## Family 6 — Pilot, UAT, acceptance (M4)

### S30. Pilot host checklist
1. **Pilot & UAT** → add this PC as a pilot host.  
2. Tick enroll / first metrics / heartbeat / alerts visible.

### S31. UAT cases
1. Mark families 1, 3, 4, 5 pass/fail with evidence notes.

### S32. Acceptance pack
1. Export pack JSON.  
2. Record sign-offs: `cbc_ops`, `tech_lead`, `sponsor` (CBC meeting).

---

## Family 7 — Users, audit, settings

### S33. User management (Admin)
1. **Utilisateurs** — create/disable; three roles.

### S34. Thresholds + retention
1. Change CPU warning/critical; save; confirm agent alerts follow new values after duration.  
2. Retention settings (alert history 30 days).

### S35. Notification channel R11
1. With messaging off → channel **Disabled**.  
2. Enable with a bad URL → **Error**.  
3. Enable with CBC Mail `/health` OK → **Opérationnel**.

---

## Family 8 — Lot 2 starter (optional — not Lot 1 Must)

These screens exist (`/actions`, `/approvals`) but Lot 1 agents stay **L0** (reject remote actions). Skip in a Lot 1 acceptance demo unless you explicitly mark an agent L1.

---

## Suggested 20-minute stakeholder path

1. Login Admin → Dashboard KPIs (S2)  
2. Agents list + Docker `sentinel-agent` online (S3–S4)  
3. Start Windows agent from `.\scripts\run_windows_agent.ps1` → second host appears  
4. Agent detail charts (S4, S6)  
5. Logs view (S7)  
6. Stop Docker agent → offline alert (S13) → start again  
7. Group config publish (S22)  
8. Custom dashboard + FR/EN (S24, S26)  
9. Pilot & UAT screen (S30)  
10. Paramètres → Plateforme health (S29)

---

## What CBC must still provide (cannot be closed in code)

See `docs/ops/CBC_WATCH_LISTS.md` and unified spec open points:

- Official PowerShell script inventory (DES-004 paths)  
- Official services / files to watch (SWIFT, etc.)  
- Official workstation offline threshold  
- Mail API credentials for live notify  
- Sign-off names for M4
