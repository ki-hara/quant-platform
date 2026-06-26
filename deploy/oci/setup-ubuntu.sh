#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/quant-platform/app}"
DATA_DIR="${DATA_DIR:-/opt/quant-platform/data}"
BACKUP_DIR="${BACKUP_DIR:-/opt/quant-platform/backups}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash deploy/oci/setup-ubuntu.sh"
  exit 1
fi

apt-get update
apt-get install -y docker.io docker-compose-v2 git sqlite3
systemctl enable --now docker

mkdir -p "$DATA_DIR" "$BACKUP_DIR"

if [[ ! -f "$APP_DIR/deploy/oci/docker-compose.yml" ]]; then
  echo "App source not found at $APP_DIR"
  echo "Clone or copy this repository there first, then run this script again."
  exit 1
fi

cd "$APP_DIR/deploy/oci"
docker compose up -d --build

echo "Quant platform is starting."
echo "Check status: docker ps"
echo "Open: http://SERVER_PUBLIC_IP"
