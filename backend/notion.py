"""
Thin client for the two Notion databases: Tasks and Schedule.
Reads NOTION_TOKEN, NOTION_TASKS_DB, NOTION_SCHEDULE_DB from environment.
"""
import os
from typing import Any, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

_TOKEN = os.getenv("NOTION_TOKEN", "")
_TASKS_DB = os.getenv("NOTION_TASKS_DB", "")
_SCHEDULE_DB = os.getenv("NOTION_SCHEDULE_DB", "")

_HEADERS = {
    "Authorization": f"Bearer {_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def _query_db(database_id: str, filter_body: Optional[dict] = None) -> list[dict]:
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    payload: dict[str, Any] = {"page_size": 100}
    if filter_body:
        payload["filter"] = filter_body

    results = []
    while True:
        resp = requests.post(url, headers=_HEADERS, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data["next_cursor"]

    return results


def _text(prop: dict) -> str:
    items = prop.get("rich_text") or prop.get("title") or []
    return "".join(t.get("plain_text", "") for t in items)


def _select(prop: dict) -> Optional[str]:
    sel = prop.get("select")
    return sel["name"] if sel else None


def _date(prop: dict) -> Optional[str]:
    d = prop.get("date")
    return d["start"] if d else None


def get_tasks(status: Optional[str] = None) -> list[dict]:
    filter_body = None
    if status:
        filter_body = {"property": "Status", "select": {"equals": status}}

    rows = _query_db(_TASKS_DB, filter_body)
    tasks = []
    for r in rows:
        p = r["properties"]
        tasks.append({
            "id": r["id"],
            "name": _text(p["Name"]),
            "status": _select(p["Status"]),
            "priority": _select(p["Priority"]),
            "due_date": _date(p["Due Date"]),
            "url": r.get("url"),
        })
    return tasks


def get_schedule(date: Optional[str] = None) -> list[dict]:
    filter_body = None
    if date:
        filter_body = {"property": "Date", "date": {"equals": date}}

    rows = _query_db(_SCHEDULE_DB, filter_body)
    items = []
    for r in rows:
        p = r["properties"]
        items.append({
            "id": r["id"],
            "name": _text(p["Name"]),
            "date": _date(p["Date"]),
            "type": _select(p["Type"]),
            "notes": _text(p["Notes"]),
            "url": r.get("url"),
        })
    return items


def get_today() -> dict:
    """
    Returns a summary for the current day:
      - schedule: today's events sorted by date
      - top_tasks: up to 3 non-done tasks sorted by priority then due date
      - neglected: the oldest-due Not-started task (the one most overdue/ignored)
    """
    from datetime import date as _date_type

    today = _date_type.today().isoformat()

    # Priority sort order — High first
    _priority_rank = {"High": 0, "Medium": 1, "Low": 2, None: 3}

    # Today's schedule
    schedule = sorted(
        get_schedule(date=today),
        key=lambda e: e["date"] or "",
    )

    # All non-done tasks
    all_tasks = [t for t in get_tasks() if t["status"] != "Done"]

    # Top 3: sort by (priority rank, due_date) — tasks with no due date go last
    top_tasks = sorted(
        all_tasks,
        key=lambda t: (_priority_rank.get(t["priority"], 3), t["due_date"] or "9999"),
    )[:3]

    # Neglected: Not-started task with the earliest (oldest) due date
    not_started = [t for t in all_tasks if t["status"] == "Not started" and t["due_date"]]
    neglected = min(not_started, key=lambda t: t["due_date"]) if not_started else None

    return {
        "date": today,
        "schedule": schedule,
        "top_tasks": top_tasks,
        "neglected": neglected,
    }
