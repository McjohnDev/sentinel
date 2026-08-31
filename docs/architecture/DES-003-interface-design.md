# DES-003 — Interface design dossier

| Field | Value |
|---|---|
| **Document reference** | DES-003 |
| **Version** | 1.0 — Draft for review |
| **Date** | 13 August 2026 |
| **Status** | Living design dossier (FS0-04) |
| **Owner** | CBC Supervision Platform — UI/UX |
| **Parents** | SPEC-CBC-UNIFIED-001, UI/UX Design Brief v1.0, DES-001, DES-002 |
| **Product name in UI** | Sentinel |

This dossier is the **binding interface specification** for the whole product: Lot 1 (visualisation / collect), Lot 2 (actions / n8n / SSO), and Lot 3 (AI assist, design-now). It extends — does not replace — the UI/UX Design Brief for visual identity, tokens, and CBC branding.

**Reading rule:** Brief wins for colour, type, spacing, and CBC identity. This dossier wins for information architecture, workflows, screen inventory, component behaviour, novice configuration, and n8n.

---

## 1. Design thesis

CBC operators are not observability engineers. The current MVP is a **configuration console** (tabs of thresholds, token lists, free-text services). The target product is an **exploitation workspace**: the operator always knows *what needs attention*, *why*, and *what to do next* — without reading YAML, JSON Schema, or n8n node graphs.

Five principles:

1. **Intent before parameters.** A novice never starts on a plugin form. They start from a CBC-approved *monitoring blueprint* (“Serveur SWIFT”, “Poste d’agence”). Advanced fields exist, one click deeper.
2. **Two clicks to meaning.** From any alert: host health, last metrics, related logs, who was notified, next action. No scavenger hunt across Settings.
3. **One product, one automation brain.** n8n is not a second application in the sidebar. It appears as **Scénarios d’automatisation** (playbooks) with health, last run, and approval. Power users may “Ouvrir dans n8n”.
4. **Inheritance over snowflakes.** Config flows Global → Group → Host. Local overrides are visible, reversible, and versioned.
5. **Banking gravity.** Gold/black CBC identity, French-first with English toggle, immutable audit on every write, no decorative noise.

---

## 2. Users and jobs

| Persona | Primary job | Success looks like |
|---|---|---|
| **Administrateur (DTDSI)** | Enrol fleet, publish config, manage users, integrations | A new host is healthy in < 15 min without SSH to edit files |
| **Opérateur / Exploitant** | Triage alerts, diagnose, ack/resolve | Morning board emptied; every critical has an owner in < 5 min |
| **Consultation (Viewer)** | Read fleet and reports | PDF/CSV without write access |
| **Lot 2 — Sécurité** | Audit trail, action approvals, security logs | Every remote action has who / why / dry-run / result |
| **Novice admin** (same Admin role, low observability literacy) | Configure monitoring without breaking production | Wizard + blueprints; never raw plugin JSON |

Roles remain **Admin / Operator / Viewer** in Lot 1. Lot 2 adds **Security** and OIDC groups. The header **role switcher** is a demo/eval tool only; it MUST be hidden in production builds (`VITE_RBAC_SIMULATOR=false`).

---

## 3. Information architecture

### 3.1 Shell

```
┌─────────────────────────────────────────────────────────────────┐
│ HEADER  CBC Supervision  / breadcrumb     pulse  search  notif  │
│         FR|EN   auto-refresh   profile                          │
├──────────┬──────────────────────────────────────────────────────┤
│ SIDEBAR  │  MAIN (max readable width, not cramped 7xl forever)  │
│ grouped  │                                                      │
│ nav      │  Page header (title, context pills, primary action)  │
│          │  Content                                             │
│ user     │                                                      │
│ footer   │                                                      │
└──────────┴─────────────────────────────────────────────────────────────────┘
 Overlay: Command palette (Ctrl+K / Cmd+K)
 Overlay: Approval drawer (Lot 2)
```

Sidebar is **grouped**, not a flat list of 15 items. Groups collapse; the active item stays visible. Badges only for *actionable* counts (open alerts, pending approvals) — never vanity (“128 agents”).

### 3.2 Navigation map (full product)

