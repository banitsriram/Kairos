# Kairos — Self-Hosted Personal "Second Brain" Life Dashboard

## Who is building this
First-year CS undergrad, Systems/Backend/DevOps track. Mac + VS Code. Strong
Python, learning C, comfortable with git/terminal. Newer to frontend/JS and
self-hosting. Wants to LEARN from the build — explain decisions, flag concepts
to study. Don't just hand over undebuggable code.

## The vision
A self-hosted personal life-dashboard / second brain running on a home-lab
server (SSH-managed), reachable from any device via Tailscale. Must be genuinely
useful every day — not a sterile dashboard, not a gimmick. Feels alive,
occasionally funny, quietly motivating, and looks beautiful.

## Stack
- Backend: FastAPI (Python 3.9)
- Search: SQLite FTS5 (porter + unicode61 tokenizer), clean upgrade path to embeddings later
- Sync: cron — git-pull vault, then run indexer; separate Notion indexer
- Frontend: React 19 + TypeScript + Vite
- Reverse proxy + HTTPS: Caddy
- Deploy: Docker Compose (`docker compose up`)
- Remote access: Tailscale — NEVER expose ports to the public internet

## Home lab server

| Field        | Value                          |
|--------------|--------------------------------|
| SSH alias    | `<your-server-alias>`          |
| Tailscale IP | `<your-tailscale-ip>`          |
| User         | `<your-server-user>`           |
| OS           | Linux                          |
| Tailscale    | Connected                      |

SSH config (`~/.ssh/config`):
```
Host <your-server-alias>
    HostName <your-tailscale-ip>
    User <your-server-user>
```

**Deployment status:** Phase 4 config is written and ready — waiting for server
to come online. All Docker/Caddy files are in the repo root.

**First-time deploy checklist (run once when server is online):**
1. `ssh <your-server-alias>` — confirm Docker is installed (`docker --version`)
2. On server: `mkdir -p ~/kairos && cp .env.example ~/kairos/.env` then fill in real values
3. On server: confirm vault path (`ls ~/vault` or wherever it lives)
4. On Mac: `./deploy.sh` — builds frontend, rsyncs to server, runs docker compose up
5. On server: set up cron — `crontab -e` and add the line from `scripts/server_cron.sh`
6. On Mac: `caddy trust` on each device to trust Caddy's internal CA (for HTTPS)
7. Open `https://<your-tailscale-ip>` from any Tailscale device

**Current dev setup (Mac only):**
- Backend: `localhost:8000`
- Frontend: `localhost:5173` (Vite dev server, proxies `/api` → `:8000`)
- Vault: `tests/sample_vault` (real vault is on the server)

## Project layout

```
kairos/
├── backend/
│   ├── main.py          # FastAPI app — /health, /search, /tasks, /schedule, /today
│   ├── db.py            # SQLite connection + schema init (notes_meta + notes_fts)
│   ├── indexer.py       # Walks VAULT_PATH, upserts changed .md notes into FTS5
│   ├── notion.py        # Notion client — get_tasks(), get_schedule()
│   └── requirements.txt # fastapi, uvicorn[standard], python-dotenv, requests
├── scripts/
│   └── sync_vault.sh    # git-pull vault → run indexer.py — add to cron (*/15 * *)
├── tests/
│   └── sample_vault/    # Local test notes: daily, cs, projects, reading
├── data/
│   └── brain.db         # SQLite DB — gitignored, created at runtime
├── .env                 # Local config — gitignored, never commit
├── .env.example         # Template — safe to commit, no real values
└── CLAUDE.md            # This file
```

## Environment variables

| Variable            | Dev default            | Description                          |
|---------------------|------------------------|--------------------------------------|
| `VAULT_PATH`        | `./tests/sample_vault` | Path to Obsidian vault               |
| `DB_PATH`           | `./data/brain.db`      | SQLite database path                 |
| `PORT`              | `8000`                 | FastAPI port                         |
| `NOTION_TOKEN`      | —                      | Notion integration token             |
| `NOTION_TASKS_DB`   | —                      | Notion Tasks database ID             |
| `NOTION_SCHEDULE_DB`| —                      | Notion Schedule database ID          |

## Notion databases

Kairos page ID: `36e522ea-e156-80c6-964d-d0f36fc7d6c4`

**Tasks DB** (`36e522ea-e156-81fd-ad79-cd3b160ddf9e`):
- Name (title), Status (select: Not started / In progress / Done),
  Priority (select: High / Medium / Low), Due Date (date)

**Schedule DB** (`36e522ea-e156-8126-93ec-c02fcc905161`):
- Name (title), Date (date), Type (select: Class / Study / Personal / Meeting),
  Notes (rich_text)

## SQLite schema

