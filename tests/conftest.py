import os
import sqlite3
import sys

# Make backend/ importable for all tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest


def make_db() -> sqlite3.Connection:
    """In-memory SQLite with the full Kairos schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE notes_meta (
            path TEXT PRIMARY KEY, mtime REAL NOT NULL, indexed_at REAL NOT NULL
        );
        CREATE VIRTUAL TABLE notes_fts USING fts5(
            path, title, body, tags, tokenize = 'porter unicode61'
        );
        CREATE TABLE activity_log (
            date TEXT PRIMARY KEY, opened INTEGER DEFAULT 0, captured INTEGER DEFAULT 0
        );
    """)
    return conn


@pytest.fixture
def db():
    conn = make_db()
    yield conn
    conn.close()
