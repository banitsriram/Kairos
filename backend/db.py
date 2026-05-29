import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_PROJECT_ROOT = Path(__file__).parent.parent  # backend/ → kairos/


def _resolve(env_key: str, default: str) -> Path:
    """Resolve a path from env. Relative paths are anchored to the project root."""
    raw = os.getenv(env_key, default)
    p = Path(raw)
    return p if p.is_absolute() else (_PROJECT_ROOT / p).resolve()


DB_PATH = _resolve("DB_PATH", "data/brain.db")


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS notes_meta (
            path        TEXT PRIMARY KEY,
            mtime       REAL NOT NULL,
            indexed_at  REAL NOT NULL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
            path,
            title,
            body,
            tags,
            tokenize = 'porter unicode61'
        );

        CREATE TABLE IF NOT EXISTS activity_log (
            date     TEXT PRIMARY KEY,
            opened   INTEGER DEFAULT 0,
            captured INTEGER DEFAULT 0
        );
    """)
    conn.commit()
    conn.close()
