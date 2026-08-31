# DES-003-MOCKUP — Handoff for high-fidelity mockups

| Field | Value |
|---|---|
| **Give this file to** | Claude (or any UI model) — **this file alone is enough** |
| **Parent** | DES-003 Interface design dossier |
| **Product** | CBC Supervision — Commercial Bank Cameroun |
| **Language on screen** | **French only** (a `FR \| EN` toggle exists but all mock copy is FR) |
| **Viewport** | Desktop **1440×900** first; also one mobile (390) for login + dashboard |
| **Date** | 13 August 2026 |

---

## Prompt to paste (start of the conversation)

```
You are a senior product designer + frontend implementer.
Build a HIGH-FIDELITY, interactive UI mockup of “CBC Supervision”
(Commercial Bank Cameroun IT supervision platform) from THIS document only.

Deliverable: a single React + Vite + Tailwind app (or one HTML file with
Tailwind CDN) with a left screen-switcher OR real routes. Static fake data.
No backend. No placeholder “lorem ipsum”. No generic blue SaaS theme.

Follow every layout, colour, French label, and constraint below.
If something is unspecified, stay sober, banking, CBC gold/black — never invent
a second product, never embed an n8n node canvas, never use emoji in the chrome.

Priority order of screens is in §0. Produce ALL of them, even unimplemented ones.
```

---

## 0. What to produce (priority)

Build **all** screens. If time-boxed, ship P0 then P1 then P2 — but the request is the **full product**.

| P | Screen | Why |
|---|---|---|
| P0 | Login | First impression |
| P0 | App shell (sidebar + header) reused everywhere | Frame |
| P0 | Tableau de bord (situation room) | Home |
| P0 | Studio Agent — Intention (blueprints) | Novice config — the innovation |
| P0 | Studio Agent — Guidé (wizard step 6+7 visible; stepper complete) | Novice config |
| P0 | Alerte — liste + tiroir détail | Daily ops |
| P1 | Parc (liste hôtes) | Fleet |
| P1 | Détail hôte (onglet Vue + onglet Configuration) | Diagnose |
| P1 | Enrôlement (sheet / modal) | Empty-state CTA |
| P1 | Intégrations (cartes Mail + webhook + n8n) | Channels |
| P1 | Scénarios n8n | Automation without n8n IDE |
| P1 | Tiroir d’approbation | Lot 2 human gate |
| P1 | Palette de commandes (Ctrl+K overlay) | Shell |
| P2 | Journaux | FS3 |
| P2 | Règles (durée + phrase en français) | FS4 |
| P2 | Tableaux personnalisés | DSH-003 |
| P2 | Rapports | PDF schedule |
| P2 | Réseau | SNMP |
| P2 | Utilisateurs, Audit, Paramètres (slim), Profil | Admin |
| P2 | Actions à distance + dry-run | Lot 2 |

Include a **screen index** in the mock (top or a “Galerie” page) so reviewers click every screen.

---

## 1. Design thesis (do not violate)

CBC operators are **not** observability engineers.

1. **Intent before parameters.** Novices start on blueprint cards (“Hôte SWIFT”), not plugin JSON.
2. **Two clicks to meaning.** Alert → host + timeline + next action.
3. **n8n is playbooks**, not a second app. No node graph in this product.
4. **Inheritance:** Global → Groupe → Hôte. Badges `Hérité` / `Surcharge locale`.
5. **Banking gravity.** Gold/black CBC, French, no startup flash, no gradients on text, no rainbow charts.

---

## 2. Visual tokens (CBC — mandatory)

### Colour

