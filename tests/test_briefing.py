import sqlite3
import sys
import os
from datetime import date, timedelta
from unittest.mock import patch
import time as _time
import textwrap

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def _make_db():
    """In-memory SQLite with the full Kairos schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE notes_meta (
            path       TEXT PRIMARY KEY,
            mtime      REAL NOT NULL,
            indexed_at REAL NOT NULL
        );
        CREATE VIRTUAL TABLE notes_fts USING fts5(
            path, title, body, tags,
            tokenize = 'porter unicode61'
        );
        CREATE TABLE activity_log (
            date     TEXT PRIMARY KEY,
            opened   INTEGER DEFAULT 0,
            captured INTEGER DEFAULT 0
        );
    """)
    return conn


# ---------------------------------------------------------------------------
# Task 1 — activity_log schema
# ---------------------------------------------------------------------------

def test_activity_log_schema():
    conn = _make_db()
    today = date.today().isoformat()
    conn.execute(
        "INSERT INTO activity_log (date, opened, captured) VALUES (?, 1, 0)", (today,)
    )
    conn.commit()
    row = conn.execute(
        "SELECT opened, captured FROM activity_log WHERE date = ?", (today,)
    ).fetchone()
    assert row["opened"] == 1
    assert row["captured"] == 0
    conn.close()


# ---------------------------------------------------------------------------
# Task 2 — config loader
# ---------------------------------------------------------------------------

def test_load_config_reads_yaml(tmp_path):
    from briefing import load_config

    cfg_file = tmp_path / "personality.yaml"
    cfg_file.write_text(textwrap.dedent("""
        sass_level: 3
        context:
          packed_threshold: 4
          neglected_days: 5
        greetings:
          default:
            - "Hello."
        motivation:
          - "Go."
    """))
    cfg = load_config(str(cfg_file))
    assert cfg["sass_level"] == 3
    assert cfg["context"]["packed_threshold"] == 4
    assert cfg["greetings"]["default"] == ["Hello."]


def test_load_config_fallback_on_missing():
    from briefing import load_config, FALLBACK_CONFIG

    cfg = load_config("/nonexistent/path/personality.yaml")
    assert cfg == FALLBACK_CONFIG


def test_load_config_fallback_on_invalid_yaml(tmp_path):
    from briefing import load_config, FALLBACK_CONFIG

    bad = tmp_path / "bad.yaml"
    bad.write_text(": this is not: valid: yaml: [[[")
    cfg = load_config(str(bad))
    assert cfg == FALLBACK_CONFIG


# ---------------------------------------------------------------------------
# Task 3 — template renderer
# ---------------------------------------------------------------------------

def test_render_template_fills_slots():
    from briefing import render_template

    result = render_template(
        "You have {n_classes} classes and {overdue} overdue.",
        {"n_classes": 4, "overdue": 2},
    )
    assert result == "You have 4 classes and 2 overdue."


def test_render_template_unknown_slot_left_as_is():
    from briefing import render_template

    result = render_template("Hello {unknown}.", {"n_classes": 1})
    assert result == "Hello {unknown}."


def test_render_template_no_slots():
    from briefing import render_template

    result = render_template("Here's your day.", {})
    assert result == "Here's your day."


# ---------------------------------------------------------------------------
# Task 4 — greeting picker
# ---------------------------------------------------------------------------

def test_pick_greeting_packed_day():
    from briefing import pick_greeting, FALLBACK_CONFIG

    result = pick_greeting(
        config=FALLBACK_CONFIG,
        n_classes=4,
        overdue_count=2,
        neglected_project=None,
    )
    assert "4" in result or "chaos" in result or "Godspeed" in result or "eat" in result


def test_pick_greeting_empty_day():
    from briefing import pick_greeting, FALLBACK_CONFIG

    result = pick_greeting(
        config=FALLBACK_CONFIG,
        n_classes=0,
        overdue_count=0,
        neglected_project=None,
    )
    assert any(phrase in result for phrase in ["Light day", "0 things", "space"])


def test_pick_greeting_neglected_takes_priority():
    from briefing import pick_greeting, FALLBACK_CONFIG

    result = pick_greeting(
        config=FALLBACK_CONFIG,
        n_classes=5,
        overdue_count=0,
        neglected_project={"name": "Kairos", "days": 10},
    )
    assert "Kairos" in result
    assert "10" in result


