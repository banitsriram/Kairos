"""
Index Claude session summaries (markdown with --- frontmatter) into FTS5.

Reads MEMORY_SESSIONS_PATH (the synced claude-memory `sessions/` directory).
Row path: conv/<filename-stem>. Raw transcripts are NOT read — summaries only.

Run manually or from cron:
  python conversations_indexer.py
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from db import get_connection, init_db, upsert_fts  # noqa: E402

_SESSIONS_PATH = os.getenv("MEMORY_SESSIONS_PATH", "")


def _parse_frontmatter(text: str):
    """Return (meta dict, body) for a markdown file with --- frontmatter.
    Values are kept as raw strings; lists like '[a, b]' stay as-is (fine for search)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")
    meta = {}
    for line in raw.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta, body


def index_conversations(conn=None) -> int:
    own_conn = conn is None
    if own_conn:
        init_db()
        conn = get_connection()

    count = 0
    sessions_dir = Path(_SESSIONS_PATH)
    if _SESSIONS_PATH and sessions_dir.is_dir():
        for f in sorted(sessions_dir.glob("*.md")):
            text = f.read_text(encoding="utf-8", errors="ignore")
            meta, body = _parse_frontmatter(text)
            date = meta.get("date", "")
            projects = meta.get("projects", "")
            title = f"{date} {projects}".strip() or f.stem
            upsert_fts(conn, f"conv/{f.stem}", title, body, f"conversation {projects}".strip())
            count += 1
    else:
        print(f"conversations: MEMORY_SESSIONS_PATH unset or missing ({_SESSIONS_PATH!r}); skipping.")

    conn.commit()
    if own_conn:
        conn.close()
    print(f"Conversations indexed: {count} summary(ies).")
    return count


if __name__ == "__main__":
    index_conversations()
