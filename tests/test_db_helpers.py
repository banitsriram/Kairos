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