| Token | Hex | Use |
|---|---|---|
| Or CBC (primary) | `#D0B335` | Primary buttons, active nav icon, focus ring, key accents |
| Or hover | `#B89C2C` | Primary hover |
| Or active | `#A68523` | Primary pressed |
| Or tint | `rgba(208,179,53,0.10)` | Selected rows, soft chips |
| Or border | `rgba(208,179,53,0.30)` | Focus / active card |
| Noir | `#000000` / `#0F172A` | Titles, primary text (use slate-900 in UI) |
| Gris CBC | `#777777` | Secondary text, placeholders |
| Sidebar | `#020617` (slate-950) | Left nav background |
| Sidebar border | `#1E293B` | |
| Content bg | `#F1F5F9` (slate-100) | Main canvas |
| Surface | `#FFFFFF` | Cards, header, tables |
| Stroke | `#E2E8F0` | Card/table borders |
| OK / online | `#059669` emerald-600 | Status only |
| Warning / minor | `#D97706` amber-600 | Status only |
| Critical / major | `#E11D48` rose-600 | Status only |
| Info | `#2563EB` blue-600 | Info badges only |

**Gold is brand, NEVER severity.** Do not colour CPU gauges gold when they are in alarm — use emerald/amber/rose.

**No:** purple, cyan neon, dark-mode content area, mesh gradients, glassmorphism, emoji icons in nav.

### Type

- UI: system / `Inter` / `Segoe UI`, 12–14 px body, 11 px meta, 18–20 px page title, 24 px max.
- Tabular numbers for CPU/RAM/disk (`font-variant-numeric: tabular-nums`).
- Page titles: slate-900 extrabold. Labels: 11 px uppercase tracking on sidebar groups only.

### Shape & space

- Radius: 8 px controls, 12 px cards, 16 px modals.
- Sidebar width: **250 px**.
- Header height: **64 px**.
- Main padding: 24–32 px. Content max-width: **1280 px** (not a skinny 768 column).
- Shadow: **none or 1 very light** (`shadow-sm`). Flat banking UI.
- Icons: Lucide, 16 px, currentColor. Active nav icon = Or CBC.

### Buttons

| Kind | Style |
|---|---|
| Primary | bg `#D0B335` text slate-950 font-semibold; hover `#B89C2C` |
| Secondary | white, border slate-200, text slate-800 |
| Ghost | transparent, text slate-600 |
| Danger | rose-600 text white |
| Disabled | 50% opacity, no pointer |

**One gold primary per page**, top-right in the page header.

---

## 3. App shell (every authenticated screen)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ HEADER 64px  bg-white  border-b                                         │
│  [≡ mobile]  CBC Supervision  /  Exploiter  /  Tableau de bord          │
│                         [● 2 critiques]  [Mail OK]  [🔍]  [30s Auto]    │
│                         [FR|EN]  [🔔 5]  [avatar J. Mbida  Admin ▾]     │
├────────────┬─────────────────────────────────────────────────────────────┤
│ SIDEBAR    │  PAGE HEADER                                                │
│ 250px      │  Title (left)                    [primary action]           │
│ slate-950  │  one-line purpose                                           │
│            │─────────────────────────────────────────────────────────────│
│ CBC mark   │  MAIN                                                       │
│ CBC        │                                                             │
│ Supervision│                                                             │
│ ISO 27001  │                                                             │
│            │                                                             │
│ EXPLOITER  │                                                             │
│  Tableau…  │                                                             │
│  Parc      │                                                             │
│  Alertes 5 │                                                             │
│  Journaux  │                                                             │
│            │                                                             │
│ ANALYSER   │                                                             │
│  Tableaux  │                                                             │
│  Tendances │                                                             │
│  Rapports  │                                                             │
│  Réseau    │                                                             │
│            │                                                             │
│ AUTOMATISER│                                                             │
│  Scénarios │                                                             │
│  Approb. 1 │                                                             │
│  Actions   │                                                             │
│            │                                                             │
│ CONFIGURER │                                                             │
│  Studio    │                                                             │
│  Règles    │                                                             │
│  Intégr. ● │                                                             │
│            │                                                             │
│ ADMINISTRER│                                                             │
│  Utilisat. │                                                             │
│  Audit     │                                                             │
│  Paramètres│                                                             │
│            │                                                             │
│ ─────────  │                                                             │
│  J  Jean   │                                                             │
│  P. Mbida  │                                                             │
│  Admin     │                                                             │
│  Quitter   │                                                             │
└────────────┴─────────────────────────────────────────────────────────────┘
 Overlay: Command palette   Overlay: Enrolment sheet   Overlay: Approval drawer
