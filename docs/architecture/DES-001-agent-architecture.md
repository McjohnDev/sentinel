# DES-001 — Agent architecture dossier (outline)

**Status:** Living draft stub (FS0-02) — diagrams to be completed in workshop  
**Refs:** DES-001, AGT-000–015  

## 1. Components

```
┌─────────────────────────────────────────────────────────┐
│                     cbc-agent (L0)                      │
│  ┌──────────┐  ┌─────────────┐  ┌────────────────────┐ │
│  │ Scheduler│→ │Plugin registry│→ │ Collectors (L0)  │ │
│  └──────────┘  └─────────────┘  └────────────────────┘ │
│        │              │                    │            │
│        ▼              ▼                    ▼            │
│  ┌──────────┐  ┌─────────────┐  ┌────────────────────┐ │
│  │ Identity │  │ Local buffer│  │ Transport (TLS out)│ │
│  │ (AGT-015)│  │ (AGT-005)   │  │ → platform :443    │ │
│  └──────────┘  └─────────────┘  └────────────────────┘ │
│        │                                                │
│        ▼                                                │
│  ┌──────────┐  task.v1 received → REJECT (L0)           │
│  │ Instance │                                           │
│  │ lock     │                                           │
│  └──────────┘                                           │
└─────────────────────────────────────────────────────────┘
```

## 2. Plugin lifecycle

1. Discover manifests (`plugin.manifest.v1`)  
2. Validate privileges vs config  
3. Schedule at `default_interval_seconds`  
4. Collect → emit `metric.v1` / `event.v1`  
5. On failure: retry / degrade; never crash host process  

## 3. Agent state machine

`starting` → `enrolling` → `enrolled` → (`collecting` | `buffering` | `degraded`) → `stopped`

## 4. Sequence — enrolment

Agent → Platform: one-time token + identity → Platform: `agent_id` + `auth_key`

## 5. Sequence — collect cycle

Scheduler → Plugin.collect → Buffer/Send → Platform ACK (or buffer on failure)

## 6. Open edits

- Replace ASCII with editable diagrams (Mermaid / draw.io) in same folder once workshop done.
