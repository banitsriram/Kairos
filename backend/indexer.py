"""
Walk the Obsidian vault and load changed notes into the SQLite FTS5 index.
Run this manually or from cron after sync_vault.sh pulls the vault.
"""
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from db import get_connection, init_db  # noqa: E402 (after load_dotenv)

_PROJECT_ROOT = Path(__file__).parent.parent


def _resolve(env_key: str, default: str) -> Path:
    raw = os.getenv(env_key, default)
    p = Path(raw)
    return p if p.is_absolute() else (_PROJECT_ROOT / p).resolve()


VAULT_PATH = _resolve("VAULT_PATH", "tests/sample_vault")


def extract_title(content: str, filepath: Path) -> str:
    """Return the first # Heading, or fall back to the filename without extension."""
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else filepath.stem


def extract_tags(content: str) -> str:
    """Return all #tags found in the note as a space-separated string."""
    tags = re.findall(r"(?<!\S)#([A-Za-z][A-Za-z0-9_/-]*)", content)
    return " ".join(tags)


def index_vault() -> None:
    if not VAULT_PATH.exists():
        print(f"ERROR: VAULT_PATH does not exist: {VAULT_PATH}", file=sys.stderr)
        sys.exit(1)

    init_db()
    conn = get_connection()

    md_files = list(VAULT_PATH.rglob("*.md"))
    indexed = skipped = 0

    for filepath in md_files:
        rel_path = str(filepath.relative_to(VAULT_PATH))
        mtime = filepath.stat().st_mtime

        existing = conn.execute(
            "SELECT mtime FROM notes_meta WHERE path = ?", (rel_path,)
        ).fetchone()

        if existing and existing["mtime"] == mtime:
            skipped += 1
            continue

        content = filepath.read_text(encoding="utf-8", errors="ignore")
        title = extract_title(content, filepath)
        tags = extract_tags(content)

        # FTS5 doesn't support UPDATE — delete old entry then insert fresh one
        conn.execute("DELETE FROM notes_fts WHERE path = ?", (rel_path,))
        conn.execute(
            "INSERT INTO notes_fts (path, title, body, tags) VALUES (?, ?, ?, ?)",
            (rel_path, title, content, tags),
        )
        conn.execute(
            """INSERT INTO notes_meta (path, mtime, indexed_at)
               VALUES (?, ?, ?)
               ON CONFLICT(path) DO UPDATE
               SET mtime = excluded.mtime, indexed_at = excluded.indexed_at""",
            (rel_path, mtime, time.time()),
        )
        indexed += 1

    conn.commit()
    conn.close()
    print(f"Vault: {VAULT_PATH}")
    print(f"Indexed {indexed} note(s), skipped {skipped} unchanged.")


if __name__ == "__main__":
    index_vault()
