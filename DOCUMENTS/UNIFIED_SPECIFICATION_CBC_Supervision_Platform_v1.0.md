# UNIFIED SPECIFICATION
## CBC Supervision Platform — Commercial Bank Cameroon

| Field | Value |
|---|---|
| **Document reference** | SPEC-CBC-UNIFIED-001 |
| **Version** | 1.0 — Draft |
| **Date** | 13 August 2026 |
| **Status** | Draft for review |
| **Owner** | CBC Supervision Platform project team |
| **Baseline codebase** | `CBC-Supervision-Platform` @ `main` (product V1.1 developing) |

---

## 0. Purpose of this document

This is the **single master specification** for the CBC Supervision Platform. It unifies and reconciles:

| Source | Role in this document |
|---|---|
| `SPEC-SRV-MON-001` v1.0 | Original technical specification (generic monitoring system) |
| `SPEC-SRV-MON-001` v1.2 | Authoritative technical baseline (macOS, PowerShell replacement, design deliverables, FastAPI) |
| `Cahier des charges CBC` v2.0 | CBC scope annex — Lot 1 business perimeter & constraints |
| `PLAN-SRV-MON-001` v2.1 | Sprint & story plan (greenfield view) |
| Current repository (V1.1) | Implementation baseline — what already exists |
| Gap analysis (Aug 2026) | Remapped delivery sprints **FS0–FS8** from current baseline |
| UI/UX Design Brief | Interface design companion (DES-003) |

**Reading rule:** where sources conflict, **SPEC v1.2** wins for technical requirements; **Cahier CBC v2** wins for CBC organisational scope and Lot-1 phase boundary; **this document’s §2 CBC deltas** record intentional divergences (e.g. Mail Service API).

**Requirement conventions (inherited):**

- IDs: `AGT-xxx`, `PLT-xxx`, `ALR-xxx`, `STO-xxx`, `INT-xxx`, `DSH-xxx`, `API-xxx`, `N8N-xxx`, `SEC-xxx`, `NFR-xxx`, `DES-xxx`
- Priority: **M** Must · **S** Should · **C** Could
- Lot: **1** visualisation/collect · **2** actions/automation · **3** AI option
- Implementation status vs current repo: **Done** · **Partial** · **Missing** · **N/A (Lot 2+)**

---

## 1. Executive summary

CBC operates a heterogeneous IT estate (Windows, Linux, macOS) currently supervised by **fragmented PowerShell scripts** with per-machine JSON configuration. The project delivers a **centralised multiplatform supervision platform** with:

1. A **single generic Python agent per host** (plugin-based), replacing — not migrating — PowerShell scripts.
2. A **FastAPI central platform** (ingest, rules, storage, API).
3. A **web dashboard** for operations (React SPA already in place).
4. **Outbound notifications** (CBC Mail Service API today; signed webhooks required).
5. Later (Lot 2): remote actions, n8n automation, SSO, advanced integrations.

**Current reality (Aug 2026):** a working MVP exists (enrolment, heartbeat, CPU/RAM/disk alerts, React dashboard, JWT RBAC, CBC Mail API, availability windows). Lot 1 **Must** architecture remains incomplete: plugin agent, canonical schemas, TSDB, duration-based rules, durable buffer, log subsystem, PowerShell coverage map, signed webhooks.

---

## 2. CBC deltas (intentional divergences from generic SPEC)

