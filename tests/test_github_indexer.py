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
