# Unified Search (A1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Kairos's `/search` cover Obsidian notes, Notion, Claude conversations, and GitHub in one query, with per-result source labels and an optional source filter.

**Architecture:** Reuse Kairos's existing SQLite FTS5 table and `/search` endpoint. Sources are distinguished by path prefix (`gh/…`, `conv/…`, alongside the existing `notion/…` and bare vault paths). Two new indexers feed the same table; a small `search_index()` function adds source filtering; the frontend gains source badges and filter pills. No schema migration, keyword search only (semantic is a deliberate future phase).

**Tech Stack:** Python 3.9, FastAPI, SQLite FTS5, `requests`, pytest; React 19 + TypeScript + Vite frontend.

**Setup:** Work on a branch. From the repo root (`~/projects/Kairos`):
```bash
git checkout -b feat/unified-search
```
All test commands run from the repo root using the project venv: `.venv/bin/pytest …`.

---

### Task 1: Test fixture + DB helpers

Add a shared in-memory DB fixture and three small helpers to `db.py`: a reusable FTS5 upsert, the source-prefix map, and a `source_of()` classifier. Existing indexers keep their inline upsert (not refactored); only new code uses `upsert_fts`.

**Files:**
- Create: `tests/conftest.py`
- Modify: `backend/db.py`
- Test: `tests/test_db_helpers.py`

- [ ] **Step 1: Create the shared test fixture**

Create `tests/conftest.py`:

```python
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
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_db_helpers.py`:

```python
from db import upsert_fts, source_of


def test_upsert_inserts_then_replaces(db):
    upsert_fts(db, "gh/reelevance", "reelevance", "movie recommender", "github")
    row = db.execute("SELECT title, body FROM notes_fts WHERE path='gh/reelevance'").fetchone()
    assert row["title"] == "reelevance"

    # Re-upsert same path replaces, never duplicates (FTS5 has no UPDATE)
    upsert_fts(db, "gh/reelevance", "reelevance", "updated body", "github")
    rows = db.execute("SELECT body FROM notes_fts WHERE path='gh/reelevance'").fetchall()
    assert len(rows) == 1
    assert rows[0]["body"] == "updated body"

    meta = db.execute("SELECT path FROM notes_meta WHERE path='gh/reelevance'").fetchone()
    assert meta is not None


def test_source_of_classifies_by_prefix():
    assert source_of("notion/tasks/abc") == "notion"
    assert source_of("gh/repo/blob/main.py") == "github"
    assert source_of("conv/2026-06-09-84359b04") == "conversation"
    assert source_of("cs/distributed-systems.md") == "note"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_db_helpers.py -v`
Expected: FAIL with `ImportError: cannot import name 'upsert_fts' from 'db'`

- [ ] **Step 4: Implement the helpers**

In `backend/db.py`, add `import time` at the top with the other imports, then append at the end of the file:

```python
SOURCE_PREFIXES = {
    "notion": "notion/",
    "github": "gh/",
    "conversation": "conv/",
}


def source_of(path: str) -> str:
    """Classify a row by its path prefix. Bare paths are vault notes."""
    for source, prefix in SOURCE_PREFIXES.items():
        if path.startswith(prefix):
            return source
    return "note"


def upsert_fts(conn, path: str, title: str, body: str, tags: str) -> None:
    """Insert-or-replace a row in notes_fts and track it in notes_meta.
    FTS5 has no UPDATE, so delete then insert — same pattern as the other indexers."""
    now = time.time()
    conn.execute("DELETE FROM notes_fts WHERE path = ?", (path,))
    conn.execute(
        "INSERT INTO notes_fts (path, title, body, tags) VALUES (?, ?, ?, ?)",
        (path, title, body, tags),
    )
    conn.execute(
        """INSERT INTO notes_meta (path, mtime, indexed_at) VALUES (?, ?, ?)
           ON CONFLICT(path) DO UPDATE
           SET mtime = excluded.mtime, indexed_at = excluded.indexed_at""",
        (path, now, now),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_db_helpers.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/test_db_helpers.py backend/db.py
git commit -m "feat(search): add FTS5 upsert + source classifier helpers"
```