| Topic | Generic SPEC | CBC decision (this unified spec) |
|---|---|---|
| Email (INT-001) | SMTP templated HTML | **CBC Mail Service API** (`/mail`, `X-API-Key`) is the Lot 1 email channel. SMTP remains an optional fallback. Webhook HMAC (INT-003) still required. |
| Workstation availability | Not in generic SPEC | **Availability windows** + `machine_type` (server vs workstation) with differentiated offline thresholds — CBC Must for Lot 1. Distinct from ALR-007 maintenance windows. |
| Notification health (R11) | Implied by INT-009 | Visual **notification channel status** (OK / Degraded / Error / Disabled) is a CBC Must. |
| Services & files lists | Generic AGT-026 | Official **service/file watch lists** to be provided by CBC (SWIFT, etc.); mechanism prepared in V1.1. |
| Branding / UI | Generic SPA | Follow **CBC visual identity** and UI/UX Design Brief (DES-003 companion). |
| Language | FR + EN (NFR-008) | Lot 1 Must; current UI is French-first. |
| Target scale | 500 Lot 1 / 5 000 Lot 2 | **128 agents today**, size to **500** for Lot 1. |

---

## 3. Scope

### 3.1 In scope — Lot 1 (Cahier + SPEC)

- Single multiplatform agent (Windows / Linux / macOS), self-contained packaging
- Plugin architecture for collectors
- Heartbeat, metrics (CPU, memory, disk, network, processes), services/files as configured
- Store-and-forward during platform outage
- Centralised versioned configuration pushed to agents
- FastAPI receiver + validation + PostgreSQL inventory/alerts/users
- Time-series metrics store + rollups + retention
- Rules engine (thresholds with duration, availability, maintenance windows)
- Outbound notify: CBC Mail API + signed webhook; delivery status
- Dashboard: overview, agents, host detail, alerts, settings, users
- Design dossiers DES-001–004 and PowerShell coverage map (AGT-013)
- Replacement of PowerShell scripts once coverage proven (AGT-013/014)

### 3.2 In scope — Lot 1 (SPEC, deferred relative to Cahier core)

Cahier v2 explicitly postpones some items that remain **SPEC Lot 1 Must** — they are scheduled in FS3/FS6 of this unified plan:

- Full log collection (AGT-025–038, STO-003)
- SNMP/ICMP network equipment (AGT-029)
- Custom dashboards & scheduled PDF reports (DSH-003/007)
- External source connectors (basic cloud/virt/containers)

### 3.3 Out of scope until Lot 2

- Remote agent actions (command, service control, patch, dry-run) — AGT-060+
- n8n closed-loop remediation — N8N-xxx
- OIDC/SSO, GraphQL, full public API completeness — API-xxx / DSH-025
- Slack/Teams/PagerDuty/ITSM advanced — INT-004+
- AI assist mode — Lot 3

### 3.4 Explicit non-goals

- Migrating or wrapping existing PowerShell code into the agent
- Long-term dual-agent architecture (legacy script + new agent) beyond a tracked transition
- Deploying a separate log shipper beside the host agent

---

## 4. System overview

### 4.1 Functional flow

```
Hosts → Agent L0 (collect [Lot1] + reject actions)
     → Platform (receive → validate → process → rules/alerts → store)
     → Storage (PostgreSQL + TSDB + log store)
     → Dashboard (visualise [Lot1])
     → Notifications (CBC Mail API, signed webhook)
     → [Lot2] Actions / n8n / ITSM
```

### 4.2 Logical components

1. **Agent** — one binary per host + plugins  
2. **Central platform** — FastAPI receiver, processing, rules, storage, API  
3. **Integrations** — Mail API, webhook, later ITSM/chat  
4. **Dashboard** — React SPA  
5. **n8n** — Lot 2 automation only  

### 4.3 Monitored perimeter

| Resource | Method | Lot |
|---|---|---|
| Windows / Linux / macOS servers & workstations | Agent | 1 |
| Configured OS services & watched files | Agent plugins | 1 |
| Network equipment | SNMP/ICMP (platform or proxy agent) | 1 |
| Cloud / virt / containers (basic) | Connectors | 1–2 |
| Applications (web/DB/runtime) | Role plugins | 1 (S) |

---

## 5. Design deliverables (Part M — SPEC v1.2)