```

### Sidebar rules

- Groups are 10 px uppercase, slate-500, tracking-widest.
- Item: 12 px semibold, rounded-xl, py-2.5 px-3.
- **Active:** text white, icon gold, subtle border slate-700 — not a gold filled bar.
- Badges **only** for actionable counts: Alertes `5`, Approbations `1`. Not “128 agents”.
- Intégrations: small health dot (emerald / amber / rose) after the label.
- Footer: avatar gold-tint, name, email `jp.mbida@cbcam.cm`, role, Quitter.

### Header rules

- Breadcrumb: `CBC Supervision / Exploiter / Tableau de bord`
- Pulse pill: if critical > 0 → rose “2 alertes critiques”; else emerald “Système opérationnel”
- Channel dots: Mail, Webhook, n8n — click goes to Intégrations
- Search icon opens palette
- Auto-refresh: segmented `30s Auto` | Pause
- **Do not** include a “tester les rôles” dropdown (production mock = real Admin session)
- Notifications bell with count; dropdown lists open alerts

### Page header pattern

```
Tableau de bord                              [ Enrôler un agent ]
Ce qui demande une action maintenant.
```

---

## 4. Fake data (use exactly — Cameroon / CBC)

**User:** Jean-Pierre Mbida · `jp.mbida@cbcam.cm` · Administrateur

**Hosts:**

| Name | Host | OS | Site | Group | Type | Status | CPU | RAM | Disk |
|---|---|---|---|---|---|---|---|---|---|
| SWIFT-01 | swift-01.douala.cbc.cm | Linux | Douala HQ | SWIFT | server | online | 41% | 62% | 71% |
| SWIFT-02 | swift-02.douala.cbc.cm | Linux | Douala HQ | SWIFT | server | warning | 91% | 77% | 68% |
| DC-YDE-01 | dc-01.yaounde.cbc.cm | Windows Server | Yaoundé | AD | server | online | 22% | 48% | 55% |
| FS-DLA-01 | files-01.douala.cbc.cm | Windows Server | Douala HQ | Fichiers | server | online | 18% | 54% | 88% |
| WS-BAF-14 | ws-14.bafoussam.cbc.cm | Windows 11 | Bafoussam | Agences | workstation | offline | — | — | — |
| MAC-DSI-03 | mac-03.dsi.cbc.cm | macOS | Douala HQ | DSI | workstation | online | 12% | 61% | 40% |

**Open alerts (5):**

1. Critique · CPU · SWIFT-02 · `CPU > 90 % depuis 6 min` · 08:12
2. Majeure · Disque · FS-DLA-01 · `Disque E: 88 % depuis 15 min` · 07:58
3. Majeure · Hors ligne · WS-BAF-14 · `Hors ligne hors fenêtre de présence` · 07:40
4. Mineure · RAM · SWIFT-01 · `Mémoire 85 % pendant 5 min` · 07:21
5. Info · Service · DC-YDE-01 · `Service Spooler arrêté (non critique)` · 06:55

**Blueprints:** Serveur métier · Hôte SWIFT · Contrôleur de domaine · Serveur de fichiers · Poste d’agence · Poste admin DSI

**n8n playbooks:** see §12.

---

## 5. Screen-by-screen wireframes

### 5.1 Login `/login` — no shell

Full viewport slate-950. Subtle **dot grid** in Or CBC at **10% opacity** (not a loud gradient).

Centered card (max 420 px), white, rounded-2xl:

- CBC wordmark (black + gold “Bank” if logo text; or gold square “CBC”)
- Title: `CBC Supervision`
- Sub: `Plateforme de supervision — Commercial Bank Cameroun`
- Email, Mot de passe (toggle œil), `Se connecter` (gold, full width)
- `Mot de passe oublié ?`
- Footer: `Connexion institutionnelle (SSO)` as secondary button (Lot 2, visible but can show “Bientôt” chip)
- Legal line: `Usage interne CBC · ISO 27001 & COBAC`

**Do not** prefill demo passwords. Empty fields. Error state: `Identifiants invalides` under the button, rose.

### 5.2 Tableau de bord `/dashboard` — P0

**Empty-fleet variant** (toggle in galerie): illustration, title `Aucun agent enrôlé`, CTA gold `Enrôler le premier agent`.

**Populated (default):**

```
Pulse strip (4–5 compact stats, NOT giant gradient KPI cards):
  Parc 5/6 en ligne   |  2 critiques  |  1 hors fenêtre  |  Mail OK · n8n OK