| Group (FR) | Item | Route | Lot | Status vs repo |
|---|---|---|---|---|
| Exploiter | Tableau de bord | `/` `/dashboard` | 1 | **Partial** — KPIs exist; not yet a situation room |
| Exploiter | Parc | `/fleet` `/agents` | 1 | **Done** (list) |
| Exploiter | Détail hôte | `/fleet/:id` | 1 | **Partial** — no logs, weak history, no plugins |
| Exploiter | Alertes | `/alerts` | 1 | **Partial** — list/ack; no incident/timeline/duration |
| Exploiter | Journaux | `/logs` | 1 (FS3) | **Missing** |
| Analyser | Tableaux | `/dashboards` | 1 (FS6) | **Missing** (DSH-003) |
| Analyser | Tendances | `/trends` | 1 (FS2/FS6) | **Missing** as dedicated view |
| Analyser | Rapports | `/reports` | 1 (FS6) | **Partial** — CSV only |
| Analyser | Réseau | `/network` | 1 (FS6) | **Missing** (SNMP/ICMP) |
| Automatiser | Scénarios | `/automation` | 2 | **Missing** (n8n playbooks) |
| Automatiser | Approbations | `/approvals` | 2 | **Missing** |
| Automatiser | Actions | `/actions` | 2 | **Missing** (`task.v1`) |
| Configurer | Studio Agent | `/studio` | 1 (FS5) | **Missing** — today’s Settings tabs are the gap |
| Configurer | Règles | `/rules` | 1 (FS4) | **Missing** — instant thresholds only |
| Configurer | Intégrations | `/integrations` | 1–2 | **Partial** — Mail tab only |
| Administrer | Utilisateurs | `/users` | 1 | **Done** |
| Administrer | Audit | `/audit` | 1–2 | **Missing** as UI (API audit exists) |
| Administrer | Paramètres | `/settings` | 1 | **Partial** — flatten; compliance stays |
| — | Connexion | `/login` | 1 | **Done** |
| — | SSO / OIDC | `/login` | 2 | **Missing** |
| — | Profil | `/profile` | 1 | **Missing** (menu link today goes to Users) |
| — | Palette | overlay | 1 | **Missing** |

Aliases: keep `/agents` as redirect to `/fleet` so existing bookmarks work.

### 3.3 Sidebar copy (production)

```
EXPLOITER
  Tableau de bord
  Parc                         [online/total only in header, not here]
  Alertes                      [N ouvertes]
  Journaux

ANALYSER
  Tableaux
  Tendances
  Rapports
  Réseau

AUTOMATISER          ← hidden until Lot 2 flag `automation.enabled`
  Scénarios
  Approbations                 [N en attente]
  Actions

CONFIGURER           ← Admin; Operator sees read-only rules
  Studio Agent
  Règles
  Intégrations                 [channel health dot]

ADMINISTRER          ← Admin (Audit: Admin + Security)
  Utilisateurs
  Audit
  Paramètres
```

Items for unshipped lots are **visible but labelled “Bientôt”** in staging, **hidden** in Lot 1 production so CBC UAT is not confused.

---

## 4. Global components (shell)

### 4.1 Header

| Element | Behaviour |
|---|---|
| Breadcrumb | Group / page / entity (host name, alert id, blueprint name) |
| Fleet pulse | Green = no open critical; amber = warnings; red + pulse = critical. Click → `/alerts?severity=critical` |
| Channel health | Dot for Mail / Webhook / n8n (CBC-INT-01). Click → Intégrations |
| Search | Opens command palette |
| Auto-refresh | 30 s Lot 1 (DSH-008); 5 s live WS Lot 2. Pause must be obvious |
| Language | `FR` / `EN` persist in profile (NFR-008) |
| Notifications | Open alerts, grouped by host; Ack inline for Operator+ |
| Profile | Name, role, Profil, Paramètres, Quitter |

Remove the production **RBAC simulator**. Keep it behind a build flag for evaluators.

### 4.2 Command palette (`Ctrl+K`)

Single search across: hosts, alerts, blueprints, rules, users, playbooks, settings keys.

Suggested actions (role-gated):

- `Acquitter les critiques`
- `Enrôler un agent`
- `Ouvrir le studio — groupe SWIFT`
- `Mettre en maintenance : db-02`
- `Lancer le scénario « Disque critique »` (Lot 2)

Empty query shows **recent** + **suggested for this page**.

### 4.3 Page header pattern

Every page:

1. Title + one-line purpose
2. Context pills (filters that are on)
3. **One** primary action (right)
4. Secondary actions in overflow (`…`)

Never two competing gold buttons.

### 4.4 Status model (visual)

