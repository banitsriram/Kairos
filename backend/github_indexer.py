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