| ID | Deliverable | Content | Prio | Lot | Status |
|---|---|---|---|---|---|
| DES-001 | Agent architecture dossier | Components, plugin lifecycle, enrolment & collect sequences, agent state machine | M | 1 | Missing (README only) |
| DES-002 | Platform architecture dossier | Components, data flow, storage model, Compose/K8s deploy | M | 1 | Partial |
| DES-003 | Interface design dossier | Screen inventory, wireframes, nav map, per-role rights | M | 1 | Done (v1.0 draft — `docs/architecture/DES-003-interface-design.md`; Brief remains visual companion) |
| DES-004 | Functional coverage map | PowerShell check → plugin → status (planned/delivered/verified/decommissioned) | M | 1 | Missing |

Diagrams SHALL be versioned editable artefacts (not images-only) and updated when interfaces change.

---

## 6. Agent requirements

### 6.1 General

| ID | Requirement | Prio | Lot | Status |
|---|---|---|---|---|
| AGT-000 | Exactly one agent per host; all needs met via plugins | M | 1 | Partial (one process, no plugins) |
| AGT-001 | Python 3.11+; Linux (Ubuntu 20.04+, Debian 11+, RHEL/Rocky 8+), Windows Server 2016+ / Win10+, **macOS 12+** | M | 1 | Partial (code multi-OS; Python version/packaging gaps) |
| AGT-001b | Self-contained package; no system Python required on host | M | 1 | Partial (PyInstaller scripts exist) |
| AGT-001c | Single-instance lock (PID/lock); refuse second start | M | 1 | Missing |
| AGT-002 | Collectors/actions as plugins with Pydantic → JSON Schema manifests | M | 1 | Missing |
| AGT-003 | Outbound TLS 1.2+ (443); no inbound port Lot 1 | M | 1 | Partial (`verify=False` in agent) |
| AGT-004 | Enrolment token → unique agent identity/key | M | 1 | Done |
| AGT-005 | Store-and-forward; default 24 h or 500 MB | M | 1 | Partial (in-memory ~100 HB) |
| AGT-006 | Heartbeat default 30 s; missed HB detectable | M | 1 | Done |
| AGT-007 | Footprint ≤ 2% CPU avg / ≤ 300 MB RAM; self-reported | M | 1 | Missing |
| AGT-008 | Remote config push, versioned, by group; rollback | M | 1 | Partial (local YAML + UI settings; no push) |
| AGT-009 | Self-update with rollback | S | 1 | Partial (updater stub) |
| AGT-010 | Reserve `task.v1` envelope; L0 agents reject actions | M | 1 | Missing |
| AGT-011 | Low-privilege account; explicit per-plugin elevation | M | 1 | Missing |
| AGT-012 | `.deb`, `.rpm`, MSI, **`.pkg`**, container; silent install | M | 1 | Partial |
| AGT-013 | PowerShell **replaced not migrated**; coverage map before decommission | M | 1 | Missing |
| AGT-014 | Transition: script+agent may coexist; platform flags duplicate checks | S | 1 | Missing |
| AGT-015 | Self-declare identity: hostname, OS+version, IP(s), agent name/version, timestamp+TZ | M | 1 | Partial |

### 6.2 Collection plugins (L0)

Default interval 60 s (configurable 10 s–15 min).

| ID | Plugin | Prio | Status |
|---|---|---|---|
| AGT-020 | CPU (total, per-core, load, steal, iowait) | M | Partial (total % only) |
| AGT-021 | Memory (used/free/cached, swap, page faults) | M | Partial |
| AGT-022 | Disk (per FS, inodes, IOPS, throughput, latency) | M | Partial (single path usage) |
| AGT-023 | Network (per-IF throughput, errors, drops, TCP states) | M | Missing |
| AGT-024 | Processes (Top-N, watched processes) | M | Missing |
| AGT-025–038 | Logs (file/journald/Event Log, parse, filter, multiline, rate limit, pattern events) | M | Missing |
| AGT-026 | Services (systemd / Windows services) | M | Partial (stubs; CBC list TBD) |
| AGT-027 | OS & agent lifecycle events | M | Missing |
| AGT-028 | Role plugins (web/DB/app) | S | Missing |
| AGT-029 | SNMP v2c/v3 + ICMP (platform/proxy) | M | Missing |