def test_pick_greeting_default_bucket():
    from briefing import pick_greeting, FALLBACK_CONFIG

    result = pick_greeting(
        config=FALLBACK_CONFIG,
        n_classes=1,
        overdue_count=0,
        neglected_project=None,
    )
    assert result in ["Here's your day.", "Let's get it.", "Make it count."]


# ---------------------------------------------------------------------------
# Task 5 — streak calculator
# ---------------------------------------------------------------------------

def test_streak_consecutive_days():
    from briefing import compute_streak

    conn = _make_db()
    today = date.today()
    for i in range(4):
        d = (today - timedelta(days=i)).isoformat()
        conn.execute("INSERT INTO activity_log (date, opened) VALUES (?, 1)", (d,))
    conn.commit()
    result = compute_streak(conn)
    assert result["count"] == 4
    assert result["bonus"] is False
    conn.close()


def test_streak_gap_resets_count():
    from briefing import compute_streak

    conn = _make_db()
    today = date.today()
    for i in [0, 1, 3, 4]:
        d = (today - timedelta(days=i)).isoformat()
        conn.execute("INSERT INTO activity_log (date, opened) VALUES (?, 1)", (d,))
    conn.commit()
    result = compute_streak(conn)
    assert result["count"] == 2
    conn.close()


def test_streak_bonus_when_captured():
    from briefing import compute_streak

    conn = _make_db()
    today = date.today().isoformat()
    conn.execute(
        "INSERT INTO activity_log (date, opened, captured) VALUES (?, 1, 1)", (today,)
    )
    conn.commit()
    result = compute_streak(conn)
    assert result["count"] == 1
    assert result["bonus"] is True
    conn.close()


def test_streak_zero_when_never_opened():
    from briefing import compute_streak

    conn = _make_db()
    result = compute_streak(conn)
    assert result["count"] == 0
    assert result["bonus"] is False
    conn.close()


# ---------------------------------------------------------------------------
# Task 6 — on-this-day query
# ---------------------------------------------------------------------------

def test_on_this_day_returns_matching_notes():
    from briefing import get_on_this_day

    conn = _make_db()
    today = date.today()
    month_day = today.strftime("%m-%d")
    last_year = today.year - 1
    current_year = today.year

    past_path = f"cs/{last_year}-{month_day}.md"
    conn.execute(
        "INSERT INTO notes_meta (path, mtime, indexed_at) VALUES (?, ?, ?)",
        (past_path, _time.time(), _time.time()),
    )
    conn.execute(
        "INSERT INTO notes_fts (path, title, body, tags) VALUES (?, ?, ?, ?)",
        (past_path, "OS Notes from last year", "content", ""),
    )
    conn.commit()

    results = get_on_this_day(conn, month_day, current_year)
    assert len(results) == 1
    assert results[0]["path"] == past_path
    assert results[0]["title"] == "OS Notes from last year"
    assert results[0]["year"] == last_year
    conn.close()


def test_on_this_day_excludes_current_year():
    from briefing import get_on_this_day

    conn = _make_db()
    today = date.today()
    month_day = today.strftime("%m-%d")
    current_year = today.year

    current_path = f"cs/{current_year}-{month_day}.md"
    conn.execute(
        "INSERT INTO notes_meta (path, mtime, indexed_at) VALUES (?, ?, ?)",
        (current_path, _time.time(), _time.time()),
    )
    conn.execute(
        "INSERT INTO notes_fts (path, title, body, tags) VALUES (?, ?, ?, ?)",
        (current_path, "Today's note", "content", ""),
    )
    conn.commit()

    results = get_on_this_day(conn, month_day, current_year)
    assert results == []
    conn.close()


def test_on_this_day_excludes_notion_paths():
    from briefing import get_on_this_day

    conn = _make_db()
    today = date.today()
    month_day = today.strftime("%m-%d")
    current_year = today.year
    last_year = today.year - 1

    notion_path = f"notion/tasks/abc-{last_year}-{month_day}"
    conn.execute(
        "INSERT INTO notes_meta (path, mtime, indexed_at) VALUES (?, ?, ?)",
        (notion_path, _time.time(), _time.time()),
    )
    conn.execute(
        "INSERT INTO notes_fts (path, title, body, tags) VALUES (?, ?, ?, ?)",
        (notion_path, "Notion task", "content", "notion task"),
    )
    conn.commit()

    results = get_on_this_day(conn, month_day, current_year)
    assert results == []
    conn.close()