Align platform status **OK / Warning / Critical / Unknown** (PLT-014) with alert severities **Info / Minor / Major / Critical** (ALR-004). UI mapping:

| Platform | Alert | Colour (semantic, not gold) |
|---|---|---|
| OK | — | Emerald |
| Warning | Minor | Amber |
| Critical | Major / Critical | Rose |
| Unknown | — | Slate |
| Info | Info | Slate/blue |

Gold (`#D0B335`) is **brand and focus**, never severity.

---

## 5. Clean workflows

These are the canonical user journeys. Every screen below exists to serve one of them.

### W1 — First host in 15 minutes (Admin)

```
Login → empty Tableau de bord
  → CTA « Enrôler le premier agent »
  → Token (TTL visible) + recettes d’install (Windows MSI / Linux / macOS)
  → Copy one-liner
  → Waiting state: « En écoute du premier heartbeat… »
  → Host appears → Studio propose un modèle selon OS + machine_type
  → Apply blueprint → Done
```

**UI:** dedicated Enrolment sheet (not buried in Settings → Jetons). Token is shown once; copy + download `.env` snippet; never logged in screenshots guidance.

### W2 — Morning exploitation (Operator)

```
Tableau de bord (situation)
  → Queue « À traiter » (critical first, then major, then offline outside window)
  → Open alert
  → Split view: timeline | host snapshot | related logs (when FS3)
  → Ack with comment (mandatory for critical)
  → Optional: « Voir l’hôte » / « Exporter »
  → Resolve when metric recovered or after confirmation
```

**Rule:** Ack is not Resolve. Auto-resolve (ALR-005) shows as « Résolu automatiquement » with the metric that cleared.

### W3 — Guided configuration for a novice (Admin) — *centrepiece*

See §6. Outcome: a versioned config is pushed to a group or host without the user naming a plugin.

### W4 — Change with confidence (Admin)

```
Edit (wizard or expert)
  → Diff (before / after) in plain language + technical
  → Impact preview (« ~3 alertes / jour estimées sur ce groupe »)
  → Confirm → config version N+1
  → Rollout progress (hosts ACK)
  → Rollback one click to N
```

### W5 — Maintenance without noise (Operator/Admin)

```
Règles → Fenêtre de maintenance
  → Select hosts or group + time range + reason
  → Suppress alerts (ALR-007) — distinct from availability windows
  → Banner on host and dashboard: « Maintenance jusqu’à HH:MM »
```

### W6 — Alert to automation (Lot 2)

```
Alert fires → signed webhook (INT-003 / ALR-011)
  → n8n playbook matches
  → If action required: Approbation drawer in CBC Supervision
  → Signed task.v1 to agent (or reject on L0)
  → Result + audit row
  → Operator sees « Scénario exécuté » on the alert timeline
```

### W7 — Report for DPPI (Viewer+)

```
Rapports → modèle « Disponibilité hebdomadaire »
  → Scope (group / all)
  → Schedule or download PDF/CSV
  → Delivery via CBC Mail API
```

---

## 6. Studio Agent — advanced configuration for novices

Today’s Settings dump (seuils, services, fichiers, disponibilité) is replaced by **Studio Agent**. Settings keeps platform-level concerns (retention, compliance, language).

### 6.1 Three modes (same object, three depths)

| Mode | Who | What they see |
|---|---|---|
| **Intention** | Novice, default | CBC blueprints. One card = one intent. Apply to group/host. |
| **Guidé** | Admin learning the estate | 7-step wizard in business language. Generates the same config as Expert. |
| **Expert** | Platform owner | Plugin manifests (`plugin.manifest.v1`), intervals, privileges, YAML preview, JSON Schema forms. |

Toggle is persistent per user. Switching Intention → Expert never loses data; it *reveals* fields.

### 6.2 Blueprints (Modèles CBC)

A blueprint is a versioned, CBC-approved bundle:

- `machine_type` (server | workstation)
- Plugin set + default intervals
- Service and file watch lists (from official CBC lists when provided)
- Thresholds **with duration**
- Availability vs 24×7
- Suggested notification routing
- Labels (`env`, `group`, `site`)

Starter catalogue (editable by Admin, locked items marked « CBC »):

