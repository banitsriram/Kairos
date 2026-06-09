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
