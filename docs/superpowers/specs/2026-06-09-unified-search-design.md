# Unified Search (A1) — Design

**Date:** 2026-06-09
**Status:** Approved (design)
**Project:** Kairos — Project A ("private work hub"), layer A1

## Overview

Extend Kairos's existing search so a single query covers **Obsidian notes, Notion,
Claude conversations, and GitHub** — instead of notes + Notion only. This is the
foundation layer of a larger private "work hub" (A2 dashboard and A3 connections
build on top of it). It stays Tailscale-only, runs on amrad, and never exposes
private data publicly.

Keyword search first (reusing Kairos's SQLite FTS5), with a deliberate upgrade
path to semantic search left for a later phase — **not** built here.

## Goals

- One `/search` query returns ranked hits across notes, Notion, conversations, and GitHub.
- Results are labeled by source and filterable by source.
- GitHub coverage: repo overview (name/description/README/topics), commit messages,
  text file contents, and issues/PRs.
- Conversations coverage: the Claude session summaries already synced to amrad.
- No new search engine, no schema migration — reuse the existing FTS5 table.

## Non-goals (explicitly out of scope for A1)

- Semantic / embedding search (future upgrade; design leaves room but does not build it).
- Indexing raw Claude transcripts (only the synced session **summaries** are indexed).
- The A2 activity dashboard and A3 connections/graph.
- The public portfolio (Project B).
- Any public exposure of the index.

## Architecture

Kairos already provides the entire search machine:

- FTS5 virtual table `notes_fts(path, title, body, tags)` (porter tokenizer).
- `notes_meta(path PK, mtime REAL, indexed_at REAL)` freshness tracking.
- Indexers `indexer.py` (vault) and `notion_indexer.py` (Notion) that DELETE+INSERT
  rows (FTS5 has no UPDATE).
- `/search?q=` endpoint, BM25-ranked (score negated).
- Cmd+K command palette + `SearchBar.tsx` / `SearchResults.tsx`.
- A 15-minute re-index cron (`scripts/server_cron.sh`).

Sources are already distinguished **purely by a path prefix** (`notion/tasks/<id>`,
`notion/schedule/<id>` vs. bare vault paths like `cs/note.md`). Unified search adds
two more prefixes and two more indexers feeding the same table:

| Source        | Path prefix           | Derived `source` label |
|---------------|-----------------------|------------------------|
| Vault notes   | *(none)* e.g. `cs/x.md` | `note`               |
| Notion        | `notion/…`            | `notion`               |
| GitHub        | `gh/…`                | `github`               |
| Conversations | `conv/…`              | `conversation`         |

No schema change is required: `source` is derived from the path prefix at query time.

## Components

### `backend/github_indexer.py`
- **Purpose:** pull the user's GitHub content into `notes_fts`.
- **Interface:** `index_github(conn) -> IndexStats` (mirrors `notion_indexer.index_notion`).
- **Depends on:** `GITHUB_TOKEN` (from `.env`), the DB connection. Calls the GitHub REST
  API directly with stdlib `urllib` — same pattern as `notion.py` — so it does **not**
  depend on the `gh` CLI being installed/authenticated on amrad.
- **Row types upserted:**
  - `gh/<repo>` → title=repo name, body=description + README, tags=topics + primary language
  - `gh/<repo>/commit/<sha>` → title=commit summary (first line), body=full message
  - `gh/<repo>/blob/<path>` → title=file path, body=file contents
  - `gh/<repo>/issue/<n>` → title=issue/PR title, body=issue/PR body
- **File filtering for `blob` rows:** skip binaries and noise — match by extension
  allowlist (text/code) and skip `node_modules/`, `.git/`, `dist/`, `build/`,
  lockfiles, and files over a size cap (e.g. 256 KB).
- **Scope:** all repos owned by the authenticated user, public and private.

### `backend/conversations_indexer.py`
- **Purpose:** pull Claude session summaries into `notes_fts`.
- **Interface:** `index_conversations(conn) -> IndexStats`.
- **Depends on:** `MEMORY_SESSIONS_PATH` (from `.env`, e.g. the claude-memory repo's
  `sessions/` dir on amrad), the DB connection.
- **Source files:** the synced session-summary markdown files
  (`sessions/YYYY-MM-DD-<id>.md`). Raw transcripts are **not** read.
- **Row type:** `conv/<date>-<id>` → title=date + projects (from frontmatter),
  body=summary text, tags=projects.

### `backend/main.py` — `/search`
- Add optional `?source=` query param (`note|notion|github|conversation`) to filter results.
- Each result object includes a derived `source` field.
- Ranking unchanged (BM25 across the unified table).

### `backend/db.py`
- Small helper `source_of(path) -> str` mapping path prefix → label, used by the
  search response builder. No schema change.

### `scripts/server_cron.sh`
- Call `github_indexer` and `conversations_indexer` alongside the existing vault and
  Notion indexers each run. GitHub indexing may run on a longer interval than 15 min
  if rate limits warrant (configurable), but default is every run for ~4 small repos.

### Frontend `src/components/SearchResults.tsx`
- Render a per-result source badge (`note` / `notion` / `github` / `conversation`).
- Optional source-filter pills that set `?source=`. Cmd+K flow otherwise unchanged.

## Data flow

```
cron (server_cron.sh)
  ├─ indexer.py            (vault)         ┐
  ├─ notion_indexer.py     (Notion)        │  DELETE+INSERT
  ├─ github_indexer.py     (GitHub API)    ├─► notes_fts ──► /search?q=&source= ──► Cmd+K UI
  └─ conversations_indexer (memory dir)    ┘                     (BM25, labeled by source)
```

## Error handling

- Each indexer is independent and wrapped so a failure in one source does not abort the
  others — mirrors Kairos's existing graceful degradation when Notion is unavailable.
- GitHub API failures (rate limit / 403 / network) skip that run and log; the previously
  indexed GitHub rows remain searchable.
- A missing or unreadable `MEMORY_SESSIONS_PATH` skips the conversations source with a log
  line, not a crash.

## Security

- `GITHUB_TOKEN` lives in `.env` (gitignored), read-only access to the user's repos.
- This index includes **private** content (the private `claude-memory` repo and
  conversation summaries). That is acceptable and intentional because Kairos is
  Tailscale-only and never publicly exposed. No private content is ever served outside
  Tailscale. The public portfolio remains a separate Project B with zero private data.

## Testing

Follow existing Kairos patterns (`_make_db()`, `TestClient` context manager, mocked
external API targets):

- `github_indexer`: unit tests with mocked GitHub REST responses; assert each row type is
  produced with the correct path prefix; assert binary/oversized files are skipped.
- `conversations_indexer`: unit tests over sample session-summary fixtures; assert
  frontmatter (date/projects) maps to title/tags.
- Integration: seed a temp DB via the indexers and assert `/search?q=…&source=github`
  returns only GitHub hits and that an unfiltered query merges all sources.

## Environment variables (new)

| Variable               | Description                                            |
|------------------------|--------------------------------------------------------|
| `GITHUB_TOKEN`         | Read-only token for the user's repos                   |
| `MEMORY_SESSIONS_PATH` | Path to the synced claude-memory `sessions/` directory |

## Future (not built in A1)

- Semantic upgrade: add an embedding index (reuse amrad's Ollama `nomic-embed-text`)
  and hybrid keyword+semantic ranking. The path-prefix/source model carries over unchanged.
- A2 activity dashboard and A3 connections build on this unified index.
