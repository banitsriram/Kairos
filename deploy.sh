#!/usr/bin/env bash
# deploy.sh — build and ship Kairos to the home lab server (amrad).
# Run from the project root: ./deploy.sh
set -euo pipefail

SERVER="amrad"
REMOTE_DIR="/home/abanit/kairos"

echo "==> Building frontend..."
cd frontend
npm run build
cd ..

echo "==> Syncing files to $SERVER..."
# rsync everything except dev artifacts and secrets.
# --exclude .env because secrets never travel over the wire — create .env
# manually on the server once, then it stays there.
rsync -avz --progress \
  --exclude '.env' \
  --exclude '.venv/' \
  --exclude 'frontend/node_modules/' \
  --exclude 'data/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  . "$SERVER:$REMOTE_DIR"

echo "==> Deploying on server..."
ssh "$SERVER" bash <<'REMOTE'
set -euo pipefail
cd /home/abanit/kairos

# First deploy: create .env from example if it doesn't exist yet
if [ ! -f .env ]; then
  echo "WARNING: .env not found on server."
  echo "Copy .env.example to .env and fill in real values, then re-run deploy.sh"
  exit 1
fi

# Re-index vault before bringing backend up
# (idempotent — skips unchanged files)
docker compose run --rm backend python indexer.py
docker compose run --rm backend python notion_indexer.py

# Bring up (or rebuild if image changed)
docker compose up -d --build

echo "==> Done. Kairos is live at https://100.104.67.55"
REMOTE

echo "==> Deploy complete."
