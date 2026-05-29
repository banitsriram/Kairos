# Phase 5 Backend — Personality & Daily Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `/briefing` and `/heartbeat` endpoints to Kairos that deliver a context-aware personality greeting, streak tracking, and on-this-day vault notes.

**Architecture:** All Phase 5 logic lives in a single new module `backend/briefing.py`. `main.py` adds two thin route handlers that call into it. A new `activity_log` SQLite table tracks daily opens and captures for streak computation.

**Tech Stack:** Python 3.9, FastAPI, SQLite (FTS5), PyYAML, pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/requirements.txt` | Modify | Add PyYAML |
| `backend/db.py` | Modify | Add `activity_log` table to `init_db()` |
| `backend/briefing.py` | Create | All Phase 5 logic: config loader, template renderer, greeting picker, streak calculator, on-this-day query, context gatherer, response assembler |
| `backend/personality.yaml` | Create | Default personality config — committed to repo |
| `backend/main.py` | Modify | Add `GET /briefing`, `POST /heartbeat` routes; increment `captured` in `POST /capture` |
| `tests/test_briefing.py` | Create | All unit + integration tests |

---

## Task 1: Add PyYAML and `activity_log` table

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/db.py:29-45`
- Test: `tests/test_briefing.py` (scaffold only)

- [ ] **Step 1: Add PyYAML to requirements**

Edit `backend/requirements.txt` to add the new line:

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
python-dotenv==1.0.1
requests==2.32.3
PyYAML==6.0.2
```

- [ ] **Step 2: Install it**

```bash
cd /Users/banit/Kairos
source .venv/bin/activate
pip install PyYAML==6.0.2
```

Expected: `Successfully installed PyYAML-6.0.2`

- [ ] **Step 3: Write the failing test for activity_log schema**

Create `tests/test_briefing.py`:

```python
import sqlite3
import sys
import os
from datetime import date

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
```

- [ ] **Step 4: Run test — it should PASS already** (schema is in `_make_db`, not testing `db.py` yet)

```bash
cd /Users/banit/Kairos
source .venv/bin/activate
pytest tests/test_briefing.py::test_activity_log_schema -v
```

Expected: PASS

- [ ] **Step 5: Add `activity_log` to `db.py`'s `init_db()`**

In `backend/db.py`, update the `executescript` to add the new table after `notes_fts`:

```python
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
```

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/db.py tests/test_briefing.py
git commit -m "feat: add activity_log table and PyYAML dependency"
```

---

## Task 2: Config loader

**Files:**
- Create: `backend/briefing.py`
- Modify: `tests/test_briefing.py`

- [ ] **Step 1: Write failing tests for config loader**

Append to `tests/test_briefing.py`:

```python
import tempfile
import textwrap


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
```