### 6.3 CBC agent extras (Lot 1)

| ID | Requirement | Status |
|---|---|---|
| CBC-AGT-01 | `machine_type`: `server` \| `workstation` | Done |
| CBC-AGT-02 | Availability windows for workstations | Done (config path) |
| CBC-AGT-03 | Configurable services/files monitoring lists | Partial (infra ready; lists empty) |

### 6.4 Action plugins (Lot 2 — summary)

AGT-060–068: on-demand metrics, command execution, service mgmt, file mgmt, health checks, patch, inventory, log shipping, dry-run. All platform-initiated, signed, RBAC, audited. **Status: Missing (Lot 2).**

### 6.5 AI-readiness constraints (design now, features later)

AGT-080–084: manifests usable as LLM tool schemas; structured action results; human approval hook; capability discovery; assist mode Lot 3 only.

---

## 7. Central platform requirements

### 7.1 Receiver / processing

| ID | Requirement | Prio | Lot | Status |
|---|---|---|---|---|
| PLT-001 | Real-time TLS ingest, auth, ACK; at-least-once; dedup by message ID | M | 1 | Partial |
| PLT-002 | Validate vs versioned schemas; invalid → DLQ + alert | M | 1 | Partial (Pydantic models; no DLQ/`metric.v1`) |
| PLT-003 | 500 agents × 8 families @ 60 s Lot 1; ready for 5 000 Lot 2 | M | 1 | Untested |
| PLT-004 | External push connectors / ingestion API | S | 1 | Missing |
| PLT-010 | Canonical event/metric model | M | 1 | Missing |
| PLT-011 | Aggregations/rollups 1 m → 5 m → 1 h → 1 d | M | 1 | Missing |
| PLT-012 | Correlate related events into incidents | M | 1 | Missing |
| PLT-013 | Enrich with inventory/topology metadata | M | 2 | Missing |
| PLT-014 | Status model: OK / Warning / Critical / Unknown | M | 1 | Partial |

### 7.2 Rules & alerts

| ID | Requirement | Prio | Lot | Status |
|---|---|---|---|---|
| ALR-001 | Threshold + **duration** (e.g. CPU > 90% for 5 min) | M | 1 | Missing (instant only) |
| ALR-002 | Heartbeat / availability rules | M | 1 | Done |
| ALR-003 | Log-pattern rules | M | 1 | Missing |
| ALR-004 | Severities: Info, Minor, Major, Critical | M | 1 | Partial (Info/Warning/Critical) |
| ALR-005 | Lifecycle Open → Ack → Resolved (+ auto-resolve, timeline) | M | 1 | Partial |
| ALR-006 | Routing: channels, recipients, schedules, escalation | M | 1 | Partial |
| ALR-007 | Maintenance windows suppress alerts per host/group | M | 1 | Missing (≠ availability windows) |
| ALR-008 | Multi-condition / multi-host correlation | S | 2 | Missing |
| ALR-009 | Noise suppression (dedup, flap, rate limit, group) | M | 2 | Partial (basic open-alert dedup) |
| ALR-010 | Anomaly baselines | C | 2 | Missing |
| ALR-011 | Alert → webhook event for n8n | M | 2 | Missing |

### 7.3 Storage

