"""
Kairos Phase 5 — Personality & Daily Experience backend logic.
"""
import random
import re
import sqlite3
from datetime import date, timedelta
from typing import Optional

import yaml

from notion import get_schedule, get_tasks

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


def render_template(line: str, ctx: dict) -> str:
    """Replace {slot} in line with ctx values; leave unknown slots unchanged."""
    def _replace(m: re.Match) -> str:
        key = m.group(1)
        return str(ctx[key]) if key in ctx else m.group(0)

    return re.sub(r"\{(\w+)\}", _replace, line)


def pick_greeting(
    config: dict,
    n_classes: int,
    overdue_count: int,
    neglected_project: Optional[dict],
) -> str:
    """Pick the right bucket, select a random line, render template slots."""
    greetings = config.get("greetings", FALLBACK_CONFIG["greetings"])
    packed_threshold = config.get("context", {}).get(
        "packed_threshold", FALLBACK_CONFIG["context"]["packed_threshold"]
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

    return render_template(random.choice(bucket), ctx)


def compute_streak(conn: sqlite3.Connection) -> dict:
    """
    Count consecutive days (from today backwards) where opened > 0.
    bonus=True if today has captured > 0.
    """
    today = date.today().isoformat()
    rows = conn.execute(
        "SELECT date, opened, captured FROM activity_log WHERE date <= ? ORDER BY date DESC LIMIT 60",
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


def get_on_this_day(
    conn: sqlite3.Connection, month_day: str, current_year: int
) -> list:
    """
    Return vault notes whose filename contains month_day (e.g. '05-30')
    but NOT the current year. Joins notes_fts for title.
    month_day format: 'MM-DD'
    """
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
        (f"%-{month_day}%", f"%{current_year}%"),
    ).fetchall()

    results = []
    for row in rows:
        match = re.search(r"(\d{4})-" + re.escape(month_day), row["path"])
        year = int(match.group(1)) if match else None
        results.append({"path": row["path"], "title": row["title"], "year": year})
    return results


def _get_neglected_project(conn: sqlite3.Connection, neglected_days: int) -> Optional[dict]:
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
    days_ago = int(
        date.today().toordinal() - date.fromtimestamp(row["last_touch"]).toordinal()
    )
    return {"name": row["project"], "days": days_ago}


def gather_context(conn: sqlite3.Connection, config: dict) -> dict:
    """
    Fetch schedule + tasks from Notion and neglected project from DB.
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
