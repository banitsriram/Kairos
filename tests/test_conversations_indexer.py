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
