#!/usr/bin/env bash
# Deploy latest changes from main.
# Run on the Oracle VM: bash /opt/bluetrak/deploy/deploy.sh

set -euo pipefail

APP_DIR="/opt/bluetrak"
SERVICE_USER="bluetrak"

echo "==> Pulling latest changes"
cd "$APP_DIR"
sudo git pull origin main

echo "==> Syncing dependencies"
sudo -u "$SERVICE_USER" bash -c "
  export PATH=$HOME/.local/bin:/root/.local/bin:$PATH
  cd $APP_DIR
  uv sync --no-dev
"

echo "==> Restarting service"
sudo systemctl restart bluetrak
sudo systemctl status bluetrak --no-pager
