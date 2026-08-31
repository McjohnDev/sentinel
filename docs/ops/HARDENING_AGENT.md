# Agent hardening guide (SEC-008 / FS7-05)

## Runtime

- Run as a dedicated low-privilege service account (not Domain Admin / root for day-to-day).
- Single instance lock enabled (default) — do not disable in production.
- TLS verify **on** for server URL (`verify=False` only for lab with explicit override).
- Durable buffer on local disk with size/time caps (default 500 MB / 24 h).

## Secrets

- Enrolment token: single-use; rotate after fleet rollout.
- Agent `auth_key` stored with file ACLs restricted to the service account.
- Do not embed tokens in golden images.

## Host

- Restrict outbound to platform API only (firewall / proxy allow-list).
- Harden OS baseline (patching, disk encryption for laptops, EDR per CBC policy).
- Log rotation enabled; avoid world-readable log dirs.

## Updates

- Pin agent version; change via controlled package rollout.
- After remote config publish, confirm `config_version` ack on heartbeat.
