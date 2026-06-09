"""
Pull the authenticated user's GitHub content into the SQLite FTS5 index.

Row paths:
  gh/<repo>                 repo overview (description + README)
  gh/<repo>/commit/<sha>    commit message
  gh/<repo>/blob/<path>     text file contents
  gh/<repo>/issue/<n>       issue / PR

Degrades gracefully: a missing/invalid GITHUB_TOKEN or a single bad repo logs and
is skipped rather than raising — so it can never break the indexing cron.

Run manually or from cron:
  python github_indexer.py
"""
import sys

import github
from db import get_connection, init_db, upsert_fts


def _index_repo(conn, repo) -> int:
    """Index one repo's overview, commits, code files and issues. Returns row count."""
    name = repo["name"]
    full = repo["full_name"]
    count = 0

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

    return count


def index_github(conn=None) -> int:
    own_conn = conn is None
    if own_conn:
        init_db()
        conn = get_connection()

    try:
        repos = github.list_repos()
    except Exception as e:
        # Missing/invalid token, rate limit, network — skip without breaking the cron.
        print(f"GitHub: could not list repos ({e}); skipping.", file=sys.stderr)
        repos = []

    count = 0
    for repo in repos:
        try:
            count += _index_repo(conn, repo)
        except Exception as e:
            print(f"GitHub: skipping repo {repo.get('full_name')} ({e})", file=sys.stderr)

    conn.commit()
    if own_conn:
        conn.close()
    print(f"GitHub indexed: {count} item(s).")
    return count


if __name__ == "__main__":
    index_github()
