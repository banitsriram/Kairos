#!/usr/bin/env bash
# Runs on the server via cron. Re-indexes the vault and Notion into Kairos.
# Add to crontab with: crontab -e
#   */15 * * * * /home/<your-user>/kairos/scripts/server_cron.sh >> /home/<your-user>/kairos/logs/cron.log 2>&1
#
# Vault sync is handled by Syncthing — no git pull needed here.
set -euo pipefail

echo "[$(date -Iseconds)] Starting index..."

# Re-index vault + Notion inside the running backend container
cd /home/<your-user>/kairos
docker compose exec -T backend python indexer.py
docker compose exec -T backend python notion_indexer.py
docker compose exec -T backend python github_indexer.py
docker compose exec -T backend python conversations_indexer.py

echo "[$(date -Iseconds)] Index complete."
