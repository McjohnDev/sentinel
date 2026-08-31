# IMPLEMENTATION SPRINT PLAN
## CBC Supervision Platform — Lot 1 delivery from V1.1 baseline

| Field | Value |
|---|---|
| **Document reference** | PLAN-CBC-IMPL-001 |
| **Version** | 1.0 — Draft |
| **Date** | 13 August 2026 |
| **Parent** | SPEC-CBC-UNIFIED-001 v1.0 |
| **Replaces for execution** | Greenfield view of PLAN-SRV-MON-001 v2.1 (stories remapped) |
| **Baseline** | Repository product V1.1 (enrolment, heartbeat, FastAPI, React dashboard, CBC Mail API) |

---

## 1. How to read this plan

- Sprints are labelled **FS0–FS8** (Future Sprints from current baseline).
- Story IDs: `FS{n}-{nn}` (e.g. `FS0-01`).
- Points: **1** = few hours · **2** ≈ 1 day · **3** ≈ 2–3 days · **5** ≈ 1 week.
- Roles: **S** senior · **J** junior/intern · **S+J** pair · **C** frontend.
- **DoD (all stories):** code reviewed · unit tests where applicable · docs/DES updated if interface changes · demo’d in sprint review · requirement ID traced.
- **DoR:** SPEC ID + acceptance criteria + (for J) reference implementation pointer.

**Already Done (do not rebuild):** enrolment token flow, basic heartbeat, FastAPI core API, PostgreSQL agents/alerts/users, React overview/agents/alerts/users/settings, JWT RBAC (3 roles), CBC Mail API + R11 channel health, availability windows / `machine_type`, WebSocket push, CSV export, packaging scripts (unproven silent CI).

---

## 2. Timeline overview

| Sprint | Duration | Theme | Est. pts | Milestone |
|---|---|---|---|---|
| FS0 | 2 weeks | Contracts, design, inventory, stack | ~24 | M1 — Design & contracts approved |
| FS1 | 2–3 weeks | Plugin agent + resilience + DLQ | ~28 | Plugin host live |
| FS2 | 2–3 weeks | Metrics depth + TSDB + packages | ~31 | History & 3-OS install |
| FS3 | 2–3 weeks | Log subsystem | ~27 | Logs searchable |
| FS4 | 2–3 weeks | Rules engine + webhooks | ~32 | Alerting Lot-1 complete |
| FS5 | 2 weeks | Config groups + script coverage | ~20 | Central config + AGT-013 mid |
| FS6 | 2 weeks | Reports, i18n, SNMP, connectors | ~18 | Lot-1 perimeter closed |
| FS7 | 2 weeks | Stabilisation & NFR proof | ~15 | Ready for pilot |
| FS8 | 2–3 weeks | Pilot, extinction, UAT | ~12 | **M4 — Lot 1 accepted** |

**Indicative Lot 1 calendar:** ~18–22 weeks from FS0 start.  
**Lot 2 (FS9+):** separate plan after M4 (actions, n8n, OIDC, ITSM).

```
FS0 ──► FS1 ──► FS2 ──► FS3 ──► FS4 ──► FS5 ──► FS6 ──► FS7 ──► FS8 (Lot 1 UAT)
                                              │
                                              └── CBC Mail API kept; webhook added in FS4
```

---

## 3. Sprint FS0 — Contracts, design & foundations
**Goal:** Nobody blocked at FS1. Freeze schemas. Map PowerShell estate. Runnable stack with TSDB.

| ID | Story | Acceptance criteria | Refs | Who | Pts |
|---|---|---|---|---|---|
| FS0-01 | Freeze canonical data contracts | Pydantic models `metric.v1`, `event.v1`, `task.v1` + plugin manifest in `shared/`; JSON Schema exported; valid & invalid fixtures; published in repo | Part G, AGT-002, AGT-010 | S | 5 |
| FS0-02 | Agent architecture dossier | DES-001: component diagram, plugin lifecycle, collect & enrol sequences, agent state machine; editable + reviewed | DES-001 | S+J | 3 |
| FS0-03 | Platform architecture dossier | DES-002: components, data flow to UI, storage model, Compose/K8s deploy diagram | DES-002 | S+J | 3 |
| FS0-04 | Interface dossier sync | DES-003 reconciled with UI/UX Brief + current React screens; nav map; rights per role | DES-003 | J+C | 2 |
| FS0-05 | PowerShell coverage map v0 | DES-004 table: check → host(s) → planned plugin → status=`planned`; CBC ops workshop done | DES-004, AGT-013 | S+J | 5 |
| FS0-06 | Compose stack with TSDB | `docker compose up` starts Postgres + chosen TSDB + Redis + API; README one-command | NFR-009, STO-001 | S | 3 |
| FS0-07 | Decide TSDB & log store | Written ADR: VictoriaMetrics **or** TimescaleDB; Loki **or** OpenSearch; recorded in UNIFIED SPEC open points | Part L | S | 2 |
| FS0-08 | CI lint/tests skeleton | PR pipeline runs lint + unit tests (Linux required; Windows/macOS matrix planned) | AGT-001 | S | 3 |
| FS0-09 | Agent simulator & contract tests | Simulator emits N hosts with valid/invalid payloads against frozen schemas | — | J | 3 |

