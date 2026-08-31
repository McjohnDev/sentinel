# Lot 1 acceptance pack (FS8-06 / M4)

**Milestone:** M4 — Lot 1 accepted  
**Source of truth (live):** `GET /api/acceptance/pack`  
**UI:** Pilot & UAT → Export pack

## Traceability

Each Part K UAT case maps to ≥ 1 requirement ID (see seeded `uat_cases`). Export the JSON pack for the sign-off meeting; attach:

- `FS7-LOAD-RESULTS.json` (NFR-004)
- Latency budget run (`tools/latency/measure_budgets.py`)
- Backup drill note (`docs/ops/BACKUP_RESTORE_RUNBOOK.md`)
- DES-004 extinction statuses (zero open Musts)

## Go / No-Go gates

| Gate | Criterion |
|---|---|
| Coverage | `open_must_check_ids` empty (verified / decommissioned / waived) |
| UAT | Families 1, 3, 4, 5 all `pass` or `waived` |
| Sign-off | ≥ 1 acceptance sign-off recorded |

## Sign-off roles

- `cbc_ops`
- `tech_lead`
- `sponsor`

Record via UI or `POST /api/acceptance/signoffs`.