À traiter                          Voir toutes les alertes →
┌─────┬────────────┬─────────────────────────────┬────────┬────────┐
│ CRIT│ SWIFT-02   │ CPU > 90 % depuis 6 min     │ 08:12  │ Acquit.│
│ MAJ │ FS-DLA-01  │ Disque E: 88 % depuis 15 min│ 07:58  │ Acquit.│
│ MAJ │ WS-BAF-14  │ Hors ligne hors fenêtre     │ 07:40  │ Voir   │
└─────┴────────────┴─────────────────────────────┴────────┴────────┘

[ Area chart 24h  CPU / RAM / Disque  — gold line for CPU, slate for others ]
[ Mix: OS donut SMALL + sites list Douala 4 · Yaoundé 1 · Bafoussam 1 ]

Channel chips: Mail OK · Webhook OK · n8n OK
```

Ranking in “À traiter”: critical → major → offline-outside-window. Max 8 rows.

**Do not** make pie charts the hero. **Do not** put “Générer un jeton” as the main dashboard action — that is Enrôler.

### 5.3 Parc `/fleet`

Page header: `Parc` / `Hôtes supervisés` · primary `Enrôler un agent` · secondary `Exporter CSV`

Filter bar: search, OS, site, groupe, type (serveur/poste), statut, “A des alertes”, saved views chips `SWIFT` `Agences`

Table columns: Statut · Nom · Hostname · OS · Groupe · CPU · RAM · Disque · Heartbeat · Alertes · Config · ⋯

- Status dot + label (`En ligne` / `Attention` / `Hors ligne`)
- Config column: `v12` or badge `Push en attente`
- Row SWIFT-02 has amber/rose tint on CPU cell 91%
- Click row → détail. Overflow: Studio, Maintenance, Révoquer

### 5.4 Détail hôte `/fleet/swift-02`

Header block:

```
← Parc
SWIFT-02                    [Attention]  Linux  ·  Serveur  ·  Groupe SWIFT
swift-02.douala.cbc.cm  ·  10.12.4.22  ·  Agent v1.2.0  ·  Heartbeat 12 s
Config v11  ·  attendu v12  [Push en attente]     [Ouvrir dans Studio]
```

Tabs: `Vue` `Métriques` `Journaux` `Événements` `Alertes` `Configuration` `Actions` `Audit`

**Onglet Vue (default):** 3 gauges CPU/RAM/Disk · services list (swift-gateway Running, sshd Running) · files watched · open alerts · availability `24×7`

**Onglet Configuration:** inheritance banner `Hérité · SWIFT-Douala` + `Surcharge locale` on CPU duration · embed Guidé summary · `Rétablir l’héritage`

**Onglet Actions (Lot 2):** dry-run toggle ON by default · plugin `service.manage` · disabled looking with note `Hôte L0 — les actions sont rejetées` OR enabled mock for SWIFT-02 as L1 demo — pick **one** and label it. Prefer: show the form + banner `Lot 2 — aperçu`.

Danger zone at bottom of Configuration: Révoquer / Supprimer (not in the header).

### 5.5 Alertes `/alerts` + drawer

List like a workbench. Filters: gravité, statut, famille, groupe, période.

Columns: Gravité · Statut · Hôte · Message (include **durée**) · Détectée · Notifications (mail icon) · Actions

Primary: none gold on this page except maybe none — Operator action is **Acquitter** per row (secondary) and `Tout acquitter` as secondary, not gold.

**Drawer (right, 480 px)** when a row is clicked:

```
Alerte ALT-1042
CPU > 90 % depuis 6 min
SWIFT-02

