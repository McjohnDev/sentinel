# DES-002 — Central platform architecture dossier (outline)

**Status:** Living draft stub (FS0-03)  
**Refs:** DES-002, PLT-*, STO-*  

## 1. Components

```
Agents ──TLS──► FastAPI Receiver ──► Validator (metric.v1/event.v1)
                      │                      │
                      │                      ├─► DLQ (invalid)
                      │                      └─► Processing / Rules
                      │                               │
                      ├─► PostgreSQL (inventory, alerts, users, audit)
                      ├─► VictoriaMetrics (metrics TSDB)
                      ├─► Loki (logs) [FS3]
                      └─► Redis (cache)
                      
Dashboard (React) ◄── REST/WS ── FastAPI API
Notify: CBC Mail API + HMAC webhook [FS4]
```

## 2. Data flow (happy path)

1. Agent POSTs authenticated batch  
2. Validate schema + dedup `message_id`  
3. Persist inventory touch; write metrics to VM; evaluate rules  
4. Open/update alerts; enqueue notifications  
5. Dashboard reads via API / WebSocket  

## 3. Deployment

- **Lot 1:** Docker Compose — Postgres, Redis, VictoriaMetrics, Loki, server, dashboard  
- **Lot 2 option:** Kubernetes HA + message queue (NATS/Kafka) when scaling past 500  

## 4. Storage model

| Class | Store | Retention (target) |
|---|---|---|
| Inventory / config / alerts / audit | PostgreSQL | Per retention policy |
| Metrics raw | VictoriaMetrics | ≥ 30 days |
| Metrics rollups | Victoria | ≥ 13 months |
| Logs | Loki | ≥ 30 days |
