#!/usr/bin/env bash
# Runs on the server via cron. Pulls the vault and re-indexes into Kairos.
# Add to crontab with: crontab -e
#   */15 * * * * /home/abanit/kairos/scripts/server_cron.sh >> /home/abanit/kairos/logs/cron.log 2>&1
set -euo pipefail

VAULT_PATH="${VAULT_PATH:-/home/abanit/vault}"

echo "[$(date -Iseconds)] Starting sync..."

# Pull latest vault from git
cd "$VAULT_PATH"
git pull --ff-only origin main

# Re-index vault + Notion inside the running backend container
cd /home/abanit/kairos
docker compose exec -T backend python indexer.py
docker compose exec -T backend python notion_indexer.py

echo "[$(date -Iseconds)] Sync complete."