**Demo:** DES artefacts presented; sample payload validated & stored; Compose up in < 5 min.  
**Exit:** M1 approved; open points 1 & 1c addressed or scheduled with owners.

---

## 4. Sprint FS1 — Plugin agent core & resilience
**Goal:** Replace monolithic collector path with plugin host; durable buffer; schema-valid ingest + DLQ.

| ID | Story | Acceptance criteria | Refs | Who | Pts |
|---|---|---|---|---|---|
| FS1-01 | Plugin framework | Registry loads plugins by manifest; fake plugin runs; docs for authors | AGT-002, AGT-080 | S | 5 |
| FS1-02 | Single-instance lock | Second process exits with clear error on Win/Linux/macOS | AGT-000, AGT-001c | J | 2 |
| FS1-03 | TLS verify + enrolment hardening | Agent rejects invalid certs (no `verify=False` in default prod mode); enrolment token single-use retained | AGT-003/004, SEC-001 | S | 5 |
| FS1-04 | Durable store-and-forward | Disk buffer default 24 h / 500 MB; ordered replay; zero loss after platform outage test | AGT-005, NFR-006 | S | 5 |
| FS1-05 | Full identity on every payload | AGT-015 fields + timezone on enrol and each metric/event batch | AGT-015 | J | 2 |
| FS1-06 | Receiver schema validation + DLQ | Authenticated ingest; Pydantic `metric.v1`; ACK; dedup by message ID; invalid → DLQ + alert | PLT-001, PLT-002 | S | 5 |
| FS1-07 | CPU golden-path plugin | Manifest, collect (total+per-core), tests, docs — template for others | AGT-020 | S+J | 3 |
| FS1-08 | Reserve task channel (reject) | Agent accepts `task.v1` envelope structure but L0 rejects execution with structured response | AGT-010 | S | 2 |
| FS1-09 | Heartbeat/status regression | Existing offline detection still works after refactor | AGT-006, ALR-002 | J | 2 |

**Demo:** Kill API 10 min → buffer fills → restart → metrics catch up; second agent instance refused; invalid payload in DLQ.  
**Exit:** Plugin host is the only collection path for CPU.

---

## 5. Sprint FS2 — Metrics depth, TSDB, packaging
**Goal:** Full L0 system metrics in TSDB; silent packages; first PowerShell replacements.

| ID | Story | Acceptance criteria | Refs | Who | Pts |
|---|---|---|---|---|---|
| FS2-01 | Memory plugin | Matches golden path; OS-consistent values; unit tests | AGT-021 | J | 3 |
| FS2-02 | Disk plugin | Per mount point; threshold-ready series | AGT-022 | J | 3 |
| FS2-03 | Network + process plugins | Per-IF throughput/errors; Top-N + watched processes | AGT-023, AGT-024 | J | 5 |
| FS2-04 | TSDB write + rollups | Points written; rollups 1m→1h→1d; retention config 30d/13mo | STO-001, STO-002, PLT-011 | S | 5 |
| FS2-05 | Host detail from TSDB | Agent detail charts over selectable range | DSH-002, DSH-006 | C+J | 5 |
| FS2-06 | Silent packages 3 OS | CI builds `.deb` `.rpm` `.msi` `.pkg`; silent install validated | AGT-012 | S | 5 |
| FS2-07 | First coverage plugins | ≥ N PowerShell checks (from DES-004) delivered as plugins; map updated | AGT-013 | S+J | 3 |
| FS2-08 | Services/files collectors | Real collection for configured lists (not stubs); CBC list placeholders documented | AGT-026, CBC-AGT-03 | J | 3 |

**Demo:** Charts for 24 h history; silent install on one Linux + one Windows host.  
**Exit:** STO-001 operational; coverage map has first `delivered` rows.

---

## 6. Sprint FS3 — Log subsystem
**Goal:** First-class log collection without a side shipper.