---

### Task 2: `search_index()` with source filter + wire into `/search`

Move the search query into a testable `search_index(conn, q, source)` function, add an optional source filter, and have the endpoint accept `?source=`.

**Files:**
- Create: `backend/search.py`
- Modify: `backend/main.py` (the `/search` endpoint, ~lines 49-86)
- Test: `tests/test_search.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_search.py`:

```python
from db import upsert_fts
from search import search_index


def _seed(db):
    upsert_fts(db, "cs/movies.md", "Movies note", "favourite movie night", "")
    upsert_fts(db, "notion/tasks/1", "Watch movie", "movie task", "notion task")
    upsert_fts(db, "gh/reelevance", "reelevance", "movie recommender", "github")
    upsert_fts(db, "conv/2026-06-09-abc", "2026-06-09", "we discussed the movie recommender", "conversation")
    db.commit()


def test_unfiltered_matches_all_sources(db):
    _seed(db)
    results = search_index(db, "movie")
    sources = {r["source"] for r in results}
    assert sources == {"note", "notion", "github", "conversation"}
    # every result carries a source label and a positive score
    assert all(r["score"] >= 0 for r in results)


def test_source_filter_github_only(db):
    _seed(db)
    results = search_index(db, "movie", source="github")
    assert [r["path"] for r in results] == ["gh/reelevance"]


def test_source_filter_note_excludes_prefixed(db):
    _seed(db)
    results = search_index(db, "movie", source="note")
    assert [r["path"] for r in results] == ["cs/movies.md"]


def test_unknown_source_is_ignored(db):
    _seed(db)
    assert len(search_index(db, "movie", source="bogus")) == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_search.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'search'`

- [ ] **Step 3: Implement `search.py`**

Create `backend/search.py`:

```python
"""Query the unified FTS5 index, optionally filtered by source."""
from db import SOURCE_PREFIXES, source_of


def _source_clause(source):
    """Return (sql_fragment, extra_params) for an optional source filter.
    Prefixes are hardcoded constants, so the 'note' clause interpolates them safely."""
    if not source:
        return "", []
    if source == "note":
        clause = "".join(f" AND path NOT LIKE '{p}%'" for p in SOURCE_PREFIXES.values())
        return clause, []
    prefix = SOURCE_PREFIXES.get(source)
    if not prefix:
        return "", []  # unknown source → no filter
    return " AND path LIKE ?", [prefix + "%"]


def search_index(conn, q, source=None, limit=20):
    clause, extra = _source_clause(source)
    sql = f"""
        SELECT path, title,
               snippet(notes_fts, 2, '<mark>', '</mark>', '…', 24) AS snippet,
               bm25(notes_fts) AS score
        FROM notes_fts
        WHERE notes_fts MATCH ?{clause}
        ORDER BY score
        LIMIT ?
    """
    rows = conn.execute(sql, [q, *extra, limit]).fetchall()
    return [
        {
            "path": r["path"],
            "title": r["title"],
            "snippet": r["snippet"],
            # bm25() is negative (more negative = better). Flip so higher = more relevant.
            "score": round(-r["score"], 4),
            "source": source_of(r["path"]),
        }
        for r in rows
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_search.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Wire `search_index` into the endpoint**

In `backend/main.py`, add this import next to the other `# noqa: E402` imports:

```python
from search import search_index  # noqa: E402
```

Replace the entire existing `/search` endpoint (the `@app.get("/search")` function) with:

```python
@app.get("/search")
def search(
    q: str = Query(..., min_length=1, description="Search query"),
    source: Optional[str] = Query(
        None, description="Filter by source: note|notion|github|conversation"
    ),
):
    conn = get_connection()
    try:
        results = search_index(conn, q, source=source)
    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=400, detail=f"Invalid query syntax: {e}")
    finally:
        conn.close()

    return {"query": q, "source": source, "total": len(results), "results": results}
```

- [ ] **Step 6: Write the endpoint integration test**

Append to `tests/test_search.py`:

```python
def test_search_endpoint_filters_by_source(monkeypatch, tmp_path):
    import db as dbmod
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "test.db")
    dbmod.init_db()
    conn = dbmod.get_connection()
    dbmod.upsert_fts(conn, "gh/reelevance", "reelevance", "movie recommender", "github")
    dbmod.upsert_fts(conn, "cs/movies.md", "Movies", "movie night", "")
    conn.commit()
    conn.close()

    import main
    from fastapi.testclient import TestClient
    client = TestClient(main.app)

    r = client.get("/search", params={"q": "movie", "source": "github"})
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "github"
    assert [x["path"] for x in data["results"]] == ["gh/reelevance"]
    assert data["results"][0]["source"] == "github"
```

- [ ] **Step 7: Run the full search test file**

Run: `.venv/bin/pytest tests/test_search.py -v`
Expected: PASS (5 passed)

- [ ] **Step 8: Commit**

```bash
git add backend/search.py backend/main.py tests/test_search.py
git commit -m "feat(search): add source-filtered search_index and /search?source="
```

---

### Task 3: GitHub client (`github.py`)

A thin `requests` client for the authenticated user's repos — mirrors `notion.py`. Reads `GITHUB_TOKEN`. Tests patch the single `_get_json` network function.

**Files:**
- Create: `backend/github.py`
- Test: `tests/test_github.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_github.py`:

```python
import github


def test_should_index_filters_binaries_dirs_and_large(monkeypatch):
    assert github._should_index("backend/main.py", 100) is True
    assert github._should_index("README.md", 100) is True
    assert github._should_index("node_modules/foo/bar.js", 100) is False
    assert github._should_index("assets/logo.png", 100) is False
    assert github._should_index("backend/main.py", 10 * 1024 * 1024) is False


def test_list_repos_shapes_rows(monkeypatch):
    monkeypatch.setattr(github, "_get_json", lambda url, params=None: [
        {"full_name": "u/reelevance", "name": "reelevance", "description": "movies",
         "default_branch": "main", "topics": ["python"], "language": "Python", "private": False},
    ])
    repos = github.list_repos()
    assert repos == [{
        "full_name": "u/reelevance", "name": "reelevance", "description": "movies",
        "default_branch": "main", "topics": ["python"], "language": "Python",
    }]


def test_list_text_files_keeps_only_indexable_blobs(monkeypatch):
    monkeypatch.setattr(github, "_get_json", lambda url, params=None: {
        "tree": [
            {"path": "main.py", "type": "blob", "sha": "a", "size": 50},
            {"path": "node_modules/x.js", "type": "blob", "sha": "b", "size": 50},
            {"path": "src", "type": "tree", "sha": "c"},
            {"path": "logo.png", "type": "blob", "sha": "d", "size": 50},
        ]
    })
    files = github.list_text_files("u/repo", "main")
    assert files == [{"path": "main.py", "sha": "a"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_github.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'github'`

- [ ] **Step 3: Implement `github.py`**

Create `backend/github.py`:

```python
"""
Thin client for the authenticated user's GitHub repos. Reads GITHUB_TOKEN from env.
Uses the REST API via `requests` — same pattern as notion.py.
"""
import base64
import os
from typing import Any, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

_TOKEN = os.getenv("GITHUB_TOKEN", "")
_API = "https://api.github.com"
_HEADERS = {
    "Authorization": f"Bearer {_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

_SKIP_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__", ".venv", "venv"}
_TEXT_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".md", ".txt", ".json", ".yaml", ".yml",
    ".toml", ".cfg", ".ini", ".sh", ".css", ".html", ".sql", ".c", ".h", ".cpp",
    ".java", ".go", ".rs", ".rb",
}
_MAX_FILE_BYTES = 256 * 1024


def _get_json(url: str, params: Optional[dict] = None) -> Any:
    resp = requests.get(url, headers=_HEADERS, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _paginate(url: str, params: Optional[dict] = None) -> list:
    params = dict(params or {})
    params.setdefault("per_page", 100)
    out: list = []
    page = 1
    while True:
        params["page"] = page
        batch = _get_json(url, params)
        if not batch:
            break
        out.extend(batch)
        if len(batch) < params["per_page"]:
            break
        page += 1
    return out


def list_repos() -> list:
    repos = _paginate(f"{_API}/user/repos", {"affiliation": "owner"})
    return [
        {
            "full_name": r["full_name"],
            "name": r["name"],
            "description": r.get("description") or "",
            "default_branch": r.get("default_branch") or "main",
            "topics": r.get("topics") or [],
            "language": r.get("language") or "",
        }
        for r in repos
    ]


def get_readme(full_name: str) -> str:
    try:
        data = _get_json(f"{_API}/repos/{full_name}/readme")
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return ""
        raise
    return base64.b64decode(data.get("content", "")).decode("utf-8", errors="ignore")


def list_commits(full_name: str, limit: int = 100) -> list:
    commits = _paginate(f"{_API}/repos/{full_name}/commits")[:limit]
    return [{"sha": c["sha"], "message": c["commit"]["message"]} for c in commits]


def list_issues(full_name: str) -> list:
    issues = _paginate(f"{_API}/repos/{full_name}/issues", {"state": "all"})
    return [
        {"number": i["number"], "title": i["title"], "body": i.get("body") or ""}
        for i in issues
    ]


def _should_index(path: str, size: int) -> bool:
    parts = path.split("/")
    if any(p in _SKIP_DIRS for p in parts[:-1]):
        return False
    if size > _MAX_FILE_BYTES:
        return False
    dot = path.rfind(".")
    ext = path[dot:].lower() if dot != -1 else ""
    return ext in _TEXT_EXTS


def list_text_files(full_name: str, branch: str) -> list:
    tree = _get_json(f"{_API}/repos/{full_name}/git/trees/{branch}", {"recursive": "1"})
    files = []
    for node in tree.get("tree", []):
        if node.get("type") != "blob":
            continue
        if _should_index(node["path"], node.get("size", 0)):
            files.append({"path": node["path"], "sha": node["sha"]})
    return files


def get_blob(full_name: str, sha: str) -> str:
    data = _get_json(f"{_API}/repos/{full_name}/git/blobs/{sha}")
    if data.get("encoding") == "base64":
        return base64.b64decode(data.get("content", "")).decode("utf-8", errors="ignore")
    return data.get("content", "")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_github.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/github.py tests/test_github.py
git commit -m "feat(search): add GitHub REST client"
```

---

### Task 4: GitHub indexer (`github_indexer.py`)

Walk the client output into FTS5 rows under the `gh/…` prefixes. Accepts an optional `conn` for tests.

**Files:**
- Create: `backend/github_indexer.py`
- Test: `tests/test_github_indexer.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_github_indexer.py`:

```python
import github
import github_indexer


def _stub_github(monkeypatch):
    monkeypatch.setattr(github, "list_repos", lambda: [
        {"full_name": "u/demo", "name": "demo", "description": "a demo repo",
         "default_branch": "main", "topics": ["cli"], "language": "Python"},
    ])
    monkeypatch.setattr(github, "get_readme", lambda fn: "# Demo\nlong readme body")
    monkeypatch.setattr(github, "list_commits", lambda fn, limit=100: [
        {"sha": "abc123", "message": "feat: first commit\n\ndetails"},
    ])
    monkeypatch.setattr(github, "list_text_files", lambda fn, branch: [
        {"path": "main.py", "sha": "blob1"},
    ])
    monkeypatch.setattr(github, "get_blob", lambda fn, sha: "print('hello')")
    monkeypatch.setattr(github, "list_issues", lambda fn: [
        {"number": 7, "title": "Bug: crash", "body": "it crashes"},
    ])


def test_index_github_creates_all_row_types(db, monkeypatch):
    _stub_github(monkeypatch)
    n = github_indexer.index_github(conn=db)
    assert n == 4

    paths = {r["path"] for r in db.execute("SELECT path FROM notes_fts").fetchall()}
    assert paths == {
        "gh/demo",
        "gh/demo/commit/abc123",
        "gh/demo/blob/main.py",
        "gh/demo/issue/7",
    }

    overview = db.execute("SELECT body, tags FROM notes_fts WHERE path='gh/demo'").fetchone()
    assert "a demo repo" in overview["body"]
    assert "long readme body" in overview["body"]
    assert "cli" in overview["tags"]

    commit = db.execute("SELECT title FROM notes_fts WHERE path='gh/demo/commit/abc123'").fetchone()
    assert commit["title"] == "feat: first commit"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_github_indexer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'github_indexer'`