Stepper: Ouverte ●  Acquittée ○  Résolue ○

Timeline:
  08:06  Détecté (durée atteinte)
  08:06  Mail CBC → dsi-ops@cbcam.cm  OK
  08:06  Webhook n8n  OK
  08:07  Scénario « CPU durable » démarré

[Acquitter]  [Voir l’hôte]  [Lancer un scénario ▾]
```

Ack modal: comment **required** for Critique.

### 5.6 Studio Agent — Intention `/studio` — P0  ★

This is the **hero innovation screen**. Spend visual quality here.

Page header: `Studio Agent` / `Configurer la supervision sans YAML`  
Toggle right: `[ Intention | Guidé | Expert ]` — Intention selected (gold underline or gold chip).

Sub-nav: `Modèles` `Groupes` `Plugins`

**Modèles grid (3 columns):**

Each `BlueprintCard`:

```
┌─────────────────────────────────┐
│ Hôte SWIFT              CBC     │
│ Linux · 8 plugins               │
│ Services et fichiers officiels. │
│ Service arrêté = majeur.        │
│ Bruit : Vigilant                │
│                         [Appliquer] │
└─────────────────────────────────┘
```

Cards: Serveur métier (Standard) · Hôte SWIFT (Vigilant, badge CBC) · Contrôleur de domaine · Serveur de fichiers · Poste d’agence (Calme) · Poste admin DSI · `+ Personnalisé` dashed.

**Apply modal:**

- Scope: ○ Nouveau groupe  ● Groupe existant [SWIFT-Douala ▾]  ○ Hôte seul
- Preview 4 lines in French: “CPU > 90 % pendant 5 min → Majeure, mail DSI”
- Buttons: Annuler · `Publier v13` (gold)

Right or below: **Groupes** mini-list `SWIFT-Douala (2 hôtes)` `Agences (1)` with inheritance caption.

### 5.7 Studio Agent — Guidé `/studio/wizard` — P0 ★

Left: vertical stepper 1–7. Current = **6 Tolérance** (show this step in the mock; stepper all visible).

```
1 Identité ✓
2 Métier ✓
3 Présence ✓
4 Collecte ✓
5 Critique ✓
6 Tolérance  ← current
7 Revue
```

Center (step 6):

Title: `À partir de quand vous réveiller ?`  
Three large selectable cards (not radio in a form dump):

- **Calme** — “J’accepte plus de délai, moins de bruit” · 15 min
- **Standard** (selected) — “Équilibre exploitation CBC” · 5 min
- **Vigilant** — “SWIFT / critique métier” · 2 min

Sentence preview (always visible, gold-tint box):

> Si le CPU dépasse **90 % pendant 5 minutes**, une alerte **majeure** part vers **Mail DSI** et le scénario **CPU durable**.

Right pane (sticky, 320 px): live summary of steps 1–5 (SWIFT-02, serveur, 24×7, plugins on, services swift-gateway…).

Footer: `Retour` · `Continuer vers la revue`

**Step 7 Revue** (second state in galerie): `ConfigDiff` two columns + `ImpactPreview`: `Cette règle aurait ouvert 2 alertes hier (au lieu de 14 avec un seuil instantané).` · `Publier v13`

**Forbidden on Guidé:** JSON, plugin ids as first label, HMAC secrets, n8n URLs.

### 5.8 Studio Expert `/studio/plugins`

Grid of plugin cards from manifests: `cpu` `memory` `disk` `network` `process` `services` `files` `logs`  
Each: version, interval 60s, privilege `none`, toggle, L0 badge. L1 `service.manage` greyed `Lot 2`.  
YAML preview drawer optional.

### 5.9 Enrôlement (sheet)

Triggered from empty dashboard or Parc CTA. Modal 640 px:

1. Jeton `cbc_enr_7K9Q…` (copy) · expire `dans 24 h` · shown **once** banner
2. OS tabs: Windows · Linux · macOS
3. One-liner in `<code>` block + Copier
4. Live: `En écoute du premier heartbeat…` with a subtle pulse dot

Windows example command (display only):

`msiexec /i CBCAgent.msi /qn ENROLL_TOKEN=… PLATFORM_URL=https://supervision.cbc.cm`

