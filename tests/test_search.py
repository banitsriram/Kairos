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
