# FS7 load results

Machine report: [`FS7-LOAD-RESULTS.json`](./FS7-LOAD-RESULTS.json)

| Metric | Value (lab 2026-08-13) |
|---|---|
| Agents | 128 created |
| Heartbeat / metric fails | **0 / 0** |
| Platform | healthy (Postgres, Redis, VM, Loki) |
| Collect→ingest p95 | 0.17 s (budget 60 s) |
| DB pool | `20+40` (was exhausting at 5+10) |

Stretch to 500:

```bash
python tools/load_test/run_load.py --agents 500 --duration 120 --interval 20 --out docs/architecture/FS7-LOAD-RESULTS-500.json
```