| ID | Requirement | Prio | Lot | Status |
|---|---|---|---|---|
| STO-001 | TSDB for metrics (VictoriaMetrics / TimescaleDB / Influx — choose) | M | 1 | Missing (HB in PostgreSQL) |
| STO-002 | ≥ 30 d raw; ≥ 13 mo rollups; configurable | M | 1 | Missing |
| STO-003 | Log store + full-text search; ≥ 30 d (Loki/OpenSearch) | M | 1 | Missing |
| STO-004 | PostgreSQL for config, inventory, alerts, audit, users | M | 1 | Done |
| STO-005 | Archive/purge policies per data class | M | 2 | Partial (retention config) |
| STO-006 | Backup/restore; RPO ≤ 24 h | M | 1 | Partial (script; procedure incomplete) |

### 7.4 API (Lot 2 completeness; Lot 1 foundation exists)

| ID | Requirement | Prio | Lot | Status |
|---|---|---|---|---|
| API-001 | REST OpenAPI: hosts, metrics, alerts, rules, actions, inventory, users, config | M | 2 | Partial (core CRUD Lot 1 present) |
| API-002 | GraphQL | S | 2 | Missing |
| API-003 | OAuth2/OIDC + scoped API keys; RBAC | M | 2 | Partial (JWT local) |
| API-004 | Async action submit → task ID → poll/webhook | M | 2 | Missing |
| API-005 | Webhook subscription management | M | 2 | Missing |
| API-006 | Rate limit + audit on API access | M | 2 | Partial (rate limit, audit present) |
| API-007 | Every dashboard op available via API | M | 2 | Partial |

**Confirmed stack:** FastAPI + Pydantic + Uvicorn/Gunicorn; add NATS/Kafka when scaling.

---

## 8. Integrations & notifications

| ID | Channel | Prio | Lot | Status / CBC note |
|---|---|---|---|---|
| INT-001 | Email | M | 1 | **Done via CBC Mail API** (SPEC SMTP variant) |
| INT-002 | SMS | M | 1 | Missing (provider open) |
| INT-003 | Signed HMAC webhook | M | 1 | Missing |
| INT-004 | ITSM (GLPI / ServiceNow / Jira — choose) | M | 1 | Missing |
| INT-005–008 | Slack/Teams, PagerDuty, Telegram, custom | M/S | 2 | Missing |
| INT-009 | Retry/backoff; delivery status visible | M | 1 | Partial |
| CBC-INT-01 | Notification channel health indicator (R11) | M | 1 | Done |

---

## 9. Dashboard requirements

### 9.1 Lot 1 visualisation

| ID | Requirement | Prio | Status |
|---|---|---|---|
| DSH-001 | Overview: fleet status, key charts, recent alerts | M | Partial / Done |
| DSH-002 | Host detail: metrics, time range, services, logs/events | M | Partial (no log pane / weak history) |
| DSH-003 | Custom composable dashboards | M | Missing |
| DSH-004 | Alert list/filter/ack/resolve/timeline | M | Partial / Done |
| DSH-005 | Search hosts, metrics, logs, events | M | Partial |
| DSH-006 | History & trends within retention | M | Partial |
| DSH-007 | Scheduled PDF/CSV reports + on-demand export | M | Partial (CSV only) |
| DSH-008 | Auto-refresh ≤ 60 s | M | Done |
| DSH-009 | Local accounts; ≥ Viewer & Administrator | M | Done (Admin / Operator / Viewer) |

### 9.2 Lot 2 KPIs & actions (summary)

DSH-020–026: header KPIs, severity charts, Maps/Logs/Trends views, dashboard actions via API pipeline, RBAC+SSO, live WS ≤ 5 s.  
**Note:** WebSocket live updates already **Done** (Lot 2 Should).

### 9.3 Roles (Cahier + SPEC)

| Role | Rights (Lot 1) |
|---|---|
| Administrator | All config, users, tokens, thresholds, revoke agents |
| Operator (Exploitant) | Ack/resolve alerts; view fleet; limited config |
| Viewer (Consultation) | Read-only |

Lot 2 adds Security role (audit / security logs) and OIDC SSO.

---

## 10. Data model & protocol (canonical)

