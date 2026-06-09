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
