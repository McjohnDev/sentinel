#!/usr/bin/env bash
# FS7-04 — Postgres backup via Docker Compose (RPO ≤ 24 h)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_DIR="${COMPOSE_DIR:-$ROOT/docker}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
STAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
OUT="$BACKUP_DIR/cbc_supervision_${STAMP}.sql.gz"

echo "Backing up cbc_supervision → $OUT"
(cd "$COMPOSE_DIR" && docker compose exec -T postgres \
  pg_dump -U cbc_user -d cbc_supervision) | gzip > "$OUT"

# Retain 8 days (≥ RPO 24 h + weekly buffer)
find "$BACKUP_DIR" -name 'cbc_supervision_*.sql.gz' -mtime +8 -delete 2>/dev/null || true
echo "OK $OUT ($(wc -c < "$OUT") bytes)"