`notes_meta(path PK, mtime, indexed_at)` — tracks what's up to date.
`notes_fts(path, title, body, tags)` — FTS5 virtual table. Source column: `path`
prefix distinguishes Obsidian notes (`vault/…`) from Notion entries (`notion/…`).
Indexer does DELETE + INSERT on change (FTS5 doesn't support UPDATE).
BM25 score returned negated so higher = more relevant.

## Running locally

```bash
cd backend
source ../.venv/bin/activate
uvicorn main:app --reload --port 8000
```

Index sample vault first:
```bash
python indexer.py
```

Test:
```bash
curl "http://localhost:8000/search?q=TLB"
curl "http://localhost:8000/tasks"
curl "http://localhost:8000/schedule?date=2026-05-29"
curl "http://localhost:8000/today"
```

## Security requirements (repo is PUBLIC — critical)
- `.gitignore` excludes: vault, data/, *.db, .env, captures/
- All secrets in `.env`; `.env.example` has blank placeholders only
- A real secret must NEVER touch git history even once
- gitleaks pre-commit hook as safety net
- Tailscale-only access; no public ports; Caddy for HTTPS on private net
- Audit for data leakage at the end of every phase

## Running the full stack

```bash
# Terminal 1 — backend
cd backend && source ../.venv/bin/activate
uvicorn main:app --reload --port 8000

# Terminal 2 — frontend dev server (proxies /api → :8000)
cd frontend && npm run dev
# open http://localhost:5173
```

## Build phases

| Phase | Status | Scope |
|-------|--------|-------|
| 1 | ✅ Done | FastAPI + /search + Obsidian FTS5 indexer |
| 2 | ✅ Done | Notion sync → /tasks, /schedule, /today; Notion indexed into FTS |
| 3 | ✅ Done | React + TypeScript + Vite frontend: hero layout, today panel (2-col grid), search, Cmd+K palette, time-of-day theming, voice search + voice capture |
| 4 | 🔄 Ready to deploy | Docker Compose + Caddy + HTTPS + Tailscale deploy |
| 5 | Pending | Daily experience + personality: morning briefing, quick-capture, daily log, streaks, on-this-day, rotating greetings/motivation, weekly review |
| 6 | Pending | Rules-based proactive nudges (no AI): class-in-1-hour, project neglect alerts, task due reminders |

## Frontend (frontend/)
Stack: React 19 + TypeScript + Vite. No UI library — all custom components.
Font: Inter (Google Fonts, preconnect in index.html).

Key files:
- `src/lib/api.ts`         — typed fetch wrappers for every backend endpoint
- `src/lib/theme.ts`       — injects CSS custom properties per time-of-day period
- `src/lib/useVoice.ts`    — Web Speech API hook (search + capture modes)
- `src/lib/useDebounce.ts` — debounce hook (250ms) to avoid search on every keystroke
- `src/lib/speech.d.ts`    — manual type declarations for Web Speech API (not in TS stdlib)
- `src/components/SearchBar.tsx`      — search input with voice mic button
- `src/components/SearchResults.tsx`  — result cards with source label + highlighted snippets
- `src/components/TodayPanel.tsx`     — two-column grid: schedule | tasks + neglected
- `src/components/CommandPalette.tsx` — Cmd+K overlay with search + voice capture tabs
- `src/index.css`          — all styles via CSS custom properties; no CSS-in-JS

Layout:
- Sticky topbar: logo (left), clock (right), ⌘K badge (right)
- Hero section: large greeting h1, live date, big centered search bar, feature hint pills
- Home view: two-column today grid (schedule | tasks)
- Search view: replaces today grid when query is non-empty
- CommandPalette: frosted-glass overlay, Search tab + Capture tab

Time-of-day periods: dawn (5–8), morning (8–12), afternoon (12–17), evening (17–21), night (21–5).
Each period sets --accent / --accent-dim / --accent-glow / --bg / --bg-panel / --bg-card /
--bg-hover / --text / --text-sub / --text-dim / --border / --border-card on :root.

Vite dev proxy: `/api/*` → `http://localhost:8000/*` (no CORS issues in dev).

Task card design: colored left stripe (3px) using priority color. Badges show
priority, status, and relative due date ("today", "tomorrow", "2d overdue").
Schedule event cards colored by type: Class=accent, Study=purple, Personal=green, Meeting=amber.

## Voice capture safety
POST /capture in main.py only ever creates new timestamped files in vault/captures/.
It will never edit, overwrite, or delete existing notes.
The captures/ directory is gitignored.

## Phase 3 — frontend notes
- Command palette (Cmd+K) is required — keyboard-first navigation
- Time-of-day theming (morning/afternoon/evening color shifts)
- Voice search: tap mic → Web Speech API → fills search bar (transient, no storage)
- Voice capture: speak → transcribe → save timestamped .md to vault/captures/ →
  auto-tagged #voice-capture → flows into indexer. NEVER edits/overwrites/deletes
  existing notes. Only creates new files.

## Phase 5 — personality config
- Greeting/motivation lines live in an editable config file (not hardcoded)
- "Sass level" setting to dial roasts up or down
- Context-aware: dry/funny when day is packed, gentle when empty, light roast
  when a project is neglected (e.g. "VoidWalker misses you. It's been 7 days.")
- Motivation mixes real quotes with user's own past wins from daily log
