# FS9 progress — Lot 2 actions & approvals
**Date:** 2026-08-16  
**Plan:** PLAN-CBC-IMPL-001 Lot 2 starter  

| Story | Status | Artefact |
|---|---|---|
| Signed task.v1 queue | **Done** | `RemoteTask` + HMAC sign; heartbeat `tasks[]` dispatch |
| Approval gate (SEC-005) | **Done** | `ActionApproval` + `/api/approvals` + UI `/approvals` |
| Action UI | **Done** | `/actions` — dry-run default, allow-listed plugins |
| L1 agent plugins | **Done** | `action_plugins.py` — health / service.manage / inventory / metrics.on_demand |
| **PCI Hygiene (Lot 2)** | **Done (starter)** | `pci.hygiene` — read-only checklist + score; **not** AoC/ASV/QSA |
| L0 still safe | **Done** | Default capability L0 rejects; L1 via config `agent.capability_level` |

## Demo

1. Publish group config `{ "agent": { "capability_level": "L1" } }` (or Mark L1 on Actions).  
2. **Actions** → dry-run `health.check` → queued → next heartbeat → result.  
3. Live `service.manage` → lands in **Approbations** → Admin approve → dispatch.  
4. **Actions** → `pci.hygiene` → result shows score % + grade (`good` / `fair` / `poor`) and failed check ids.

## PCI Hygiene (Lot 2 placement)

- **Theme:** Action plugins (AGT-060+) — optional CBC control-plane hygiene, not payment certification.  
- **Plugin:** `pci.hygiene` (allow-listed on agent + platform).  
- **Probes (read-only):** risky listeners, host firewall, identity, AV/EDR process list, time sync, logging capability, disk free.  
- **Disclaimer:** Hygiene score only — **not** PCI DSS Attestation of Compliance, ASV scan, or QSA assessment.  
- **Next Lot 2 polish:** CBC-specific process allow-list, evidence export into reports, optional ASV connector ingest.

## Note

Live service start/stop remains **gated** (recorded, not executed) until CBC allow-list is defined.

Rebuild: `docker compose up -d --build server dashboard agent`