| ID | Name (FR) | Intent in one sentence |
|---|---|---|
| `bp.server.generic` | Serveur métier | CPU/RAM/disk/net/process + OS services; 24×7; duration 5 min |
| `bp.server.swift` | Hôte SWIFT | Generic + SWIFT service/file lists; major on service down; no noisy disk on backup volumes |
| `bp.server.ad` | Contrôleur de domaine | Directory services + replication-oriented process watch |
| `bp.server.files` | Serveur de fichiers | Disk inodes + share paths + large-file growth |
| `bp.ws.branch` | Poste d’agence | Workstation; availability windows; offline only outside window |
| `bp.ws.admin` | Poste admin DSI | Workstation + extra process watch; quieter nights |
| `bp.custom` | Personnalisé | Empty shell; forces Guidé wizard |

Each card shows: OS coverage, plugin count, estimated noisiness (Calme / Standard / Vigilant), last published version.

**Apply flow:** Choose scope (new group / existing group / single host) → preview diff vs current → publish.

### 6.3 Guided wizard (7 steps)

Plain-language questions. Right pane = **live summary** (always visible on desktop).

| Step | Title | Questions | Maps to |
|---|---|---|---|
| 1 | Identité | Confirm hostname, site, env, `machine_type` | Inventory |
| 2 | Métier | “Que fait cette machine ?” chips (SWIFT, Core, Agence, Fichiers, AD, Autre) | Blueprint suggestion |
| 3 | Présence | 24×7 or calendar (week grid). Offline threshold in minutes, not seconds | Availability policy |
| 4 | Collecte | Toggles with *why*: CPU, mémoire, disques, réseau, processus, services, fichiers, journaux | Plugins on/off + interval presets |
| 5 | Critique | Typeahead from **official CBC lists** (services / files). “Ajouter un chemin” is secondary | AGT-026, CBC-AGT-03 |
| 6 | Tolérance | “À partir de quand vous réveiller ?” — Calme / Standard / Vigilant. Shows resulting duration + severity in a sentence | ALR-001 duration rules |
| 7 | Revue | Diff, estimated alert volume, channels that will fire, who inherits | Config version |

**Guardrails (inline, not after save):**

- Warning threshold < critical
- Workstation cannot use 24×7 offline = 60 s (too noisy) without explicit “Je confirme”
- Enabling an **elevated** plugin (Lot 2) requires a privilege explanation
- Log collection warns on volume (“peut générer ~X Mo/j”)

**Forbidden in Guidé:** raw JSON, plugin IDs as the first label, HMAC secrets, n8n URLs.

### 6.4 Expert inspector

- One card per plugin from `plugin.manifest.v1` (name, version, kind, privileges, interval)
- Form generated from `input_schema`
- Capability **L0** vs **L1** badge; L1 disabled until Lot 2 + host allow-list
- Config YAML / JSON preview (read-only) for support tickets
- Version history: who, when, diff, rollback (AGT-008)

### 6.5 Groups and inheritance

```
Global defaults  →  Group (e.g. SWIFT-Douala)  →  Host override
```

UI badges:

- `Hérité · SWIFT-Douala`
- `Surcharge locale` (with “Rétablir l’héritage”)
- `En attente de push` (host has not ACK’d version)

Bulk: select N hosts on Parc → “Appliquer le modèle…” → same preview as Studio.

### 6.6 Impact preview

Optional but specified: using last 24 h of TSDB data, count how many alerts the new rule *would have* opened. Display: “Cette règle aurait ouvert 2 alertes hier (au lieu de 14 avec le seuil instantané).” This is the antidote to instant CPU>90% spam.

---

## 7. Screen specifications

For each screen: purpose, layout, primary action, empty/loading/error, RBAC. Visual tokens stay in the Brief.

### 7.1 Login — `/login` — Lot 1 Done

- CBC mark, gold/black, FR copy
- Email + password; show/hide; forgot-password **must work** (today: modal only)
- Lot 2: “Connexion institutionnelle (SSO)” primary if OIDC configured; local login behind “Compte local”
- No demo password prefill in production
- Error: generic (“Identifiants invalides”) — no user enumeration
- After login: last route or Tableau de bord

### 7.2 Tableau de bord (Situation room) — `/dashboard`

**Purpose:** Answer “what needs me now?” in under 5 seconds.

**Layout (desktop):**

```
[ Pulse strip: fleet % · critical · major · offline hors fenêtre · mail/n8n health ]
[ À traiter — ranked queue, max 8 rows, “Voir tout” ]
[ Load 24h — CPU/RAM/disk area from TSDB ]
[ Mix OS | sites | server vs workstation ]
[ Channel health chips ]
```

