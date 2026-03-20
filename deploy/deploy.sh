#!/usr/bin/env bash
# Deploy latest changes from main.
# Run on the GCP VM: bash ~/bluetrak/deploy/deploy.sh

set -euo pipefail

APP_DIR="$HOME/bluetrak"

echo "==> Pulling latest changes"
cd "$APP_DIR"
git pull origin main

echo "==> Rebuilding and restarting service"
docker compose up -d --build

echo "==> Done! Logs:"
docker compose logs --tail=20