All payloads SHALL use versioned schemas. Invalid payloads → DLQ.

### 10.1 `metric.v1`

```json
{
  "schema": "metric.v1",
  "agent_id": "uuid",
  "host": "web-01.prod",
  "ts": "2026-07-30T08:15:00Z",
  "family": "cpu",
  "name": "cpu.total.utilization",
  "value": 87.5,
  "unit": "percent",
  "labels": {"core": "all", "env": "prod", "group": "web"}
}
```

### 10.2 `event.v1`

```json
{
  "schema": "event.v1",
  "source": "agent|platform|external",
  "host": "db-02.prod",
  "ts": "...",
  "type": "service_down|log_match|os_event|...",
  "severity": "info|minor|major|critical",
  "message": "...",
  "attributes": {}
}
```

### 10.3 `task.v1` (defined Lot 1, active Lot 2)

```json
{
  "schema": "task.v1",
  "task_id": "uuid",
  "issued_by": "user|api|n8n|rule",
  "signature": "…",
  "plugin": "service.manage",
  "input": {"service": "nginx", "operation": "restart"},
  "dry_run": false,
  "approval_ref": "optional",
  "expires_at": "..."
}
```

L0 agents **reject** action tasks. Envelope reserved from Lot 1 (AGT-010).

**Current gap:** codebase uses flat heartbeat JSON — migration to canonical schemas is FS0/FS1.

---

## 11. Security

| ID | Requirement | Prio | Lot | Status |
|---|---|---|---|---|
| SEC-001 | TLS 1.2+; mTLS recommended agent↔platform | M | 1 | Partial |
| SEC-002 | One-time enrolment token; credential rotation | M | 1 | Partial (token done; rotation weak) |
| SEC-003 | Secrets encrypted at rest; never plain in config files | M | 1 | Partial (env vars) |
| SEC-004 | Immutable audit: config changes, alert actions, (Lot 2) agent actions | M | 1/2 | Partial |
| SEC-005 | Action auth chain (RBAC → approval → sign → allow-list → exec → audit) | M | 2 | Missing |
| SEC-006 | Security log classification; Security-role access | M | 2 | Missing |
| SEC-007 | Independent security review before Lot 2 go-live | M | 2 | Missing |
| SEC-008 | Hardening guides agent + platform | S | 1 | Missing |

Banking context: auditability of configuration and alert handling is non-negotiable.

---

## 12. Non-functional requirements

| ID | Target | Lot | Status |
|---|---|---|---|
| NFR-001 | Collect → dashboard ≤ 60 s (Lot 1); ≤ 15 s (Lot 2) | 1/2 | Untested |
| NFR-002 | Detect → notify ≤ 30 s | 1 | Untested |
| NFR-003 | Availability ≥ 99.5% Lot 1; ≥ 99.9% HA Lot 2 | 1/2 | Untested |
| NFR-004 | 500 agents Lot 1; architecture for 5 000 Lot 2 (CBC: 128 now) | 1/2 | Untested |
| NFR-005 | Dashboard page load ≤ 3 s | 1 | Untested |
| NFR-006 | Zero data loss on platform restart (buffer + queues) | 1 | Partial |
| NFR-007 | Action feedback ≤ 5 s after completion | 2 | N/A |
| NFR-008 | UI French + English | 1 | Missing |
| NFR-009 | Docker Compose + Kubernetes option | 1 | Partial (Compose: Postgres+server only) |
| NFR-010 | Platform self-monitoring via same pipeline | 1 | Partial (Prometheus metrics) |

---

## 13. Technology baseline (confirmed)