**Remove / demote:** pie charts as the hero; enrolment token generation (move to Studio / empty-state CTA).

**Empty fleet:** illustration + W1 CTA, not a blank table.

**RBAC:** all roles read; Admin sees Enroler; Operator sees Ack on queue rows.

### 7.3 Parc — `/fleet`

KPI strip (online / offline / degraded / unknown) + search + filters (OS, site, group, machine_type, status, “a des alertes”, “config en retard”).

Table columns: Status, Name, Hostname, OS, Group, CPU, RAM, Disk, Heartbeat, Alerts, Config version, Actions.

Row click → détail. Actions overflow: Studio, Maintenance, Révoquer (Admin), Export.

**Saved views:** “Agences”, “SWIFT”, “Hors ligne”. Persist per user.

Mobile: cards with status stripe + 3 gauges.

### 7.4 Détail hôte — `/fleet/:id`

Header: name, status, OS, IP, group, machine_type, agent version, last heartbeat, config version vs expected.

Tabs:

| Tab | Lot | Content |
|---|---|---|
| Vue | 1 | Gauges, open alerts, services/files status, availability banner |
| Métriques | 1 | Time range (1h/6h/24h/7j/30j), families from plugins, TSDB charts |
| Journaux | 1 FS3 | Embedded log explorer scoped to host |
| Événements | 1 | OS/agent lifecycle (AGT-027) |
| Alertes | 1 | Host-filtered workbench |
| Configuration | 1 | Embed Studio in Guidé/Expert for this host; inheritance banner |
| Actions | 2 | Dry-run + execute allow-listed plugins; hidden on L0 |
| Audit | 1–2 | Config pushes, acks, tasks |

Danger zone (Admin): Révoquer, Supprimer — two-step typed confirm (hostname).

### 7.5 Alertes — `/alerts` + drawer `/alerts/:id`

**List:** filters severity, status (open/ack/resolved), type/family, group, time. Bulk ack (Operator+: not Viewer). Export CSV/PDF.

**Drawer / page (missing today):**

- Lifecycle stepper: Ouverte → Acquittée → Résolue
- Timeline: detect, notify (Mail/webhook/n8n), ack, comments, auto-resolve
- Correlated events (PLT-012) when available
- Actions: Ack, Escalader, Créer un ticket ITSM (Lot 2), Lancer un scénario (Lot 2), Voir l’hôte

Duration rules show: “CPU > 90 % **depuis 5 min**” not a single spike.

### 7.6 Journaux — `/logs` — Lot 1 FS3

Loki-backed explorer: query bar, time range, host/group facets, histogram, stream. Deep-link from alert (`?q=...&host=`). Rate-limit warning if query too broad. Viewer can read; no delete.

### 7.7 Tableaux personnalisés — `/dashboards` — DSH-003

Grid of widgets (KPI, timeseries, top-N hosts, alert list, gauge). Add widget → pick metric family + hosts/group. Share with role. Default “Exploitation” dashboard is system-owned and not deletable.

### 7.8 Tendances — `/trends`

Capacity: disk fill ETA, CPU p95 by group, offline minutes by site. Feeds reports.

### 7.9 Rapports — `/reports`

Templates: disponibilité, top alertes, conformité config, inventaire. On-demand + schedule (Mail API). Viewer: download if granted; Admin: schedule.

### 7.10 Réseau — `/network`

SNMP/ICMP inventory: name, IP, status, last ping, sysDescr. Device detail: interface table, ICMP loss. No agent install CTA (these are not hosts).

### 7.11 Studio Agent — `/studio` — see §6

Sub-routes: `/studio/blueprints`, `/studio/groups`, `/studio/wizard`, `/studio/plugins`.

### 7.12 Règles — `/rules`

- Threshold + **duration** (ALR-001)
- Heartbeat / availability (ALR-002) — already exists, relocate from Settings
- Log pattern (ALR-003)
- Maintenance windows (ALR-007) — **not** the same as availability
- Routing: channels, recipients, schedules, escalation (ALR-006)
- Noise (Lot 2): dedup, flap, rate limit

Rule editor: condition builder (metric, op, value, for duration) + “en français” preview sentence. Test against last 24 h (same as impact preview).

### 7.13 Intégrations — `/integrations`

Cards per channel with **health** (OK / Degraded / Error / Disabled):

