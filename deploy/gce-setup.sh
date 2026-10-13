#!/bin/bash
# Google Cloud e2-micro (Ubuntu 22.04/24.04) da Agent Bot o'rnatish.
# Ishlatish (VM ichida, root yoki sudo bilan):
#   sudo bash deploy/gce-setup.sh
set -e

APP_DIR=/opt/agent_bot
APP_USER=agentbot
REPO_URL="${REPO_URL:-}"  # masalan: export REPO_URL=https://github.com/siz/agent_bot.git

if [ -z "$REPO_URL" ]; then
  echo "XATO: avval REPO_URL ni belgilang:"
  echo "  export REPO_URL=https://github.com/siz/agent_bot.git"
  exit 1
fi

apt-get update -y
apt-get install -y git python3-venv python3-pip

id -u "$APP_USER" >/dev/null 2>&1 || useradd -m -s /bin/bash "$APP_USER"

if [ ! -d "$APP_DIR/.git" ]; then
  rm -rf "$APP_DIR"
  git clone "$REPO_URL" "$APP_DIR"
  chown -R "$APP_USER:$APP_USER" "$APP_DIR"
fi

sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
  echo ">>> $APP_DIR/.env ni to'ldiring (TELEGRAM_BOT_TOKEN, GEMINI_API_KEY), keyin:"
  echo ">>> sudo cp $APP_DIR/deploy/agentbot.service /etc/systemd/system/ && sudo systemctl enable --now agentbot"
else
  cp "$APP_DIR/deploy/agentbot.service" /etc/systemd/system/agentbot.service
  systemctl daemon-reload
  systemctl enable --now agentbot
  systemctl status agentbot --no-pager
fi