| Layer | Choice |
|---|---|
| Agent | Python 3.11+, PyInstaller, psutil, httpx, Pydantic, APScheduler |
| Platform | **FastAPI** + Pydantic + Uvicorn/Gunicorn |
| Relational DB | PostgreSQL |
| TSDB | **TBD** — VictoriaMetrics *or* TimescaleDB (open point) |
| Logs | **TBD** — Grafana Loki *or* OpenSearch |
| Cache | Redis (already used) |
| Dashboard | React + TypeScript + Vite + Tailwind (existing) |
| Auth Lot 1 | Local JWT + RBAC |
| Auth Lot 2 | OIDC (Keycloak or corporate IdP) |
| Automation Lot 2 | n8n self-hosted |
| Deploy | Docker Compose (Lot 1); Kubernetes HA (Lot 2 option) |

---

## 14. Delivery roadmap

### 14.1 Relationship to Plan v2.1

`PLAN-SRV-MON-001` v2.1 assumed greenfield Sprints 0–8. The repository already covers parts of S1/S2/S4/S5 (dashboard, FastAPI, enrolment, basic alerts, Mail API).  

**This unified plan uses remapped sprints FS0–FS8** that start from the V1.1 MVP and close Lot 1 Must gaps, then FS9+ for Lot 2.

### 14.2 Lot 1 — Future sprints (from current baseline)

| Sprint | Title | Objective | Key refs |
|---|---|---|---|
| **FS0** | Contracts, design, inventory | Freeze `metric.v1`/`event.v1`/`task.v1` + plugin manifest; DES-001–004; PowerShell map; Compose+TSDB; 3-OS CI | S0-*, DES-*, AGT-013 |
| **FS1** | Plugin agent & resilience | Plugin host, lock, durable 24h/500MB buffer, TLS verify, DLQ, CPU golden plugin | AGT-002/001c/005/020, PLT-001/002 |
| **FS2** | Metric depth, TSDB, packaging | Mem/disk/net/process plugins; rollups; host charts; silent .deb/.rpm/.msi/.pkg; first coverage plugins | AGT-021–024/012, STO-001/002 |
| **FS3** | Log subsystem | File/journald/Event Log, parsers, filters, rate limit, log store + search | AGT-030–038, STO-003 |
| **FS4** | Rules & notifications | Duration thresholds, 4 severities, maintenance windows, escalation, HMAC webhook; keep CBC Mail API | ALR-001/004–007, INT-003/009 |
| **FS5** | Config groups & coverage | Versioned group config push; finish AGT-013 plugins; CBC service/file lists; footprint reporting | AGT-008/007/013 |
| **FS6** | Analysis & perimeter | Custom dashboards, PDF/CSV schedules, i18n FR/EN, SNMP/ICMP, basic connectors | DSH-003/007, NFR-008, AGT-029 |
| **FS7** | Stabilisation | Load 128→500, latency NFRs, 3-OS regression, backup RPO, hardening guides | NFR-*, STO-006, SEC-008 |
| **FS8** | Pilot & extinction | UAT families; coverage map → zero; decommission scripts; Lot 1 acceptance (M4) | AGT-014, Part K |

### 14.3 Lot 2 — After Lot 1 (FS9+)

- Activate `task.v1` + action plugins (AGT-060–068, SEC-005/007)  
- OIDC SSO + Security role (DSH-025)  
- n8n starter pack (N8N-001–007)  
- Noise suppression / correlation (ALR-008/009)  
- ITSM / Teams / Slack (INT-004/005)  
- Scale path to 5 000 agents / HA  

### 14.4 First 30 days (recommended)

1. Freeze shared Pydantic schemas (`metric.v1`, `event.v1`, `task.v1`, plugin manifest)  
2. Produce DES-004 PowerShell coverage map with CBC ops  
3. Add chosen TSDB to `docker-compose`  
4. Start agent plugin host + instance lock + durable buffer  
5. Confirm INT-001 = CBC Mail API; schedule INT-003 webhook  

Story-level detail for S0–S4 remains in `07_Plan_Sprints_v2.1_et_Stories.md`; map those stories onto FS0–FS4 when planning iterations.