| Channel | Lot | Actions |
|---|---|---|
| CBC Mail API | 1 | Endpoint, key (write-only), recipients, Test, last delivery |
| Webhook HMAC | 1 FS4 | URL, secret rotation, event types, last 10 deliveries |
| SMS | 1 | Provider when chosen |
| n8n | 2 | See §8 |
| ITSM | 2 | GLPI / Jira / ServiceNow mapping |
| Slack / Teams | 2 | Workspace, channel, mention policy |

Never show full API keys after save — last 4 chars + rotate.

### 7.14 Scénarios (n8n) — `/automation` — Lot 2, §8

### 7.15 Approbations — `/approvals` — Lot 2

Queue of `task.v1` requiring `approval_ref`. Diff of dry-run vs requested. Approve / Deny with comment. SEC-005 chain visible.

### 7.16 Actions — `/actions` — Lot 2

Pick host → plugin (service.manage, command, …) → form from manifest → **Dry-run default ON** → submit. Poll task id. Stream result. Audit mandatory.

### 7.17 Utilisateurs — `/users` — Done, extend Lot 2

Add SSO-linked identity, Security role, last login, deactivate vs delete. Self-service password on `/profile`.

### 7.18 Audit — `/audit`

Immutable table: actor, action, target, before/after (collapsed), IP, timestamp. Filters. Export for COBAC. Security role sees security-class logs (SEC-006).

### 7.19 Paramètres — `/settings`

**Only** platform-wide: retention, language default, session timeout, compliance dossier, feature flags (automation, AI). Enrolment tokens move to Studio. Thresholds move to Règles / Studio.

### 7.20 Profil — `/profile`

Name (read-only if SSO), password (local), language, notification personal email (if allowed), active sessions.

---

## 8. n8n connection — product UX (not a second IDE)

n8n stays self-hosted. CBC Supervision is the **control plane** operators live in. n8n is the **workflow engine**.

### 8.1 Connection (N8N-001)

Integrations → card **n8n**

| Field | Notes |
|---|---|
| Base URL | `https://n8n.cbc.internal` |
| Auth | Scoped API key (write-only) **or** mTLS later |
| Inbound webhook | Platform URL `/api/webhooks/n8n` + HMAC secret (INT-003) |
| Outbound events | `alert.opened`, `alert.acknowledged`, `alert.resolved`, `agent.offline`, `config.published` |
| Status | Last successful ping, last event delivered, last workflow error |
| Test | “Envoyer un événement fictif” (does not page humans; uses `dry_run: true`) |

Disconnected state: playbooks list is visible but **Lancer** disabled; banner “n8n injoignable”.

### 8.2 Playbooks in Supervision (N8N-003, N8N-004)

Each playbook is a row:

- Name, description, trigger, required approval (yes/no), last run, success rate 7d, enabled toggle
- **Ouvrir dans n8n** (new tab) — Admin only
- **Lancer** (manual) — Operator+ if playbook allows
- **Runs** — last 20 executions

Supervision does **not** embed the n8n node canvas. Editing graphs is n8n’s job. Supervision owns: enablement, trigger mapping, approval, audit, human copy.

### 8.3 Starter pack (five workflows)

| # | Name (FR) | Trigger | What n8n does | Human gate |
|---|---|---|---|---|
| 1 | Disque critique → mail + ticket | `alert.opened` disk critical | Mail API + create ITSM ticket | No |
| 2 | Service SWIFT arrêté | service_down on SWIFT list | Escalate (second channel); Lot 2: propose restart | **Yes** for restart |
| 3 | Hors ligne hors fenêtre | agent.offline ∧ outside availability | Mail + SMS | No |
| 4 | CPU durable | CPU > threshold for duration | Correlate host; suppress flap duplicates | No |
| 5 | Nouvel agent enrôlé | enrolment complete | Mail inventaire + suggest blueprint | No |

UAT Lot 2 requires these five demonstrable (unified spec Part K).

### 8.4 Closed loop (N8N-005–007)

```
metric/event → rules → alert.v1
        → HMAC webhook → n8n
        → (optional) POST /api/approvals
        → operator approves in drawer
        → platform signs task.v1
        → agent executes or L0 rejects
        → task.result.v1 → n8n + UI timeline + audit
```

**Approval drawer:** host, plugin, input summary, dry-run output, expiry, Approve/Deny. If the operator is the requester, four-eyes MAY be required (config flag) for `command_exec` / `elevated`.

**Run history** is first-class: never “look in n8n to know if it worked”.