- [ ] **Step 3: Implement `github_indexer.py`**

Create `backend/github_indexer.py`:

```python
"""
Pull the authenticated user's GitHub content into the SQLite FTS5 index.

Row paths:
  gh/<repo>                 repo overview (description + README)
  gh/<repo>/commit/<sha>    commit message
  gh/<repo>/blob/<path>     text file contents
  gh/<repo>/issue/<n>       issue / PR

Run manually or from cron:
  python github_indexer.py
"""
import github
from db import get_connection, init_db, upsert_fts


def index_github(conn=None) -> int:
    own_conn = conn is None
    if own_conn:
        init_db()
        conn = get_connection()

    count = 0
    for repo in github.list_repos():
        name = repo["name"]
        full = repo["full_name"]

        # Repo overview
        readme = github.get_readme(full)
        body = "\n\n".join(p for p in [repo["description"], readme] if p)
        tags = " ".join(["github", repo["language"], *repo["topics"]]).strip()
        upsert_fts(conn, f"gh/{name}", name, body, tags)
        count += 1

        # Commits
        for c in github.list_commits(full):
            summary = c["message"].splitlines()[0] if c["message"] else c["sha"][:7]
            upsert_fts(conn, f"gh/{name}/commit/{c['sha']}", summary, c["message"], "github commit")
            count += 1

        # Code files
        for f in github.list_text_files(full, repo["default_branch"]):
            content = github.get_blob(full, f["sha"])
            upsert_fts(conn, f"gh/{name}/blob/{f['path']}", f["path"], content, "github code")
            count += 1

        # Issues / PRs
        for i in github.list_issues(full):
            upsert_fts(conn, f"gh/{name}/issue/{i['number']}", i["title"], i["body"], "github issue")
            count += 1

    conn.commit()
    if own_conn:
        conn.close()
    print(f"GitHub indexed: {count} item(s).")
    return count


if __name__ == "__main__":
    index_github()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_github_indexer.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/github_indexer.py tests/test_github_indexer.py
git commit -m "feat(search): index GitHub repos, commits, code and issues into FTS5"
```

---

### Task 5: Conversations indexer (`conversations_indexer.py`)

Index Claude session-summary markdown files (with `---` frontmatter) into FTS5 under `conv/…`. Reads `MEMORY_SESSIONS_PATH`; skips gracefully if unset/missing.

**Files:**
- Create: `backend/conversations_indexer.py`
- Test: `tests/test_conversations_indexer.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_conversations_indexer.py`:

```python
import textwrap

import conversations_indexer as ci


def test_parse_frontmatter_splits_meta_and_body():
    text = textwrap.dedent("""\
        ---
        date: 2026-06-09
        projects: [kairos, claude-memory]
        type: session
        ---

        ## What we worked on
        Unified search.
    """)
    meta, body = ci._parse_frontmatter(text)
    assert meta["date"] == "2026-06-09"
    assert meta["projects"] == "[kairos, claude-memory]"
    assert "Unified search." in body
    assert "What we worked on" in body


def test_index_conversations_reads_session_files(db, tmp_path, monkeypatch):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "2026-06-09-abc.md").write_text(textwrap.dedent("""\
        ---
        date: 2026-06-09
        projects: [kairos]
        ---

        Discussed the unified search design.
    """), encoding="utf-8")

    monkeypatch.setattr(ci, "_SESSIONS_PATH", str(sessions))
    n = ci.index_conversations(conn=db)
    assert n == 1

    row = db.execute("SELECT title, body FROM notes_fts WHERE path='conv/2026-06-09-abc'").fetchone()
    assert "2026-06-09" in row["title"]
    assert "unified search" in row["body"].lower()


def test_missing_path_skips_without_error(db, monkeypatch):
    monkeypatch.setattr(ci, "_SESSIONS_PATH", "")
    assert ci.index_conversations(conn=db) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_conversations_indexer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'conversations_indexer'`

