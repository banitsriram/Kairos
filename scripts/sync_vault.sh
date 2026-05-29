#!/usr/bin/env bash
# Pull the latest vault from git, then trigger a re-index.
# Add to cron: */15 * * * * /path/to/kairos/scripts/sync_vault.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

VAULT_PATH="${VAULT_PATH:-/home/banit/vault}"
DB_PATH="${DB_PATH:-/data/brain.db}"

cd "$VAULT_PATH"
git pull --ff-only origin main

export VAULT_PATH DB_PATH
cd "$PROJECT_ROOT/backend"
python indexer.py
python notion_indexer.py
