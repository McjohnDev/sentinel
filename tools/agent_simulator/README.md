# Agent simulator (FS0-09)

Generates realistic `metric.v1` payloads (and optional invalid ones) against the frozen shared protocols.

```bash
# from repo root
pip install -r shared/requirements.txt
python tools/agent_simulator/simulate.py --hosts 5
python tools/agent_simulator/simulate.py --invalid
python tools/agent_simulator/simulate.py --hosts 3 --out /tmp/metrics.jsonl
```

When the platform ingest endpoint exists (FS1):

```bash
python tools/agent_simulator/simulate.py --hosts 10 --post http://localhost:8443/api/ingest/metrics
```
