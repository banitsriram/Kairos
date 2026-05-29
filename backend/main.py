import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from briefing import build_briefing, load_config  # noqa: E402

_PERSONALITY_CONFIG = os.getenv(
    "PERSONALITY_CONFIG", str(Path(__file__).parent / "personality.yaml")
)

from db import get_connection, init_db  # noqa: E402
from notion import get_schedule, get_tasks, get_today  # noqa: E402

app = FastAPI(title="Kairos API", version="0.1.0")

# Permissive CORS for now — tightened in Phase 4 to the Tailscale hostname
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/search")
def search(q: str = Query(..., min_length=1, description="Search query")):
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                path,
                title,
                snippet(notes_fts, 2, '<mark>', '</mark>', '…', 24) AS snippet,
                bm25(notes_fts) AS score
            FROM notes_fts
            WHERE notes_fts MATCH ?
            ORDER BY score
            LIMIT 20
            """,
            (q,),
        ).fetchall()
    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=400, detail=f"Invalid query syntax: {e}")
    finally:
        conn.close()

    return {
        "query": q,
        "total": len(rows),
        "results": [
            {
                "path": r["path"],
                "title": r["title"],
                "snippet": r["snippet"],
                # bm25() is negative (more negative = better). Flip so higher = more relevant.
                "score": round(-r["score"], 4),
            }
            for r in rows
        ],
    }


@app.get("/tasks")
def tasks(status: Optional[str] = Query(None, description="Filter by status, e.g. 'In Progress'")):
    try:
        return {"results": get_tasks(status=status)}
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Notion error: {e}")


@app.get("/schedule")
def schedule(date: Optional[str] = Query(None, description="Filter by date, ISO format e.g. 2026-05-28")):
    try:
        return {"results": get_schedule(date=date)}
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Notion error: {e}")


@app.get("/today")
def today():
    try:
        return get_today()
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Notion error: {e}")


@app.post("/heartbeat", status_code=200)
def heartbeat():
    """Record that the app was opened today. Fire-and-forget — never errors."""
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO activity_log (date, opened, captured) VALUES (?, 1, 0)
            ON CONFLICT(date) DO UPDATE SET opened = opened + 1
            """,
            (today_str,),
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


class CaptureBody(BaseModel):
    text: str


@app.post("/capture", status_code=201)
def capture(body: CaptureBody):
    """
    Save a voice/quick capture as a new timestamped markdown note in the vault.
    SAFETY: only ever CREATES new files — never touches existing notes.
    """
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text must not be empty")

    vault_path = Path(os.getenv("VAULT_PATH", "tests/sample_vault"))
    if not vault_path.is_absolute():
        vault_path = (Path(__file__).parent.parent / vault_path).resolve()

    captures_dir = vault_path / "captures"
    captures_dir.mkdir(parents=True, exist_ok=True)

    # Filename: captures/2026-05-28T143022.md — sortable, collision-resistant
    ts = datetime.now().strftime("%Y-%m-%dT%H%M%S")
    filename = captures_dir / f"{ts}.md"

    # Safety: refuse to overwrite if (somehow) the file already exists
    if filename.exists():
        raise HTTPException(status_code=409, detail="Capture file already exists")

    # Sanitise a short title from the first sentence (≤60 chars)
    first_sentence = re.split(r"[.!?\n]", text)[0].strip()
    title = first_sentence[:60]

    content = f"# {title}\n\n#voice-capture\n\n{text}\n"
    filename.write_text(content, encoding="utf-8")

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
