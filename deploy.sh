#!/usr/bin/env bash
# deploy.sh — build and ship Kairos to the home lab server.
# Run from the project root: ./deploy.sh
#
# Set SERVER and REMOTE_DIR to match your setup, either by editing the defaults
# below or by exporting them at call time (keeps real values out of git):
#   KAIROS_SERVER=myserver KAIROS_REMOTE_DIR=/home/me/kairos ./deploy.sh
#   SERVER     — SSH alias from ~/.ssh/config (e.g. "myserver")
#   REMOTE_DIR — absolute path on the server (e.g. "/home/<user>/kairos")
set -euo pipefail

SERVER="${KAIROS_SERVER:-<your-server-alias>}"
REMOTE_DIR="${KAIROS_REMOTE_DIR:-/home/<your-user>/kairos}"

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
ssh "$SERVER" "REMOTE_DIR='$REMOTE_DIR' bash -s" <<'REMOTE'
set -euo pipefail
cd "$REMOTE_DIR"

# First deploy: create .env from example if it doesn't exist yet
if [ ! -f .env ]; then
  echo "WARNING: .env not found on server."
  echo "Copy .env.example to .env and fill in real values, then re-run deploy.sh"
  exit 1
fi

# Build image first so indexers run on the latest code
docker compose build backend

# Re-index all sources before bringing backend up
# (idempotent — skips unchanged files; github/conversations degrade gracefully
#  if GITHUB_TOKEN / MEMORY_SESSIONS_PATH aren't configured yet)
# NOTE: `< /dev/null` is required — `docker compose run` attaches stdin, and
# without it the first run would swallow the rest of this heredoc (skipping `up -d`).
docker compose run --rm -T backend python indexer.py </dev/null
docker compose run --rm -T backend python notion_indexer.py </dev/null
docker compose run --rm -T backend python github_indexer.py </dev/null
docker compose run --rm -T backend python conversations_indexer.py </dev/null

# Bring up (or restart if already running)
docker compose up -d

echo "==> Done. Kairos is live."
REMOTE

echo "==> Deploy complete."
