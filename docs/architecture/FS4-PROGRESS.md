# FS4 progress — Rules, alerts, notifications
**Date:** 2026-08-13  
**Plan:** PLAN-CBC-IMPL-001  

| Story | Status | Artefact |
|---|---|---|
| FS4-01 Duration thresholds | **Done** | `threshold_duration_seconds` (default 300). Spike ≠ alert; all samples in window must exceed. Settings UI. |
| FS4-02 Four severities + lifecycle | **Done** | Info / Minor / Major / Critical. Open → Ack → Resolved (+ auto-resolve). Timeline `alert_events`. Ack bug (`active` vs `open`) fixed. |
| FS4-03 Maintenance windows | **Done** | `GET/POST/DELETE /api/maintenance`. Distinct from availability windows. Suppress + audit event. |
| FS4-04 Routing & escalation | **Partial** | Recipients = CBC Mail API. Escalate unacked after N min → Critical + re-notify. Per-rule schedules later. |
| FS4-05 CBC Mail API | **Done** | Still Lot-1 channel; delivery status on alert (`mail_status`). |
| FS4-06 HMAC webhook | **Done** | `X-CBC-Signature: sha256=…`, retries, `webhook_status`. |
| FS4-07 Log-pattern rules | **Done** | `pattern_alerts` from agent → `log_pattern` alert (ALR-003). |
| FS4-08 Alert UI | **Done** | Filters 4 severities, resolve, delivery status. |
| FS4-09 Offline regression | **Done** | Offline still uses availability windows; skipped during maintenance. |

## Demo

1. Set duration to 300 s. One high-CPU heartbeat → no alert. Sustained 5 min → **Major**.  
2. Create a maintenance window → metric alerts suppressed (timeline `suppressed`).  
3. Enable webhook URL + secret → POST signed JSON on new Major/Critical.

Rebuild: `docker compose up -d --build server dashboard`
