# FS7 load test

Sustained synthetic agent traffic for **NFR-004** (128 → 500).

## Server flags (Compose)

```yaml
environment:
  ALLOW_LOAD_SIM: "true"
  RATE_LIMIT_DISABLED: "true"
```

Then rebuild/restart `server`.

## Run

```bash
# 128 agents × 60 s (CBC current fleet size)
python tools/load_test/run_load.py --agents 128 --duration 60 --out docs/architecture/FS7-LOAD-RESULTS.json

# stretch to Lot-1 target
python tools/load_test/run_load.py --agents 500 --duration 120 --out docs/architecture/FS7-LOAD-RESULTS-500.json
```

Default credentials: `admin` / `admin123` (override with `--username` / `--password`).

## Pass criteria

- Heartbeat + metric POSTs succeed (fail count = 0) → no data loss under sustained load
- Report JSON archived under `docs/architecture/`