# ---------------------------------------------------------------------------
# Task 7 — context gatherer
# ---------------------------------------------------------------------------

def test_gather_context_counts_classes_and_overdue():
    from briefing import gather_context

    conn = _make_db()
    today_str = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    mock_schedule = [
        {"id": "1", "name": "CS101", "date": today_str, "type": "Class", "notes": "", "url": None},
        {"id": "2", "name": "Study", "date": today_str, "type": "Study", "notes": "", "url": None},
    ]
    mock_tasks = [
        {"id": "a", "name": "Task A", "status": "Not started", "priority": "High", "due_date": yesterday, "url": None},
        {"id": "b", "name": "Task B", "status": "Done", "priority": "Low", "due_date": yesterday, "url": None},
        {"id": "c", "name": "Task C", "status": "In progress", "priority": "Medium", "due_date": None, "url": None},
    ]

    with patch("briefing.get_schedule", return_value=mock_schedule), \
         patch("briefing.get_tasks", return_value=mock_tasks):
        ctx = gather_context(conn, {"context": {"neglected_days": 7}})

    assert ctx["n_classes"] == 2
    assert ctx["overdue_count"] == 1
    assert ctx["next_event"]["name"] == "CS101"
    conn.close()


def test_gather_context_detects_neglected_project():
    from briefing import gather_context

    conn = _make_db()
    old_mtime = _time.time() - (10 * 86400)
    conn.execute(
        "INSERT INTO notes_meta (path, mtime, indexed_at) VALUES (?, ?, ?)",
        ("cs/old-note.md", old_mtime, old_mtime),
    )
    conn.commit()

    with patch("briefing.get_schedule", return_value=[]), \
         patch("briefing.get_tasks", return_value=[]):
        ctx = gather_context(conn, {"context": {"neglected_days": 7}})

    assert ctx["neglected_project"] is not None
    assert ctx["neglected_project"]["name"] == "cs"
    assert ctx["neglected_project"]["days"] >= 10
    conn.close()


def test_gather_context_notion_failure_returns_defaults():
    from briefing import gather_context

    conn = _make_db()

    with patch("briefing.get_schedule", side_effect=Exception("Notion down")), \
         patch("briefing.get_tasks", side_effect=Exception("Notion down")):
        ctx = gather_context(conn, {"context": {"neglected_days": 7}})

    assert ctx["n_classes"] == 0
    assert ctx["overdue_count"] == 0
    assert ctx["next_event"] is None
    conn.close()


# ---------------------------------------------------------------------------
# Task 8 — build_briefing assembler
# ---------------------------------------------------------------------------

def test_build_briefing_shape():
    from briefing import build_briefing, FALLBACK_CONFIG

    conn = _make_db()

    with patch("briefing.get_schedule", return_value=[]), \
         patch("briefing.get_tasks", return_value=[]):
        result = build_briefing(conn, FALLBACK_CONFIG)

    assert "greeting" in result
    assert "sass_level" in result
    assert "context" in result
    assert "streak" in result
    assert "on_this_day" in result
    assert isinstance(result["greeting"], str)
    assert isinstance(result["streak"]["count"], int)
    assert isinstance(result["on_this_day"], list)
    conn.close()


# ---------------------------------------------------------------------------
# Task 9 — FastAPI routes integration tests
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.setenv("PERSONALITY_CONFIG", str(tmp_path / "personality.yaml"))

    import importlib
    import db as _db
    import main as _main
    importlib.reload(_db)
    importlib.reload(_main)

    from fastapi.testclient import TestClient
    with TestClient(_main.app) as c:
        yield c


def test_heartbeat_returns_ok(client):
    r = client.post("/heartbeat")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_briefing_returns_expected_shape(client):
    with patch("briefing.get_schedule", return_value=[]), \
         patch("briefing.get_tasks", return_value=[]):
        r = client.get("/briefing")
    assert r.status_code == 200
    body = r.json()
    assert "greeting" in body
    assert "streak" in body
    assert "on_this_day" in body
    assert "context" in body


def test_capture_increments_streak_bonus(client, tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setenv("VAULT_PATH", str(vault))

    client.post("/heartbeat")
    r = client.post("/capture", json={"text": "Test capture note."})
    assert r.status_code == 201

    with patch("briefing.get_schedule", return_value=[]), \
         patch("briefing.get_tasks", return_value=[]):
        r2 = client.get("/briefing")
    assert r2.json()["streak"]["bonus"] is True