- [ ] **Step 2: Run — expect ImportError (module doesn't exist yet)**

```bash
pytest tests/test_briefing.py::test_load_config_reads_yaml -v
```

Expected: `ModuleNotFoundError: No module named 'briefing'`

- [ ] **Step 3: Create `backend/briefing.py` with config loader**

```python
"""
Kairos Phase 5 — Personality & Daily Experience backend logic.
"""
import os
import random
import re
import sqlite3
from datetime import date
from typing import Optional

import yaml

FALLBACK_CONFIG: dict = {
    "sass_level": 2,
    "context": {"packed_threshold": 3, "neglected_days": 7},
    "greetings": {
        "packed_day": [
            "You have {n_classes} classes today. Godspeed.",
            "{n_classes} classes and {overdue} overdue. You love chaos.",
            "Packed schedule. Remember to eat.",
        ],
        "empty_day": [
            "Light day. Don't waste it.",
            "Only {n_classes} things scheduled. No excuses.",
            "You've got space to think. Use it.",
        ],
        "project_neglected": [
            "{project} misses you. It's been {days} days.",
            "You haven't touched {project} in {days} days. Just saying.",
            "{project} is gathering dust. {days} days.",
        ],
        "default": ["Here's your day.", "Let's get it.", "Make it count."],
    },
    "motivation": [
        "Small steps compound.",
        "You showed up. That's already something.",
        "Progress, not perfection.",
    ],
}


def load_config(path: str) -> dict:
    """Load personality.yaml; return FALLBACK_CONFIG on any error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        if not isinstance(cfg, dict):
            return FALLBACK_CONFIG
        return cfg
    except Exception:
        return FALLBACK_CONFIG
```

- [ ] **Step 4: Run tests — all three should PASS**

```bash
pytest tests/test_briefing.py::test_load_config_reads_yaml \
       tests/test_briefing.py::test_load_config_fallback_on_missing \
       tests/test_briefing.py::test_load_config_fallback_on_invalid_yaml -v
```

Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/briefing.py tests/test_briefing.py
git commit -m "feat: briefing config loader with YAML fallback"
```

---

## Task 3: Template renderer

**Files:**
- Modify: `backend/briefing.py`
- Modify: `tests/test_briefing.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_briefing.py`:

```python
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
```

- [ ] **Step 2: Run — expect AttributeError (function not defined)**

```bash
pytest tests/test_briefing.py::test_render_template_fills_slots -v
```

Expected: `ImportError` or `AttributeError`

- [ ] **Step 3: Add `render_template` to `backend/briefing.py`**

Add after `load_config`:

```python
def render_template(line: str, ctx: dict) -> str:
    """Replace {slot} in line with ctx values; leave unknown slots unchanged."""
    def _replace(m: re.Match) -> str:
        key = m.group(1)
        return str(ctx[key]) if key in ctx else m.group(0)

    return re.sub(r"\{(\w+)\}", _replace, line)
```

- [ ] **Step 4: Run — all three PASS**

```bash
pytest tests/test_briefing.py::test_render_template_fills_slots \
       tests/test_briefing.py::test_render_template_unknown_slot_left_as_is \
       tests/test_briefing.py::test_render_template_no_slots -v
```

Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/briefing.py tests/test_briefing.py
git commit -m "feat: template slot renderer"
```

---

## Task 4: Greeting picker

**Files:**
- Modify: `backend/briefing.py`
- Modify: `tests/test_briefing.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_briefing.py`:

```python
def test_pick_greeting_packed_day():
    from briefing import pick_greeting, FALLBACK_CONFIG

    # n_classes=4 >= packed_threshold=3 → packed_day bucket
    result = pick_greeting(
        config=FALLBACK_CONFIG,
        n_classes=4,
        overdue_count=2,
        neglected_project=None,
    )
    # Must be one of the packed_day lines (with slots rendered)
    assert "4" in result or "chaos" in result or "Godspeed" in result or "eat" in result


def test_pick_greeting_empty_day():
    from briefing import pick_greeting, FALLBACK_CONFIG

    result = pick_greeting(
        config=FALLBACK_CONFIG,
        n_classes=0,
        overdue_count=0,
        neglected_project=None,
    )
    assert any(
        phrase in result
        for phrase in ["Light day", "0 things", "space"]
    )


def test_pick_greeting_neglected_takes_priority():
    from briefing import pick_greeting, FALLBACK_CONFIG

    # Even with packed day, neglected project wins
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

    # n_classes=1 → not packed, not empty → default
    result = pick_greeting(
        config=FALLBACK_CONFIG,
        n_classes=1,
        overdue_count=0,
        neglected_project=None,
    )
    assert result in ["Here's your day.", "Let's get it.", "Make it count."]
```

- [ ] **Step 2: Run — expect ImportError**

```bash
pytest tests/test_briefing.py::test_pick_greeting_packed_day -v
```

Expected: `ImportError`

- [ ] **Step 3: Add `pick_greeting` to `backend/briefing.py`**

```python
def pick_greeting(
    config: dict,
    n_classes: int,
    overdue_count: int,
    neglected_project: Optional[dict],
) -> str:
    """Pick the right bucket, select a random line, render template slots."""
    greetings = config.get("greetings", FALLBACK_CONFIG["greetings"])
    packed_threshold = config.get("context", {}).get(
        "packed_threshold",
        FALLBACK_CONFIG["context"]["packed_threshold"],
    )

    if neglected_project:
        bucket = greetings.get("project_neglected", FALLBACK_CONFIG["greetings"]["project_neglected"])
        ctx = {
            "project": neglected_project["name"],
            "days": neglected_project["days"],
            "n_classes": n_classes,
            "overdue": overdue_count,
        }
    elif n_classes >= packed_threshold:
        bucket = greetings.get("packed_day", FALLBACK_CONFIG["greetings"]["packed_day"])
        ctx = {"n_classes": n_classes, "overdue": overdue_count}
    elif n_classes == 0:
        bucket = greetings.get("empty_day", FALLBACK_CONFIG["greetings"]["empty_day"])
        ctx = {"n_classes": n_classes, "overdue": overdue_count}
    else:
        bucket = greetings.get("default", FALLBACK_CONFIG["greetings"]["default"])
        ctx = {"n_classes": n_classes, "overdue": overdue_count}

    line = random.choice(bucket)
    return render_template(line, ctx)
```

- [ ] **Step 4: Run — all four PASS**

```bash
pytest tests/test_briefing.py::test_pick_greeting_packed_day \
       tests/test_briefing.py::test_pick_greeting_empty_day \
       tests/test_briefing.py::test_pick_greeting_neglected_takes_priority \
       tests/test_briefing.py::test_pick_greeting_default_bucket -v
```

Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/briefing.py tests/test_briefing.py
git commit -m "feat: context-aware greeting bucket picker"
```

---

## Task 5: Streak calculator

**Files:**
- Modify: `backend/briefing.py`
- Modify: `tests/test_briefing.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_briefing.py`:

```python
from datetime import date, timedelta


def test_streak_consecutive_days():
    from briefing import compute_streak

    conn = _make_db()
    today = date.today()
    for i in range(4):
        d = (today - timedelta(days=i)).isoformat()
        conn.execute(
            "INSERT INTO activity_log (date, opened) VALUES (?, 1)", (d,)
        )
    conn.commit()
    result = compute_streak(conn)
    assert result["count"] == 4
    assert result["bonus"] is False
    conn.close()


def test_streak_gap_resets_count():
    from briefing import compute_streak

    conn = _make_db()
    today = date.today()
    # Days 0, 1 open — gap on day 2 — days 3, 4 open
    for i in [0, 1, 3, 4]:
        d = (today - timedelta(days=i)).isoformat()
        conn.execute(
            "INSERT INTO activity_log (date, opened) VALUES (?, 1)", (d,)
        )
    conn.commit()
    result = compute_streak(conn)
    assert result["count"] == 2  # only today + yesterday; gap breaks chain
    conn.close()


def test_streak_bonus_when_captured():
    from briefing import compute_streak

    conn = _make_db()
    today = date.today().isoformat()
    conn.execute(
        "INSERT INTO activity_log (date, opened, captured) VALUES (?, 1, 1)",
        (today,),
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
```

- [ ] **Step 2: Run — expect ImportError**

```bash
pytest tests/test_briefing.py::test_streak_consecutive_days -v
```

Expected: `ImportError`

- [ ] **Step 3: Add `compute_streak` to `backend/briefing.py`**

```python
def compute_streak(conn: sqlite3.Connection) -> dict:
    """
    Count consecutive days (from today backwards) where opened > 0.
    bonus=True if today has captured > 0.
    """
    today = date.today().isoformat()
    rows = conn.execute(
        """
        SELECT date, opened, captured FROM activity_log
        WHERE date <= ?
        ORDER BY date DESC
        LIMIT 60
        """,
        (today,),
    ).fetchall()

    if not rows:
        return {"count": 0, "bonus": False}

    bonus = rows[0]["captured"] > 0 if rows[0]["date"] == today else False

    count = 0
    expected = date.today()
    for row in rows:
        row_date = date.fromisoformat(row["date"])
        if row_date == expected and row["opened"] > 0:
            count += 1
            expected = expected - timedelta(days=1)
        else:
            break

    return {"count": count, "bonus": bonus}
```

Also add `from datetime import date, timedelta` to the imports at the top of `briefing.py` (update the existing `from datetime import date` line).

- [ ] **Step 4: Run — all four PASS**

```bash
pytest tests/test_briefing.py::test_streak_consecutive_days \
       tests/test_briefing.py::test_streak_gap_resets_count \
       tests/test_briefing.py::test_streak_bonus_when_captured \
       tests/test_briefing.py::test_streak_zero_when_never_opened -v
```

Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/briefing.py tests/test_briefing.py
git commit -m "feat: streak calculator with bonus flag"
```

---

## Task 6: On-this-day query

**Files:**
- Modify: `backend/briefing.py`
- Modify: `tests/test_briefing.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_briefing.py`:

```python
import time as _time


def test_on_this_day_returns_matching_notes():
    from briefing import get_on_this_day

    conn = _make_db()
    today = date.today()
    month_day = today.strftime("%m-%d")
    last_year = today.year - 1
    current_year = today.year

    # Matching note from last year
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

    # Note from current year — should be excluded
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

    # Notion path — should not appear
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
```

- [ ] **Step 2: Run — expect ImportError**

```bash
pytest tests/test_briefing.py::test_on_this_day_returns_matching_notes -v
```

Expected: `ImportError`

- [ ] **Step 3: Add `get_on_this_day` to `backend/briefing.py`**

```python
def get_on_this_day(
    conn: sqlite3.Connection, month_day: str, current_year: int
) -> list[dict]:
    """
    Return vault notes whose filename contains month_day (e.g. '05-30')
    but NOT the current year. Joins notes_fts for title.
    month_day format: 'MM-DD'
    """
    pattern = f"%-{month_day}%"
    exclude = f"%-{current_year}-%"
    rows = conn.execute(
        """
        SELECT m.path, f.title, m.mtime
        FROM notes_meta m
        JOIN notes_fts f ON f.path = m.path
        WHERE m.path NOT LIKE 'notion/%'
          AND m.path LIKE ?
          AND m.path NOT LIKE ?
        ORDER BY m.mtime DESC
        LIMIT 5
        """,
        (pattern, exclude),
    ).fetchall()

    results = []
    for row in rows:
        # Extract year from path: look for 4-digit year before the month-day
        match = re.search(r"(\d{4})-" + re.escape(month_day), row["path"])
        year = int(match.group(1)) if match else None
        results.append({"path": row["path"], "title": row["title"], "year": year})
    return results
```

- [ ] **Step 4: Run — all three PASS**

```bash
pytest tests/test_briefing.py::test_on_this_day_returns_matching_notes \
       tests/test_briefing.py::test_on_this_day_excludes_current_year \
       tests/test_briefing.py::test_on_this_day_excludes_notion_paths -v
```

Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/briefing.py tests/test_briefing.py
git commit -m "feat: on-this-day vault query"
```

---

## Task 7: Context gatherer and neglected-project query

**Files:**
- Modify: `backend/briefing.py`
- Modify: `tests/test_briefing.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_briefing.py`:

```python
from unittest.mock import patch


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
    assert ctx["overdue_count"] == 1  # only Task A: not Done and due yesterday
    assert ctx["next_event"]["name"] == "CS101"
    conn.close()


def test_gather_context_detects_neglected_project():
    from briefing import gather_context

    conn = _make_db()
    # Insert a note last touched 10 days ago in project "cs"
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
```

- [ ] **Step 2: Run — expect ImportError**

```bash
pytest tests/test_briefing.py::test_gather_context_counts_classes_and_overdue -v
```

Expected: `ImportError`

- [ ] **Step 3: Add `gather_context` to `backend/briefing.py`**

Add `from notion import get_schedule, get_tasks` to the imports, then:

```python
def _get_neglected_project(
    conn: sqlite3.Connection, neglected_days: int
) -> Optional[dict]:
    """Return the most-neglected vault project subfolder, or None."""
    row = conn.execute(
        """
        SELECT substr(path, 1, instr(path, '/') - 1) AS project,
               MAX(mtime) AS last_touch
        FROM notes_meta
        WHERE path NOT LIKE 'notion/%'
          AND path LIKE '%/%'
        GROUP BY project
        HAVING (strftime('%s','now') - last_touch) / 86400.0 >= ?
        ORDER BY last_touch ASC
        LIMIT 1
        """,
        (neglected_days,),
    ).fetchone()
    if not row:
        return None
    days_ago = int((date.today().toordinal() -
                    date.fromtimestamp(row["last_touch"]).toordinal()))
    return {"name": row["project"], "days": days_ago}


def gather_context(conn: sqlite3.Connection, config: dict) -> dict:
    """
    Fetch schedule + tasks from Notion and neglected project from DB.
    Returns context dict for greeting picker and /briefing response.
    Gracefully degrades if Notion is unavailable.
    """
    today = date.today().isoformat()
    neglected_days = config.get("context", {}).get(
        "neglected_days", FALLBACK_CONFIG["context"]["neglected_days"]
    )

    try:
        schedule = get_schedule(date=today)
        all_tasks = get_tasks()
    except Exception:
        schedule, all_tasks = [], []

    overdue = [
        t for t in all_tasks
        if t["status"] != "Done" and t["due_date"] and t["due_date"] < today
    ]

    next_event = schedule[0] if schedule else None
    neglected_project = _get_neglected_project(conn, neglected_days)

    return {
        "n_classes": len(schedule),
        "next_event": (
            {"name": next_event["name"], "date": next_event["date"], "type": next_event["type"]}
            if next_event else None
        ),
        "overdue_count": len(overdue),
        "neglected_project": neglected_project,
    }
```

- [ ] **Step 4: Run — all three PASS**

```bash
pytest tests/test_briefing.py::test_gather_context_counts_classes_and_overdue \
       tests/test_briefing.py::test_gather_context_detects_neglected_project \
       tests/test_briefing.py::test_gather_context_notion_failure_returns_defaults -v
```

Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/briefing.py tests/test_briefing.py
git commit -m "feat: context gatherer with neglected-project detection"
```

---

## Task 8: `build_briefing` assembler and `personality.yaml`

**Files:**
- Modify: `backend/briefing.py`
- Create: `backend/personality.yaml`
- Modify: `tests/test_briefing.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_briefing.py`:

```python
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
```

- [ ] **Step 2: Run — expect ImportError**

```bash
pytest tests/test_briefing.py::test_build_briefing_shape -v
```

Expected: `ImportError`

- [ ] **Step 3: Add `build_briefing` to `backend/briefing.py`**

```python
def build_briefing(conn: sqlite3.Connection, config: dict) -> dict:
    """Assemble the full /briefing response."""
    ctx = gather_context(conn, config)
    greeting = pick_greeting(
        config=config,
        n_classes=ctx["n_classes"],
        overdue_count=ctx["overdue_count"],
        neglected_project=ctx["neglected_project"],
    )
    streak = compute_streak(conn)
    today = date.today()
    on_this_day = get_on_this_day(conn, today.strftime("%m-%d"), today.year)

    return {
        "greeting": greeting,
        "sass_level": config.get("sass_level", FALLBACK_CONFIG["sass_level"]),
        "context": ctx,
        "streak": streak,
        "on_this_day": on_this_day,
    }
```

- [ ] **Step 4: Run — PASS**

```bash
pytest tests/test_briefing.py::test_build_briefing_shape -v
```

Expected: PASS

- [ ] **Step 5: Create `backend/personality.yaml`**

```yaml
sass_level: 2  # 1–5 (returned in /briefing for frontend use; filtering by sass level is future scope)

context:
  packed_threshold: 3   # schedule events >= this → "packed day" bucket
  neglected_days: 7     # days without vault activity → "project neglected" bucket

greetings:
  packed_day:
    - "You have {n_classes} classes today. Godspeed."
    - "{n_classes} classes and {overdue} overdue. You love chaos."
    - "Packed schedule. Remember to eat."
  empty_day:
    - "Light day. Don't waste it."
    - "Only {n_classes} things scheduled. No excuses."
    - "You've got space to think. Use it."
  project_neglected:
    - "{project} misses you. It's been {days} days."
    - "You haven't touched {project} in {days} days. Just saying."
    - "{project} is gathering dust. {days} days."
  default:
    - "Here's your day."
    - "Let's get it."
    - "Make it count."

motivation:
  - "Small steps compound."
  - "You showed up. That's already something."
  - "Progress, not perfection."
```

- [ ] **Step 6: Run all tests so far**

```bash
pytest tests/test_briefing.py -v
```

Expected: All PASS (16 tests)

- [ ] **Step 7: Commit**

```bash
git add backend/briefing.py backend/personality.yaml tests/test_briefing.py
git commit -m "feat: build_briefing assembler and default personality config"
```

---

## Task 9: Wire up routes in `main.py`

**Files:**
- Modify: `backend/main.py`
- Modify: `tests/test_briefing.py`

- [ ] **Step 1: Write failing integration tests**

Append to `tests/test_briefing.py`:

```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Point DB to a temp file so tests don't touch data/brain.db
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.setenv(
        "PERSONALITY_CONFIG",
        str(tmp_path / "personality.yaml"),  # missing → uses FALLBACK_CONFIG
    )

    # Re-import app after env vars are set
    import importlib
    import db as _db
    import main as _main
    importlib.reload(_db)
    importlib.reload(_main)

    return TestClient(_main.app)


def test_heartbeat_increments_opened(client, monkeypatch):
    with patch("briefing.get_schedule", return_value=[]), \
         patch("briefing.get_tasks", return_value=[]):
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


def test_capture_increments_captured(client, tmp_path):
    # First heartbeat so activity_log row exists
    with patch("briefing.get_schedule", return_value=[]), \
         patch("briefing.get_tasks", return_value=[]):
        client.post("/heartbeat")

    vault = tmp_path / "vault"
    vault.mkdir()
    import os
    os.environ["VAULT_PATH"] = str(vault)

    r = client.post("/capture", json={"text": "Test capture note."})
    assert r.status_code == 201

    # Streak bonus should now be True
    with patch("briefing.get_schedule", return_value=[]), \
         patch("briefing.get_tasks", return_value=[]):
        r2 = client.get("/briefing")
    assert r2.json()["streak"]["bonus"] is True
```

- [ ] **Step 2: Run — expect 404/errors (routes not added yet)**

```bash
pytest tests/test_briefing.py::test_heartbeat_increments_opened \
       tests/test_briefing.py::test_briefing_returns_expected_shape -v
```

Expected: FAIL (404)

- [ ] **Step 3: Add routes and capture increment to `backend/main.py`**

Add imports near the top of `main.py` (after existing imports):

```python
from briefing import build_briefing, load_config
```

Add this near the top with the other `os.getenv` calls (after `load_dotenv()`):

```python
_PERSONALITY_CONFIG = os.getenv("PERSONALITY_CONFIG", str(Path(__file__).parent / "personality.yaml"))
```

Add the two new routes after the existing `/today` route:

```python
@app.post("/heartbeat", status_code=200)
def heartbeat():
    """Record that the app was opened today. Fire-and-forget — never errors."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO activity_log (date, opened, captured) VALUES (?, 1, 0)
            ON CONFLICT(date) DO UPDATE SET opened = opened + 1
            """,
            (today,),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass
    return {"ok": True}


@app.get("/briefing")
def briefing():
    config = load_config(_PERSONALITY_CONFIG)
    conn = get_connection()
    try:
        return build_briefing(conn, config)
    finally:
        conn.close()
```

Update the existing `POST /capture` route — add the captured increment inside the route, just before `return`:

```python
    # Increment today's captured count for streak bonus
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        cap_conn = get_connection()
        cap_conn.execute(
            """
            INSERT INTO activity_log (date, opened, captured) VALUES (?, 0, 1)
            ON CONFLICT(date) DO UPDATE SET captured = captured + 1
            """,
            (today_str,),
        )
        cap_conn.commit()
        cap_conn.close()
    except Exception:
        pass

    return {"path": str(filename.relative_to(vault_path)), "title": title}
```

Also ensure `datetime` is imported — it already is at the top of `main.py` (`from datetime import datetime`).

- [ ] **Step 4: Run all integration tests**

```bash
pytest tests/test_briefing.py::test_heartbeat_increments_opened \
       tests/test_briefing.py::test_briefing_returns_expected_shape \
       tests/test_briefing.py::test_capture_increments_captured -v
```

Expected: 3 PASS

- [ ] **Step 5: Run the full test suite**

```bash
pytest tests/test_briefing.py -v
```

Expected: All 19 tests PASS

- [ ] **Step 6: Smoke-test the live server**

```bash
cd /Users/banit/Kairos/backend
source ../.venv/bin/activate
python indexer.py            # index sample vault first
uvicorn main:app --reload --port 8000 &
sleep 2
curl -s -X POST http://localhost:8000/heartbeat | python3 -m json.tool
curl -s http://localhost:8000/briefing | python3 -m json.tool
```

Expected: heartbeat returns `{"ok": true}`, briefing returns JSON with `greeting`, `streak`, `on_this_day`, `context`.

- [ ] **Step 7: Kill the dev server and commit**

```bash
kill %1 2>/dev/null || true
git add backend/main.py tests/test_briefing.py
git commit -m "feat: add /briefing and /heartbeat routes, capture streak increment"
```

---

## Self-Review Checklist (run before handing off)

- [ ] All spec requirements covered:
  - `GET /briefing` ✓ (Task 9)
  - `POST /heartbeat` ✓ (Task 9)
  - `activity_log` schema ✓ (Task 1)
  - Config loader + YAML ✓ (Task 2)
  - Template renderer ✓ (Task 3)
  - Greeting picker with 4 buckets ✓ (Task 4)
  - Streak calculator + bonus ✓ (Task 5)
  - On-this-day query ✓ (Task 6)
  - Context gatherer + neglected project ✓ (Task 7)
  - `build_briefing` assembler ✓ (Task 8)
  - `personality.yaml` default config ✓ (Task 8)
  - Capture increment ✓ (Task 9)
  - Notion graceful degradation ✓ (Task 7 + 9)
- [ ] No placeholder text anywhere in plan
- [ ] Function names consistent: `load_config`, `render_template`, `pick_greeting`, `compute_streak`, `get_on_this_day`, `gather_context`, `_get_neglected_project`, `build_briefing` used consistently across all tasks