| ID | Story | Acceptance criteria | Refs | Who | Pts |
|---|---|---|---|---|---|
| FS3-01 | File log tailing | Multi-file/glob; rotation; persisted offsets; no loss/dup on restart | AGT-030 | S | 5 |
| FS3-02 | journald + Windows Event Log | System/Application (+ configurable channels) | AGT-031 | J | 3 |
| FS3-03 | Parsers | regex/JSON/syslog; ts/severity/message; raw if `parsed=false` | AGT-032 | J | 5 |
| FS3-04 | Source filters | include/exclude; drop stats reported | AGT-033 | J | 3 |
| FS3-05 | Multiline grouping | Configurable start-pattern | AGT-034 | S | 3 |
| FS3-06 | Rate limit + spill | Default 5 MB/min; local spill; platform alert on limit | AGT-038 | S | 3 |
| FS3-07 | Log store + UI search | Full-text search; filter host/severity/period | STO-003, DSH-005 | S+C | 5 |
| FS3-08 | Pattern → event.v1 | Matching lines emit immediate events for ALR-003 | AGT-036 | S | 2 |

**Demo:** Tail nginx error log → appear in UI search < 60 s; rate-limit alert triggered in test.  
**Exit:** Log path Lot-1 Must accepted in review.

---

## 7. Sprint FS4 — Rules, alerts, notifications
**Goal:** Close Cahier Lot-1 alerting & outbound notify gaps.

| ID | Story | Acceptance criteria | Refs | Who | Pts |
|---|---|---|---|---|---|
| FS4-01 | Duration thresholds | Rule “metric > X for N minutes”; editable in UI; no alert on spike | ALR-001 | S | 5 |
| FS4-02 | Four severities + auto-resolve | Info/Minor/Major/Critical; Open→Ack→Resolved; auto-resolve + timeline | ALR-004, ALR-005 | S+J | 5 |
| FS4-03 | Maintenance windows | Per host/group; suppress + audit; distinct from availability windows | ALR-007 | J | 3 |
| FS4-04 | Routing & escalation | Recipients, channels, schedules, escalate after N min unacked | ALR-006 | S | 5 |
| FS4-05 | Keep CBC Mail API polished | Delivery status on alert; retry/backoff; templates | INT-001 (CBC), INT-009 | S | 2 |
| FS4-06 | Signed HMAC webhook | Per-rule URL; HMAC signature; retry; status visible | INT-003, INT-009 | J | 3 |
| FS4-07 | Log-pattern alert rules | ALR-003 wired to FS3 events | ALR-003 | S | 3 |
| FS4-08 | Alert UI polish | Filters, ack, resolve, timeline, delivery status | DSH-004 | C+J | 3 |
| FS4-09 | Offline regression | Existing ALR-002 + availability windows still correct | ALR-002, CBC-AGT-02 | J | 2 |

**Demo:** Sustained CPU 5 min → Major email + webhook; maintenance suppresses; spike does not alert.  
**Exit:** Lot-1 notify channels = Mail API + webhook both green.

---

## 8. Sprint FS5 — Central config & coverage completion
**Goal:** Config no longer edited on each machine; PowerShell map largely delivered.

| ID | Story | Acceptance criteria | Refs | Who | Pts |
|---|---|---|---|---|---|
| FS5-01 | Config by machine group | Create groups; assign agents; versioned config; rollback | AGT-008 | S+J | 5 |
| FS5-02 | Agent applies remote config | Pull/push apply without SSH; ack version to platform | AGT-008 | S | 5 |
| FS5-03 | Coverage plugins complete | All DES-004 `planned` → `delivered` (or waived with sign-off) | AGT-013 | S+J | 5 |
| FS5-04 | CBC service/file lists live | Official lists from CBC loaded; collectors verified | CBC-A/B | S | 2 |
| FS5-05 | Agent footprint self-report | CPU/RAM of agent reported as metrics; alert if over AGT-007 | AGT-007 | J | 2 |
| FS5-06 | Duplicate-check flagging | Platform flags overlapping legacy script + plugin checks | AGT-014 | S | 3 |

**Demo:** Change threshold for group “Agence” → agents pick up new version without local edit.  
**Exit:** Central config is default ops path.

---

## 9. Sprint FS6 — Analysis, i18n, perimeter
**Goal:** Remaining Lot-1 Must visualisation & network perimeter.

| ID | Story | Acceptance criteria | Refs | Who | Pts |
|---|---|---|---|---|---|
| FS6-01 | Custom dashboards | User widget grids; shareable | DSH-003 | C | 5 |
| FS6-02 | Scheduled reports | PDF/CSV schedule + on-demand | DSH-007 | S+C | 5 |
| FS6-03 | i18n FR + EN | Language switch; all Lot-1 screens | NFR-008 | C | 3 |
| FS6-04 | SNMP/ICMP checks | Poll network gear; status on dashboard | AGT-029 | S | 5 |
| FS6-05 | Basic external connectors | At least one of: Docker host metrics or VMware/Hyper-V basic | PLT-004 | S | 3 |

**Demo:** Custom board shared; EN UI; switch SNMP device appears offline.  
**Exit:** Lot-1 functional perimeter declared complete pending FS7 proof.

---

