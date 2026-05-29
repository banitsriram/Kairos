"""
Pull Notion tasks and schedule items into the same SQLite FTS5 index as the
Obsidian vault, so /search covers both sources in one query.

Each Notion entry gets a synthetic path:
  notion/tasks/<id>
  notion/schedule/<id>

This prefix lets the frontend (and you) tell Obsidian notes from Notion entries
at a glance in search results.

Run manually or after a Notion sync:
  python notion_indexer.py
"""
import sys
import time

from db import get_connection, init_db
from notion import get_schedule, get_tasks


def _upsert(conn, path: str, title: str, body: str, tags: str) -> None:
    # FTS5 doesn't support UPDATE — delete stale entry then insert fresh one.
    # Same pattern as the Obsidian indexer.
    conn.execute("DELETE FROM notes_fts WHERE path = ?", (path,))
    conn.execute(
        "INSERT INTO notes_fts (path, title, body, tags) VALUES (?, ?, ?, ?)",
        (path, title, body, tags),
    )
    conn.execute(
        """INSERT INTO notes_meta (path, mtime, indexed_at)
           VALUES (?, ?, ?)
           ON CONFLICT(path) DO UPDATE
           SET mtime = excluded.mtime, indexed_at = excluded.indexed_at""",
        (path, time.time(), time.time()),
    )


def index_notion() -> None:
    init_db()
    conn = get_connection()
    tasks_indexed = sched_indexed = 0

    # --- Tasks ---
    for task in get_tasks():
        path = f"notion/tasks/{task['id']}"
        title = task["name"]
        # Build a text body so the content is searchable
        parts = [title]
        if task["status"]:
            parts.append(f"Status: {task['status']}")
        if task["priority"]:
            parts.append(f"Priority: {task['priority']}")
        if task["due_date"]:
            parts.append(f"Due: {task['due_date']}")
        body = "\n".join(parts)
        tags = "notion task"
        _upsert(conn, path, title, body, tags)
        tasks_indexed += 1

    # --- Schedule ---
    for event in get_schedule():
        path = f"notion/schedule/{event['id']}"
        title = event["name"]
        parts = [title]
        if event["date"]:
            parts.append(f"Date: {event['date']}")
        if event["type"]:
            parts.append(f"Type: {event['type']}")
        if event["notes"]:
            parts.append(event["notes"])
        body = "\n".join(parts)
        tags = f"notion schedule {(event['type'] or '').lower()}".strip()
        _upsert(conn, path, title, body, tags)
        sched_indexed += 1

    conn.commit()
    conn.close()
    print(f"Notion indexed: {tasks_indexed} task(s), {sched_indexed} schedule item(s).")


if __name__ == "__main__":
    index_notion()
