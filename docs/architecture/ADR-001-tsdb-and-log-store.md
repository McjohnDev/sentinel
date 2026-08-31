# ADR-001 — Time-series and log store selection
**Status:** Accepted (FS0-07)  
**Date:** 2026-08-13  
**Context:** SPEC-CBC-UNIFIED-001 open points STO-001 / STO-003  

## Decision

| Store | Choice | Rationale |
|---|---|---|
| **TSDB** | **VictoriaMetrics** (single-node for Lot 1) | Prometheus-compatible ingest/query; low ops overhead; matches Cahier preference for Prometheus-ecosystem TSDB; horizontal path later via VM cluster |
| **Log store** | **Grafana Loki** (Lot 1) | Native label-based log model; pairs with agent batched log shipping; lighter than OpenSearch for CBC fleet size (128→500) |

## Alternatives considered

- **TimescaleDB** — strong if we want SQL-only stack; deferred to avoid coupling metrics retention to PostgreSQL ops until needed.
- **InfluxDB** — viable; less aligned with Prometheus tooling already used for platform self-metrics.
- **OpenSearch** — richer full-text; heavier footprint; revisit if Loki search proves insufficient in FS3 UAT.

## Consequences

- `docker-compose` SHALL include VictoriaMetrics (port 8428) and Loki (port 3100) as optional Lot-1 services.
- Platform metric writer (FS2) uses Prometheus remote-write or VM import API.
- Log ship path (FS3) targets Loki push API.
- Decision may be revisited only via a new ADR before Lot 1 UAT if load tests fail NFR-004.