## 10. Sprint FS7 — Stabilisation & performance
**Goal:** Prove NFRs before pilot.

| ID | Story | Acceptance criteria | Refs | Who | Pts |
|---|---|---|---|---|---|
| FS7-01 | Load test 128→500 | Sustained load; no data loss; document results | NFR-004, PLT-003 | S | 5 |
| FS7-02 | Latency budgets | Measure collect→UI ≤60 s; detect→notify ≤30 s; page ≤3 s | NFR-001/002/005 | S+J | 3 |
| FS7-03 | 3-OS regression suite | Automated smoke on Win/Linux/macOS agent builds | AGT-001/012 | S | 3 |
| FS7-04 | Backup/restore drill | RPO ≤24 h demonstrated; runbook published | STO-006 | S | 2 |
| FS7-05 | Hardening guides | Agent + platform hardening docs | SEC-008 | S | 2 |
| FS7-06 | Platform self-monitoring | Critical platform components monitored | NFR-010 | J | 2 |

**Demo:** Load report + restore drill in review.  
**Exit:** Go/No-Go for FS8 pilot.

---

## 11. Sprint FS8 — Pilot, extinction, Lot 1 UAT
**Goal:** M4 — Lot 1 accepted; PowerShell scripts decommissioned where covered.

| ID | Story | Acceptance criteria | Refs | Who | Pts |
|---|---|---|---|---|---|
| FS8-01 | Pilot fleet onboarding | UAT family 1 on agreed pilot hosts | Part K | S+J | 3 |
| FS8-02 | Alerting E2E UAT | Family 3 on Mail API + webhook | Part K | S+J | 2 |
| FS8-03 | Resilience UAT | Family 4 pass | Part K | S | 2 |
| FS8-04 | History/reporting UAT | Family 5 pass | Part K | J | 2 |
| FS8-05 | Script extinction | Each DES-004 row → `verified in production` then `script decommissioned`; zero uncovered Must checks | AGT-013/014 | S+CBC | 5 |
| FS8-06 | Lot 1 acceptance pack | Traceability matrix requirement→test→evidence; sign-off | UNIFIED SPEC §15 | S | 3 |

**Demo:** Coverage map at zero open Musts; UAT sign-off meeting.  
**Exit:** **M4 Lot 1 accepted.**

---

## 12. Lot 2 backlog placeholder (FS9+)

Do **not** start before M4 unless explicitly approved.

| Theme | Refs | Notes |
|---|---|---|
| Action plugins + signed tasks | AGT-060–068, SEC-005/007 | Human approval, dry-run, audit — **starter Done (FS9)** |
| **PCI Hygiene action** | AGT-060+ (Lot 2) | **Starter Done:** `pci.hygiene` checklist + score on host (not AoC/ASV). Extend with CBC process lists + evidence export. |
| OIDC SSO + Security role | DSH-025, API-003 | Corporate IdP open point |
| n8n closed-loop pack | N8N-001–007 | 5 starter workflows |
| Noise suppression / correlation | ALR-008/009 | |
| ITSM / Teams / Slack | INT-004/005 | Tool choice open |
| Scale / HA to 5 000 | NFR-003/004 | |

---

## 13. Capacity & sequencing rules

1. **FS0 is mandatory** before FS1 coding of plugins.  
2. **FS3 (logs)** can partially overlap late FS2 if staffing allows; do not start before TSDB decision (FS0-07).  
3. **FS4** depends on FS1 schemas + FS2 metrics (and FS3 for ALR-003).  
4. **Senior-only zones:** FS1-03, FS1-04, FS3-01, FS3-06, FS4-01, FS7-01.  
5. Update DES-004 at **every** sprint review until FS8-05.  
6. CBC blockers (service/file lists, offline threshold, script inventory) escalate within 5 business days if unanswered.

---

## 14. Definition of Done — Sprint

- All committed stories Done or explicitly carried with reason  
- No open Sev-1 defects in sprint scope  
- UNIFIED SPEC status columns updated for touched IDs  
- Demo recorded / notes filed  
- Coverage map (DES-004) committed  

---

## 15. First sprint commitment (FS0) — proposed board

**Committed (priority order):**

1. FS0-01 Freeze contracts  
2. FS0-07 ADR TSDB/log store  
3. FS0-05 PowerShell map workshop + v0 table  
4. FS0-06 Compose + TSDB  
5. FS0-02 / FS0-03 DES dossiers  
6. FS0-09 Simulator  
7. FS0-04 / FS0-08 as capacity allows  

**Owners to name:** Product (CBC), Tech lead (S), Intern (J), Frontend (C).

---

## 16. Change log

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-08-13 | Initial implementation sprint plan from UNIFIED SPEC + remapped Plan v2.1 |

---

*End of PLAN-CBC-IMPL-001 v1.0*