### 5.10 Règles `/rules`

Two columns: list of rules | editor.

Rule list: `CPU haute durée` `RAM` `Disque` `Heartbeat` `Hors fenêtre` `Maintenance`

Editor:

- Metric `cpu.total.utilization`  op `>`  value `90`  **pendant** `[ 5 ] min`
- Sévérité Majeure
- Cible: groupe SWIFT
- **PlainLanguagePreview** sentence at top of editor
- Test 24 h: `2 déclenchements hier`
- Fenêtres de maintenance: calendar strip — caption `Distinct des fenêtres de présence`

### 5.11 Intégrations `/integrations`

Cards 2×2:

| Card | Health | Body |
|---|---|---|
| CBC Mail API | OK emerald | Last delivery 08:06 · [Tester] · key `••••4e2a` |
| Webhook HMAC | OK | URL `/api/webhooks/n8n` · last 10 deliveries |
| SMS | Disabled | Provider TBD |
| **n8n** | OK | URL `https://n8n.cbc.internal` · last ping 4 s · [Tester événement fictif] |

n8n card CTA: `Voir les scénarios` → `/automation`

Never show full API keys.

### 5.12 Scénarios `/automation` — P1

Title: `Scénarios d’automatisation`  
Subtitle: `n8n exécute. CBC Supervision pilote.`  
Banner if disconnected: `n8n injoignable — Lancer désactivé`

Table:

| Nom | Déclencheur | Approbation | Dernier run | 7j | On | |
|---|---|---|---|---|---|---|
| Disque critique → mail + ticket | alert.opened disque | Non | 07:58 OK | 100% | on | Runs · Ouvrir dans n8n |
| Service SWIFT arrêté | service_down | **Oui** | — | — | on | |
| Hors ligne hors fenêtre | agent.offline | Non | 07:40 OK | 100% | on | |
| CPU durable | CPU durée | Non | 08:06 OK | 96% | on | |
| Nouvel agent enrôlé | enrolment | Non | hier | 100% | on | |

**No node canvas.** “Ouvrir dans n8n” is a text button, Admin only.

Click a row → slide-over last 20 runs.

### 5.13 Approbation (drawer overlay)

Triggered from playbook 2 or Actions.

```
Approbation requise                    expire 11:20
Redémarrer le service swift-gateway
Hôte SWIFT-02

Dry-run
  OK — service actif, restart autorisé, impact ~8 s

Motif (obligatoire)
  [                                        ]

[Refuser]                    [Approuver et signer]
```

Show chain caption: `RBAC → approbation → signature → allow-list → exécution → audit`

### 5.14 Palette Ctrl+K

Centered modal 560 px, dark header optional but keep white to match app:

Search placeholder: `Hôtes, alertes, modèles, scénarios…`

Default suggestions:

- Acquitter les critiques
- Enrôler un agent
- Ouvrir Studio — groupe SWIFT
- Mettre en maintenance : FS-DLA-01
- Lancer le scénario « Disque critique »

### 5.15 Journaux `/logs`

Time range · query `level=error` · facets host/group · histogram (slate bars) · virtualised log lines (mono 12 px).  
Deep-link chip: `Filtré · SWIFT-02`

### 5.16 Tableaux `/dashboards`

Grid 12-col. Default dashboard `Exploitation` (not deletable). Widgets: KPI, timeseries, top-N disk, alert list. Empty widget slot `+ Ajouter un widget`.

### 5.17 Rapports `/reports`

Cards: Disponibilité hebdomadaire · Top alertes · Inventaire · Conformité config.  
Each: [Télécharger PDF] [Planifier] (Mail API).

### 5.18 Réseau `/network`

