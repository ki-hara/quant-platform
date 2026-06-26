#!/usr/bin/env bash
set -euo pipefail

DB_PATH="${DB_PATH:-/opt/quant-platform/data/quant_platform.db}"
BACKUP_DIR="${BACKUP_DIR:-/opt/quant-platform/backups}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKUP_PATH="$BACKUP_DIR/quant_platform_$STAMP.db"

mkdir -p "$BACKUP_DIR"

if [[ ! -f "$DB_PATH" ]]; then
  echo "Database not found: $DB_PATH"
  exit 1
fi

sqlite3 "$DB_PATH" ".backup '$BACKUP_PATH'"
echo "$BACKUP_PATH"
