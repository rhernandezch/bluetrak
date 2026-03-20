#!/usr/bin/env bash
# One-time setup script for a Google Cloud e2 VM (Ubuntu 22.04+, x86_64).
# Run as a user with sudo access:
#   bash setup.sh

set -euo pipefail

REPO_URL="git@github.com:rhernandezch/bluetrak.git"
APP_DIR="$HOME/bluetrak"
DEPLOY_KEY="$HOME/.ssh/bluetrak_deploy"

echo "==> Installing system dependencies"
sudo apt-get update -q
sudo apt-get install -y -q curl git

echo "==> Installing Docker"
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
echo "    Docker installed. NOTE: group membership takes effect in new shells."

echo "==> Setting up GitHub deploy key"
if [ ! -f "$DEPLOY_KEY" ]; then
  ssh-keygen -t ed25519 -C "bluetrak-deploy" -f "$DEPLOY_KEY" -N ""
fi

echo ""
echo "    Add the following public key as a Deploy Key on GitHub:"
echo "    https://github.com/rhernandezch/bluetrak/settings/keys/new"
echo "    (Title: bluetrak-vm, Allow write access: NO)"
echo ""
cat "${DEPLOY_KEY}.pub"
echo ""
read -rp "    Press Enter once the key has been added to GitHub... "

cat >> "$HOME/.ssh/config" <<SSH_CONFIG

Host github.com
  HostName github.com
  User git
  IdentityFile $DEPLOY_KEY
  StrictHostKeyChecking accept-new
SSH_CONFIG

echo "==> Cloning repository"
git clone "$REPO_URL" "$APP_DIR"

echo "==> Creating .env file"
if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  echo "    Edit $APP_DIR/.env to configure Telegram and other settings"
  echo "    Then run: cd $APP_DIR && docker compose up -d --build"
else
  echo "==> Starting service"
  cd "$APP_DIR"
  sg docker "docker compose up -d --build"
fi

echo ""
echo "==> Done! Next steps:"
echo "    1. Edit secrets:  nano $APP_DIR/.env"
echo "    2. Start service: cd $APP_DIR && docker compose up -d --build"
echo "    3. Check logs:    docker compose -f $APP_DIR/compose.yml logs -f"