- [ ] **Step 3: Implement `conversations_indexer.py`**

Create `backend/conversations_indexer.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_conversations_indexer.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Run the whole backend suite (no regressions)**

Run: `.venv/bin/pytest tests/ -v`
Expected: PASS — all existing `test_briefing.py` tests plus the new files.

- [ ] **Step 6: Commit**

```bash
git add backend/conversations_indexer.py tests/test_conversations_indexer.py
git commit -m "feat(search): index Claude session summaries into FTS5"
```

---

### Task 6: Frontend — source badges + filter pills

Add GitHub/conversation labels to the existing prefix-based badge logic (no regression to Task/Event labels), thread a `source` param through the API, and add filter pills to the command palette. The frontend has no unit-test harness, so verification is `tsc`/`build`.

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/SearchResults.tsx`
- Modify: `frontend/src/components/CommandPalette.tsx`

- [ ] **Step 1: Extend the API client**

In `frontend/src/lib/api.ts`, add `source` to the `SearchResult` interface:

```typescript
export interface SearchResult {
  path: string
  title: string
  snippet: string
  score: number
  source: string
}
```

Replace the existing `search` function with one that accepts an optional source:

```typescript
export async function search(q: string, source?: string): Promise<{ results: SearchResult[] }> {
  const params = new URLSearchParams({ q })
  if (source) params.set('source', source)
  return get(`/search?${params.toString()}`)
}
```

- [ ] **Step 2: Add GitHub + conversation badges**

In `frontend/src/components/SearchResults.tsx`, extend the two helper functions (keep the existing Task/Event/Note cases):

```typescript
function sourceLabel(path: string): string {
  if (path.startsWith('notion/tasks'))    return 'Task'
  if (path.startsWith('notion/schedule')) return 'Event'
  if (path.startsWith('gh/'))             return 'GitHub'
  if (path.startsWith('conv/'))           return 'Conversation'
  return 'Note'
}

function sourceIcon(path: string): string {
  if (path.startsWith('notion/tasks'))    return '✓'
  if (path.startsWith('notion/schedule')) return '◷'
  if (path.startsWith('gh/'))             return '⎇'
  if (path.startsWith('conv/'))           return '💬'
  return '◈'
}
```

- [ ] **Step 3: Add source-filter pills to the palette**

In `frontend/src/components/CommandPalette.tsx`:

(a) Add filter state next to the other `useState` calls:

```typescript
  const [source, setSource] = useState<string | null>(null)
```

(b) Reset it when the palette opens — inside the `if (open) { … }` block of the "Focus input when palette opens" effect, add:

```typescript
      setSource(null)
```

(c) Make live search pass the filter and re-run when it changes — replace the "Live search" effect body's `search(debouncedQuery)` call and dependency array:

```typescript
  // Live search
  useEffect(() => {
    if (mode !== 'search' || !debouncedQuery.trim()) {
      setResults([])
      return
    }
    setLoading(true)
    search(debouncedQuery, source ?? undefined)
      .then((r) => setResults(r.results))
      .catch(() => setResults([]))
      .finally(() => setLoading(false))
  }, [debouncedQuery, mode, source])
```

(d) Update the search input placeholder and add the pill row directly above the `<input>` in the `mode === 'search'` block:

```tsx
            <div className="palette-filters">
              {([
                ['All', null],
                ['Notes', 'note'],
                ['Notion', 'notion'],
                ['GitHub', 'github'],
                ['Conversations', 'conversation'],
              ] as [string, string | null][]).map(([label, value]) => (
                <button
                  key={label}
                  className={`palette-filter ${source === value ? 'palette-filter--active' : ''}`}
                  onClick={() => setSource(value)}
                >
                  {label}
                </button>
              ))}
            </div>
            <input
              ref={inputRef as React.RefObject<HTMLInputElement>}
              className="palette-input"
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search notes, Notion, GitHub, conversations…"
              spellCheck={false}
              autoComplete="off"
            />
```