### 8.5 What we never do in UI

- Store n8n credentials in localStorage
- Let Viewer enable playbooks
- Fire production Mail from the Test button without a `[TEST]` prefix and a dedicated recipient
- Bypass SEC-005 by “quick restart” on the host page without audit

---

## 9. Component system (product, not only atoms)

Atoms already in repo: `Badge`, `Modal`, `ProgressBar`, `GaugeChart`, `EmptyState`, `SkeletonLoader`, `Toast`, `AcknowledgeModal`, `Header`, `Sidebar`.

### 9.1 New / specified components

| Component | Role | Notes |
|---|---|---|
| `CommandPalette` | Global search + actions | Ctrl+K |
| `PageHeader` | Title, pills, primary action | Mandatory on every view |
| `PulseStrip` | Fleet + severity + channel dots | Dashboard + header compact |
| `StatusDot` | OK/Warn/Crit/Unknown | Never gold |
| `InheritanceBadge` | Hérité / Surcharge / Push pending | Studio + host |
| `BlueprintCard` | Intent catalogue | Noisiness + OS + plugin count |
| `WizardStepper` | 7-step Guidé | Persistent summary pane |
| `PlainLanguagePreview` | Rule/config as a French sentence | Rules + wizard step 6–7 |
| `ConfigDiff` | Version N vs N+1 | Side-by-side + rollback |
| `ImpactPreview` | “Would have fired N times” | TSDB-backed |
| `TimeRangePicker` | 1h–30j + custom | Metrics, logs, trends |
| `LogStream` | Loki results | Virtualised |
| `ChannelCard` | Integration health | Test + last delivery |
| `PlaybookRow` | n8n scenario | Enable, runs, open n8n |
| `ApprovalDrawer` | Lot 2 four-eyes | Dry-run + comment |
| `DryRunPreview` | task.v1 dry_run | Actions |
| `MaintenanceBanner` | Host/dashboard | Distinct from availability |
| `EnrolmentSheet` | Token + OS recipes | W1 |
| `DurationInput` | “pendant X min” | ALR-001 |
| `OfficialListPicker` | CBC services/files typeahead | Not free-text first |
| `SavedViews` | Parc / alerts | Per user |
| `RoleGate` | Hide/disable by RBAC | Tooltip “Réservé Admin” |
| `FeatureFlag` | Hide Lot 2 nav | `automation.enabled` |

### 9.2 Behaviour rules

- **Destructive:** typed confirm (hostname / email), never checkbox-only
- **Toasts:** success 4 s; errors sticky until dismiss; include next action
- **Forms:** save is explicit; unsaved barrier on navigate
- **Tables:** sticky header, keyboard row focus, empty vs filtered-empty copy
- **Loading:** skeletons matching layout, not a centred spinner for pages with structure
- **Live data:** values that move (CPU) use tabular nums; no layout jump

### 9.3 Existing atoms — keep, restyle only if Brief conflicts

Do not rewrite `GaugeChart` / `Badge` unless contrast fails WCAG. Align Badge severity with ALR-004 four levels when FS4 lands (`minor` / `major` vs today’s `warning`).

---

## 10. RBAC matrix (UI)

| Capability | Viewer | Operator | Admin | Security (L2) |
|---|---|---|---|---|
| Dashboard, fleet, alerts, logs, trends | R | R | R | R |
| Ack / resolve alerts | — | RW | RW | R |
| Bulk ack | — | RW | RW | — |
| Export CSV/PDF | — | RW | RW | RW |
| Enrolment tokens | — | — | RW | — |
| Studio / groups / blueprints / push | — | R | RW | R |
| Rules, maintenance | — | R (maintenance RW) | RW | R |
| Integrations secrets | — | — | RW | R |
| Users | — | — | RW | R |
| Audit | — | — | R | RW |
| Playbooks enable | — | R | RW | R |
| Playbooks run (allowed ones) | — | RW | RW | — |
| Approve tasks | — | RW* | RW | RW |
| Execute actions | — | RW* allow-list | RW | — |
| SSO / flags | — | — | RW | — |

\*Operator action/approval scope is allow-listed per plugin (no `command_exec` by default).

Disabled controls stay **visible** with a tooltip (discoverability) except secrets and Lot 2 nav in Lot 1 production.

---

## 11. Content, i18n, accessibility

