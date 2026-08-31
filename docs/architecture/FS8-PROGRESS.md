# FS8 progress — Pilot, extinction, Lot 1 UAT
**Date:** 2026-08-13  
**Plan:** PLAN-CBC-IMPL-001  

| Story | Status | Artefact |
|---|---|---|
| FS8-01 Pilot fleet | **Done** | `PilotHost` + `/api/pilot/hosts`; UI checklist on **Pilot & UAT** |
| FS8-02 Alerting E2E UAT | **Done** | Family 3 cases `UAT-3.*` in `uat_cases` |
| FS8-03 Resilience UAT | **Done** | Family 4 cases `UAT-4.*` |
| FS8-04 History/reporting UAT | **Done** | Family 5 cases `UAT-5.*` |
| FS8-05 Script extinction | **Done** | `CoverageCheck` DB + transitions; bulk verify/decommission; DES-004 v0.3 |
| FS8-06 Acceptance pack | **Done** | `/api/acceptance/pack` + sign-offs; `docs/ops/LOT1_ACCEPTANCE_PACK.md` |

## Demo

1. Open **Pilot & UAT** — add a pilot host, tick family-1 checklist.  
2. Mark UAT cases pass/fail with evidence.  
3. Admin: **Bulk verify delivered** → **Decommission verified** until open Musts = 0.  
4. Export acceptance pack JSON; record sign-off.

## Note

CBC still owes official script inventory (open point 1c). Rows stay `TBD` for legacy paths until workshop; extinction workflow is ready.

Demo walkthrough: `docs/ops/LOT1_DEMO_SCENARIOS.md`. Placeholder watch lists: `docs/ops/CBC_WATCH_LISTS.md`.

Rebuild: `docker compose up -d --build server dashboard`
