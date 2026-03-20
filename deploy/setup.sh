#!/usr/bin/env bash
# One-time setup script for a Google Cloud e2 VM (Ubuntu 22.04+, x86_64).
# Run as a user with sudo access:
#   bash setup.sh

set -euo pipefail

REPO_URL="git@github.com:rhernandezch/bluetrak.git"
APP_DIR="/opt/bluetrak"
SERVICE_USER="bluetrak"
DEPLOY_KEY="/root/.ssh/bluetrak_deploy"

echo "==> Installing system dependencies"
sudo apt-get update -q
sudo apt-get install -y -q curl git

echo "==> Installing uv"
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

echo "==> Setting up GitHub deploy key"
if [ ! -f "$DEPLOY_KEY" ]; then
  sudo ssh-keygen -t ed25519 -C "bluetrak-deploy" -f "$DEPLOY_KEY" -N ""
  sudo chmod 600 "$DEPLOY_KEY"
fi

echo ""
echo "    Add the following public key as a Deploy Key on GitHub:"
echo "    https://github.com/rhernandezch/bluetrak/settings/keys/new"
echo "    (Title: bluetrak-vm, Allow write access: NO)"
echo ""
sudo cat "${DEPLOY_KEY}.pub"
echo ""
read -rp "    Press Enter once the key has been added to GitHub... "

# Configure SSH for root to use the deploy key for github.com
sudo mkdir -p /root/.ssh
sudo tee /root/.ssh/config > /dev/null <<'SSH_CONFIG'
Host github.com
  HostName github.com
  User git
  IdentityFile /root/.ssh/bluetrak_deploy
  StrictHostKeyChecking accept-new
SSH_CONFIG
sudo chmod 600 /root/.ssh/config

echo "==> Creating service user"
sudo useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER" || true

echo "==> Cloning repository"
sudo git clone "$REPO_URL" "$APP_DIR"
sudo chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"

echo "==> Installing Python and dependencies"
sudo -u "$SERVICE_USER" bash -c "
  export PATH=$HOME/.local/bin:/root/.local/bin:$PATH
  cd $APP_DIR
  uv sync --no-dev
"

echo "==> Creating .env file"
if [ ! -f "$APP_DIR/.env" ]; then
  sudo cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  sudo chmod 600 "$APP_DIR/.env"
  sudo chown "$SERVICE_USER:$SERVICE_USER" "$APP_DIR/.env"
  echo "    Edit $APP_DIR/.env to configure alerts and other settings"
fi

echo "==> Creating data directory"
sudo mkdir -p "$APP_DIR/data"
sudo chown "$SERVICE_USER:$SERVICE_USER" "$APP_DIR/data"

echo "==> Installing systemd service"
sudo cp "$APP_DIR/deploy/bluetrak.service" /etc/systemd/system/bluetrak.service
sudo sed -i "s|ExecStart=.*|ExecStart=$APP_DIR/.venv/bin/python -m bluetrak|" /etc/systemd/system/bluetrak.service
sudo systemctl daemon-reload
sudo systemctl enable bluetrak
sudo systemctl start bluetrak

echo ""
echo "==> Done! Check status with:"
echo "    sudo systemctl status bluetrak"
echo "    sudo journalctl -u bluetrak -f"