- **Default language:** French. Every string through i18n keys (`fr`, `en`). No hardcoded mixed language.
- **Tone:** vous, short sentences, no slang, no emoji in chrome (Brief already forbids flashy UI).
- **Time:** Europe/Douala displayed; store UTC. Relative + absolute on hover.
- **A11y:** contrast ≥ 4.5:1; focus rings gold; skip link; palette and modals focus-trap; charts have text alternative (table or summary).
- **Responsive:** sidebar drawer < `lg`; situation room stacks; wizard summary becomes accordion on mobile.
- **NFR-005:** first contentful paint of shell ≤ 3 s on CBC LAN; route-level code split for Logs, n8n, dashboards.

---

## 12. Mapping to delivery

| UI slice | Sprint | Spec IDs |
|---|---|---|
| Situation room + palette + page header | FS2–FS4 | DSH-001, DSH-008 |
| Host metrics from TSDB + time range | FS2 | DSH-002, DSH-006, STO-001 |
| Studio Intention + Guidé + groups | FS5 | AGT-008, CBC-AGT-* |
| Expert plugins from manifests | FS1/FS5 | AGT-002 |
| Rules + duration + maintenance | FS4 | ALR-001, ALR-007 |
| Intégrations + HMAC + channel health | FS4 | INT-003, CBC-INT-01 |
| Logs explorer | FS3 | AGT-025–038, STO-003 |
| Custom dashboards + PDF reports + i18n | FS6 | DSH-003, DSH-007, NFR-008 |
| Network | FS6 | AGT-029 |
| n8n playbooks + approval + actions | FS9+ | N8N-001–007, AGT-060+, SEC-005 |
| SSO + Security role | FS9+ | DSH-025, API-003 |
| AI assist panel | Lot 3 | AGT-080–084 |

**N8N requirement IDs** (were referenced, not listed in the unified spec):

| ID | Requirement |
|---|---|
| N8N-001 | Connection object in UI + health ping |
| N8N-002 | Signed alert events to n8n (ALR-011) |
| N8N-003 | Playbook catalogue (enable, last run, open n8n) |
| N8N-004 | Five starter workflows |
| N8N-005 | Approval drawer before `task.v1` |
| N8N-006 | Run history in Supervision + audit |
| N8N-007 | Failure visible (n8n down, HMAC fail, agent reject) |

---

## 13. Explicit non-goals (UI)

- Embedding Grafana / n8n canvases as the main UI
- Per-host YAML editors as the default admin path
- Dark theme in Lot 1 (shell is light content + dark sidebar as today)
- Mobile-native app
- AI chat as a replacement for ack/resolve (Lot 3 assist only)

---

## 14. Acceptance (design)

Lot 1 UI exit (with FS8):

1. A new Admin who has never seen the product can enrol a host and apply `bp.ws.branch` or `bp.server.generic` without documentation beyond in-app copy (hallway test).
2. An Operator can ack a critical alert and reach host metrics + (if FS3) related logs in ≤ 2 clicks.
3. No production screen requires editing JSON to monitor CPU/RAM/disk/services/files.
4. Channel health is visible on the dashboard (already R11).
5. FR/EN switch covers all chrome strings.
6. Role switcher absent in production build.

Lot 2 UI exit:

7. The five starter playbooks are operable from `/automation` without opening n8n.
8. A restart-style action cannot execute without approval UI + audit row.
9. n8n outage is a first-class degraded state, not a silent miss.

---

## 15. Open UX points

| # | Point | Default until CBC decides |
|---|---|---|
| UX-1 | Official SWIFT service/file labels for pickers | Technical names + “libellé CBC à fournir” |
| UX-2 | Four-eyes for all Lot 2 actions vs only elevated | Only `command_exec` / `elevated` |
| UX-3 | Whether Viewer may download PDF | Yes (DSH-007 Should) |
| UX-4 | Keep `/agents` path forever | Redirect 12 months |
| UX-5 | Dark theme | Not Lot 1 |

---

## 16. Document control

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-08-13 | First full IA, workflows, Studio Agent (novice), n8n playbooks, component inventory, screen map vs repo |

**Companions:**

- `docs/architecture/DES-003-MOCKUP-BRIEF.md` — **handoff for Claude/Figma mockups** (self-contained: tokens, shell, wireframes, French copy, fake data). Also copied under `DOCUMENTS/`.
- `docs/UI-UX-Design-Brief.md` — visual identity (gold/black CBC).

---

*End of DES-003 v1.0*
