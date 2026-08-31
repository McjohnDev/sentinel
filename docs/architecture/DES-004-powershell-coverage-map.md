# DES-004 — Functional coverage map (PowerShell → agent plugins)

**Status:** v0.3 (FS8) — extinction workflow live in platform  
**Refs:** AGT-013, AGT-014, DES-004  

## Instructions

1. Workshop with CBC: list every check performed by legacy PowerShell scripts.  
2. One row per distinct check (not per host copy of the same script).  
3. Update `status` at every sprint review until FS8 extinction.  
4. A script may only be stopped when status = `verified_in_production`.  
5. Platform UI: **Pilot & UAT** or Paramètres → Couverture PS; API `PATCH /api/coverage/checks/{id}`.

Allowed `status` values: `planned` · `delivered` · `verified_in_production` · `script_decommissioned` · `waived`

## Coverage table

| Check ID | Legacy script / path | Check description | Hosts / groups | Planned plugin | Status | Sprint | Notes |
|---|---|---|---|---|---|---|---|
| PS-001 | *TBD — CBC inventory* | CPU threshold / utilisation | *TBD* | `cpu.collector` | delivered | FS2 | Advance via Pilot & UAT after pilot proof |
| PS-002 | *TBD* | Disk free space | *TBD* | `disk.collector` | delivered | FS2 | |
| PS-003 | *TBD* | Critical Windows/Linux service | *TBD* | `services.collector` | delivered | FS5 | Needs CBC official service list in group config |
| PS-004 | *TBD* | Watched log / file growth | *TBD* | `files.collector` | delivered | FS5 | Needs CBC official file list in group config |
| PS-005 | *TBD* | Memory utilisation | *TBD* | `memory.collector` | delivered | FS2 | |
| PS-006 | *TBD* | Network IF counters | *TBD* | `network.collector` | delivered | FS2 | |
| PS-007 | *TBD* | Process presence / Top-N | *TBD* | `process.collector` | delivered | FS2 | |
| PS-008 | *TBD* | Agent self footprint | *TBD* | `agent.footprint` | delivered | FS5 | AGT-007 |

## Extinction path (FS8-05)

`delivered` → `verified_in_production` (pilot UAT) → `script_decommissioned`  
Bulk helpers: `POST /api/coverage/checks/bulk-verify`, `POST /api/coverage/checks/bulk-decommission`.

## Duplicate-run tracking (AGT-014)

During transition, legacy script + agent MAY run on the same host. Platform SHALL flag overlapping checks via `POST /api/coverage/overlaps` (UI: Paramètres → Couverture PS).

| Host | Legacy check ID | Plugin | Detected on | Cleared on |
|---|---|---|---|---|
| — | — | — | — | — |

## Sign-off

| Role | Name | Date |
|---|---|---|
| CBC ops | | |
| Tech lead | | |
