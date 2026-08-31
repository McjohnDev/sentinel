# CBC watch lists (Lot 1 placeholders)

**Status:** Demo placeholders until CBC delivers official inventories (open points CBC-A / CBC-B / 1c).

These lists are **not** production SWIFT/core-banking inventories. They exist so Lot 1 collectors, group config, and UAT can be exercised today.

## Services (CBC-A)

| OS | Demo name | Why it is here |
|---|---|---|
| Windows | `Spooler` | Present on every Windows host |
| Windows | `EventLog` | Always running; safe to watch |
| Linux | `cron` / `cron.service` | Common on Ubuntu/Debian |
| Linux | `ssh` / `sshd` | Common on servers |

Official CBC list (examples expected later): SWIFT AutoClient, SQL Server, core banking services.

Load via **Paramètres → Groupes & config** JSON:

```json
{
  "services_monitoring": {
    "enabled": true,
    "interval": 60,
    "services": ["Spooler", "EventLog"]
  }
}
```

Or set `agent/config.lab.yaml` / group overlay.

## Files (CBC-B)

| OS | Path | `max_size_mb` |
|---|---|---|
| Windows | `C:\Windows\Temp` | 2048 |
| Linux | `/var/log` | 1024 |
| Linux | `/tmp` | 2048 |

Official CBC list expected later: SWIFT log files, application logs with size caps.

```json
{
  "files_monitoring": {
    "enabled": true,
    "interval": 300,
    "files": [{ "path": "C:\\\\Windows\\\\Temp", "max_size_mb": 2048 }]
  }
}
```

## Workstation offline threshold (CBC-C)

Lab default: **7200 s** (2 h) for `machine_type: workstation`, **90 s** for `server`.  
CBC must confirm the official workstation value.

## PowerShell inventory (open point 1c)

DES-004 rows `PS-001`–`PS-008` are **delivered as plugins**. Legacy script paths stay `TBD` until the CBC ops workshop. Extinction (`verified_in_production` → `script_decommissioned`) cannot complete without that inventory.