---

## 15. Acceptance & test mapping (Part K)

Each requirement ID SHALL map to ≥ 1 test case. UAT families:

1. Fleet onboarding (install, enrol, first metrics)  
2. Metric correctness vs OS tools  
3. Alerting E2E (trigger → notify all Lot 1 channels → ack → resolve → escalate)  
4. Resilience (outage → buffer → recovery; agent restart; network flap)  
5. History & reporting (retention, rollups, exports)  
6. **Lot 2:** actions on Linux+Windows, RBAC denials, approval, audit, API contracts, 5 n8n workflows, security abuse cases  

**Lot 1 exit (FS8 / M4):** coverage map has zero uncovered PowerShell checks verified in production; NFR targets measured; DES artefacts up to date.

---

## 16. Open points (must close)

| # | Point | Blocks |
|---|---|---|
| 1 | Final TSDB choice (VictoriaMetrics vs TimescaleDB) | FS2 |
| 1b | macOS perimeter size & versions | Packaging / NFR |
| 1c | Inventory of legacy PowerShell scripts | DES-004, AGT-013, FS8 |
| 2 | Target ITSM tool | INT-004 |
| 3 | SMS gateway provider | INT-002 |
| 4 | Exact fleet size & growth | NFR-004 sizing |
| 5 | HA for Lot 1 vs single-node Compose | Deploy architecture |
| 6 | SSO / corporate IdP availability | Lot 2 OIDC |
| 7 | Patch depth (OS only vs apps) | AGT-065 Lot 2 |
| CBC-A | Official services list to monitor | AGT-026 / CBC-AGT-03 |
| CBC-B | Official files list to monitor | CBC-AGT-03 |
| CBC-C | Official workstation offline threshold | Availability policy |
| CBC-D | Backup RPO/RTO & dimensioning numbers | STO-006 / ops |

---

## 17. Document control

### 17.1 Supersession

| Document | Status relative to this unified spec |
|---|---|
| SPEC-SRV-MON-001 v1.0 | Superseded as standalone; content absorbed |
| SPEC-SRV-MON-001 v1.2 | Technical parent; this doc is the CBC project binding view |
| Cahier CBC v2.0 | Scope parent for Lot 1 phase; absorbed into §§2–3 |
| Plan sprints v2.1 | Planning parent; remapped in §14 |
| Gap canvas Aug 2026 | Analysis input; findings in Status columns |

### 17.2 Companion artefacts

- `docs/architecture/DES-003-interface-design.md` — interface dossier (IA, workflows, Studio Agent, n8n)
- `docs/architecture/DES-003-MOCKUP-BRIEF.md` — self-contained mockup handoff for Claude / design
- `docs/UI-UX-Design-Brief.md` / DOCUMENTS UI_UX PDF — visual identity companion to DES-003  
- `docs/INSTALLATION_GUIDE.md` — deploy procedures  
- `README.md` — product overview & changelog V1.0/V1.1  
- Living DES-001–004 (to be created under `docs/architecture/`)  
- `docs/IMPLEMENTATION_SPRINTS_CBC_Supervision_Platform_v1.0.md` (+ PDF) — executable Lot 1 sprint plan (PLAN-CBC-IMPL-001)  
- PDF edition: `docs/UNIFIED_SPECIFICATION_CBC_Supervision_Platform_v1.0.pdf`

### 17.3 Change log

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | 2026-08-13 | Project (draft) | First unified specification: merge SPEC v1.2 + Cahier v2 + Plan v2.1 + repo baseline + remapped FS roadmap; PDF + implementation sprint plan published |

### 17.4 Approval (to be completed)

| Entity | Name / role | Date | Signature |
|---|---|---|---|
| DTDSI — Support | | | |
| DPPI — Beneficiary | | | |
| DPIRS — Beneficiary | | | |

---

*End of SPEC-CBC-UNIFIED-001 v1.0*
