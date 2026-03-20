#!/usr/bin/env bash
# One-time setup script for a Google Cloud e2 VM (Ubuntu 22.04+, x86_64).
# Safe to re-run — each step checks whether it has already been completed.
#
# Run as a user with sudo access:
#   bash setup.sh

set -euo pipefail

REPO_URL="git@github.com:rhernandezch/bluetrak.git"
APP_DIR="$HOME/bluetrak"
DEPLOY_KEY="$HOME/.ssh/bluetrak_deploy"

# ── System dependencies ────────────────────────────────────────────────────
if ! command -v curl &>/dev/null || ! command -v git &>/dev/null; then
  echo "==> Installing system dependencies"
  sudo apt-get update -q
  sudo apt-get install -y -q curl git
else
  echo "==> System dependencies already installed, skipping"
fi

# ── Docker ─────────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo "==> Installing Docker"
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"
  echo "    Docker installed. NOTE: group membership takes effect in new shells."
else
  echo "==> Docker already installed, skipping"
fi

# ── GitHub deploy key ──────────────────────────────────────────────────────
if [ ! -f "$DEPLOY_KEY" ]; then
  echo "==> Generating GitHub deploy key"
  mkdir -p "$HOME/.ssh"
  ssh-keygen -t ed25519 -C "bluetrak-deploy" -f "$DEPLOY_KEY" -N ""
fi

if ! grep -q "bluetrak_deploy" "$HOME/.ssh/config" 2>/dev/null; then
  echo "==> Configuring SSH for GitHub"
  cat >> "$HOME/.ssh/config" <<SSH_CONFIG

Host github.com
  HostName github.com
  User git
  IdentityFile $DEPLOY_KEY
  StrictHostKeyChecking accept-new
SSH_CONFIG
else
  echo "==> SSH config for GitHub already present, skipping"
fi

# Test connectivity; if it fails the key hasn't been added to GitHub yet
if ! ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
  echo ""
  echo "    Add the following public key as a Deploy Key on GitHub:"
  echo "    https://github.com/rhernandezch/bluetrak/settings/keys/new"
  echo "    (Title: bluetrak-vm, Allow write access: NO)"
  echo ""
  cat "${DEPLOY_KEY}.pub"
  echo ""
  read -rp "    Press Enter once the key has been added to GitHub... "
fi

# ── Clone repository ──────────────────────────────────────────────────────
if [ ! -d "$APP_DIR/.git" ]; then
  echo "==> Cloning repository"
  git clone "$REPO_URL" "$APP_DIR"
else
  echo "==> Repository already cloned, pulling latest"
  git -C "$APP_DIR" pull origin main
fi

# ── Environment file ─────────────────────────────────────────────────────
if [ ! -f "$APP_DIR/.env" ]; then
  echo "==> Creating .env file from template"
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
else
  echo "==> .env file already exists, skipping"
fi

echo ""
echo "==> Done! Next steps:"
echo "    1. Edit secrets:  nano $APP_DIR/.env"
echo "    2. Start service: cd $APP_DIR && docker compose up -d --build"
echo "    3. Check logs:    docker compose -f $APP_DIR/compose.yml logs -f"
