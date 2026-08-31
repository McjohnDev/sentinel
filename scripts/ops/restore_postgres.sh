#!/usr/bin/env bash
# FS7-04 — Restore Postgres dump (destructive — confirm)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_DIR="${COMPOSE_DIR:-$ROOT/docker}"
FILE="${1:-}"
if [[ -z "$FILE" || ! -f "$FILE" ]]; then
  echo "Usage: $0 path/to/cbc_supervision_YYYYMMDD_HHMMSS.sql.gz" >&2
  exit 1
fi
echo "WARNING: restores into running postgres container (cbc_supervision)."
echo "File: $FILE"
read -r -p "Type YES to continue: " confirm
[[ "$confirm" == "YES" ]] || exit 1

gunzip -c "$FILE" | (cd "$COMPOSE_DIR" && docker compose exec -T postgres \
  psql -U cbc_user -d cbc_supervision)
echo "Restore complete. Restart server if needed: docker compose -f $COMPOSE_DIR/docker-compose.yml restart server"