Devices: `core-sw-dla-01` ICMP OK · `fw-yde-02` SNMP degraded. No “enrôler un agent” here. Caption: `Équipements SNMP/ICMP — pas des hôtes agent`.

### 5.19 Utilisateurs `/users`

Existing pattern: table Nom, Email, Rôle, Statut, Actions. Primary `Créer un utilisateur`. Roles: Admin, Opérateur, Consultation. Lot 2 chip `Sécurité` on one row as preview.

### 5.20 Audit `/audit`

Table: Heure · Acteur · Action · Cible · IP. Row example: `08:15  J.P. Mbida  config.publish  groupe SWIFT v13  10.1.1.40`  
Filter + `Exporter pour COBAC`.

### 5.21 Paramètres `/settings` (slim)

Only: Rétention · Langue par défaut · Session · Dossier conformité ISO · Feature flags `Automatisation` `IA`  
**Do not** put thresholds, tokens, or services here anymore.

### 5.22 Profil `/profile`

Nom (read-only), changer mot de passe, langue FR/EN, sessions actives.

### 5.23 Actions `/actions` (Lot 2)

Host picker · plugin · JSON-schema form · **Dry-run = ON** default · Submit. Result panel. Caption L0 reject example on a workstation.

---

## 6. Component recipes (implement these as reusable bits)

| Name | Recipe |
|---|---|
| `PageHeader` | Title + subtitle + **one** gold button |
| `StatusDot` | 8 px circle emerald/amber/rose/slate |
| `SeverityBadge` | Info slate · Mineure amber · Majeure rose · Critique rose solid |
| `InheritanceBadge` | `Hérité · SWIFT-Douala` / `Surcharge locale` / `Push en attente` |
| `BlueprintCard` | See 5.6 |
| `WizardStepper` | Vertical, checkmarks, current gold |
| `PlainLanguagePreview` | Sentence in gold-tint box |
| `ConfigDiff` | Two columns, added emerald / removed rose text, no decoration |
| `ImpactPreview` | One sentence + number |
| `ChannelCard` | Title, health, last event, Test |
| `PlaybookRow` | Table row + toggle |
| `EnrolmentSheet` | Modal 5.9 |
| `ApprovalDrawer` | 5.13 |
| `CommandPalette` | 5.14 |
| `PulseStrip` | Compact stats, not 4 huge gradient tiles |
| `MaintenanceBanner` | amber bar `Maintenance jusqu’à 14:00 — alertes suspendues` |

---

## 7. Interaction for the mock (enough to demo)

- Sidebar navigates all screens.
- Dashboard row → alert drawer.
- Alert “Voir l’hôte” → SWIFT-02.
- `Enrôler un agent` → enrolment sheet.
- Studio toggle Intention / Guidé / Expert.
- Guidé: Continuer shows step 7.
- Appliquer blueprint → apply modal.
- Intégrations n8n → Scénarios.
- Scénario with approval → approval drawer.
- `⌘K` / search icon → palette.
- Ack → modal → toast `Alerte acquittée`.

RBAC: mock as **Admin**. Optional footer switch `Vue Opérateur` that hides Studio write and gold Enrôler — nice, not required.

---

## 8. Explicit don’ts

- Do not clone Datadog’s density or Grafana’s dark dashboards as the main chrome.
- Do not put n8n’s node editor inside CBC Supervision.
- Do not use English UI strings (except hostnames / metric names).
- Do not use Lorem ipsum.
- Do not prefill login passwords.
- Do not use gold for CPU-critical.
- Do not show a role-simulator labelled “Tester les permissions RBAC”.
- Do not invent a chatbot (Lot 3 is out of this mock unless a tiny disabled `Assistant IA — bientôt` in sidebar).
- Do not add a marketing landing page.

---

## 9. References (optional if the model has the repo)

- Identity long-form: `docs/UI-UX-Design-Brief.md` §36
- Behaviour long-form: `docs/architecture/DES-003-interface-design.md`
- This file **wins** for mockup layout and copy.

---

*End of DES-003-MOCKUP. Hand this file to Claude as the single source of truth for mockups.*