- [ ] **Step 4: Add styles for the filter pills**

In `frontend/src/index.css`, append:

```css
.palette-filters {
  display: flex;
  gap: 0.4rem;
  margin-bottom: 0.6rem;
  flex-wrap: wrap;
}
.palette-filter {
  padding: 0.2rem 0.7rem;
  border-radius: 999px;
  border: 1px solid var(--bg-panel);
  background: transparent;
  color: var(--text);
  font-size: 0.8rem;
  cursor: pointer;
}
.palette-filter--active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
```

- [ ] **Step 5: Type-check and build**

Run: `cd frontend && npm run build`
Expected: build succeeds with no TypeScript errors. Then `cd ..`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/components/SearchResults.tsx frontend/src/components/CommandPalette.tsx frontend/src/index.css
git commit -m "feat(search): source badges and filter pills in the command palette"
```

---

### Task 7: Wire up config and cron

Document the two new env vars and run the new indexers from the server cron.

**Files:**
- Modify: `.env.example`
- Modify: `scripts/server_cron.sh`

- [ ] **Step 1: Add the new env vars to `.env.example`**

Append to `.env.example`:

```bash
# --- Unified search (A1) ---
# Read-only GitHub token (scope: repo) for indexing your repos
GITHUB_TOKEN=
# Path to the synced claude-memory sessions/ directory on the server
MEMORY_SESSIONS_PATH=/home/<your-user>/.claude/memory/sessions
```

- [ ] **Step 2: Run the new indexers from cron**

In `scripts/server_cron.sh`, after the existing two `docker compose exec` lines, add:

```bash
docker compose exec -T backend python github_indexer.py
docker compose exec -T backend python conversations_indexer.py
```

- [ ] **Step 3: Verify the script parses**

Run: `bash -n scripts/server_cron.sh`
Expected: no output (syntax OK).

- [ ] **Step 4: Commit**

```bash
git add .env.example scripts/server_cron.sh
git commit -m "chore(search): add GITHUB_TOKEN + MEMORY_SESSIONS_PATH and cron indexing"
```

---

## Deploy notes (after the branch merges)

These are operational steps for the user, not code tasks:

1. Create a GitHub personal access token (classic, scope `repo`) and put it in `~/kairos/.env` on amrad as `GITHUB_TOKEN`.
2. Set `MEMORY_SESSIONS_PATH` in `~/kairos/.env` to the synced claude-memory `sessions/` directory, and ensure the backend container can read it (mount the path into the container in `docker-compose.yml` if it lives outside the project tree).
3. `./deploy.sh` to rebuild and re-index.
4. First GitHub index will be the slowest run (it fetches every text file once); subsequent runs re-upsert.

## Self-review notes

- **Spec coverage:** GitHub overview/commits/code/issues → Task 4; conversations (summaries only) → Task 5; unified `/search` + `?source=` + per-result source → Tasks 1-2; source badges + filter UI → Task 6; cron + env (`GITHUB_TOKEN`, `MEMORY_SESSIONS_PATH`) → Task 7; graceful per-source degradation → conversations skip (Task 5) and the README-404 guard in the client (Task 3). Path-prefix source model and no-schema-change → Tasks 1-2.
- **Deviations from spec (intentional):** indexers take an optional `conn` (testability) instead of being argless; the GitHub client uses `requests` (the real `notion.py` pattern), not `urllib`; source *labels* are derived client-side by path prefix (the existing Kairos pattern) while the API also returns a `source` field used for filtering — no duplicated logic introduced into existing files.
- **Type/name consistency:** `upsert_fts(conn, path, title, body, tags)`, `source_of(path)`, `SOURCE_PREFIXES`, `search_index(conn, q, source, limit)`, `index_github(conn=None)`, `index_conversations(conn=None)`, and the `github` client functions are referenced consistently across tasks and tests.
