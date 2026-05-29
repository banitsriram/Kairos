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
- Search: SQLite FTS5 (porter + unicode61 tokenizer), upgrade path to embeddings later
- Vault sync: Syncthing (Mac → server, send-only / receive-only)
- Cron: re-indexes vault + Notion every 15 min (no git pull — Syncthing handles sync)
- Frontend: React 19 + TypeScript + Vite
- Reverse proxy + HTTPS: Caddy (`tls internal`, Tailscale MagicDNS hostname)
- Deploy: Docker Compose (`./deploy.sh` from Mac)
- Remote access: Tailscale — NEVER expose ports to the public internet

## Home lab server

| Field        | Value                          |
|--------------|--------------------------------|
| SSH alias    | `<your-server-alias>`          |
| Tailscale hostname | `<your-tailscale-hostname>` |
| User         | `<your-server-user>`           |
| OS           | Linux                          |
| Tailscale    | Connected                      |

SSH config (`~/.ssh/config`):
```
Host <your-server-alias>
    HostName <your-tailscale-ip>
    User <your-server-user>
```

## Deployment

**Status:** Live. All 6 phases deployed and running.

**URL:** `https://<your-tailscale-hostname>` (Tailscale devices only)

**Deploy command (run from Mac project root):**
```bash
./deploy.sh
```
Builds frontend → rsyncs to server → `docker compose build` → indexes vault+Notion → `docker compose up -d`.

**First-time setup checklist:**
1. `ssh <your-server-alias>` — confirm Docker is installed (`docker --version`)
2. On server: `mkdir -p ~/kairos ~/vault`
3. On server: `cp .env.example ~/kairos/.env` — fill in real values
4. Install Syncthing on server (`~/bin/syncthing`) and Mac (`brew install syncthing`)
5. Configure Syncthing: Mac vault → `~/vault` on server (send-only / receive-only)
6. Add cron: `*/15 * * * * /home/<your-user>/kairos/scripts/server_cron.sh >> .../cron.log 2>&1`
7. On Mac: `./deploy.sh`
8. Open `https://<your-tailscale-hostname>` in browser — accept cert warning once

**Dev setup (Mac only):**
```bash
# Terminal 1 — backend
cd backend && source ../.venv/bin/activate
uvicorn main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
# open http://localhost:5173
```
Vault: `tests/sample_vault` (real vault is on the server)

**Tests:**
```bash
.venv/bin/pytest tests/ -v
```

## Project layout

```
kairos/
├── backend/
│   ├── main.py            # FastAPI app — all routes
│   ├── db.py              # SQLite connection + schema (notes_meta, notes_fts, activity_log)
│   ├── briefing.py        # Phase 5/6 logic: greeting, streak, on-this-day, nudges
│   ├── personality.yaml   # Editable personality config — greeting lines, sass level
│   ├── indexer.py         # Walks VAULT_PATH, upserts changed .md notes into FTS5
│   ├── notion.py          # Notion client — get_tasks(), get_schedule(), get_today()
│   ├── notion_indexer.py  # Pulls Notion tasks + schedule into FTS5 index
│   └── requirements.txt
├── frontend/src/
│   ├── App.tsx            # Root — topbar, hero, BriefingCard, TodayPanel
│   ├── index.css          # All styles via CSS custom properties; no CSS-in-JS
│   ├── components/
│   │   ├── BriefingCard.tsx   # Personality greeting + streak + stat pills
│   │   ├── NudgeBanner.tsx    # Dismissible rule-based alert banners
│   │   ├── TodayPanel.tsx     # 3-col grid: schedule | tasks | on-this-day
│   │   ├── CommandPalette.tsx # Cmd+K overlay: search + voice capture
│   │   └── SearchBar.tsx / SearchResults.tsx
│   └── lib/
│       ├── api.ts         # Typed fetch wrappers for all endpoints
│       ├── theme.ts       # Time-of-day CSS variable injection
│       └── useVoice.ts / useDebounce.ts / speech.d.ts
├── scripts/
│   ├── server_cron.sh     # Re-indexes vault + Notion (runs on server via cron)
│   └── sync_vault.sh      # Legacy — Syncthing replaced git-pull approach
├── tests/
│   ├── test_briefing.py   # 29 unit + integration tests
│   └── sample_vault/      # Local test notes for dev
├── data/brain.db          # SQLite DB — gitignored, created at runtime
├── .env                   # Local config — gitignored, never commit
├── .env.example           # Template — safe to commit, no real values
├── Caddyfile              # Caddy config — tls internal, /api/* proxy
├── Dockerfile             # python:3.9-slim, installs requirements, runs uvicorn
├── docker-compose.yml     # backend + caddy services, db_data volume
└── deploy.sh              # One-command deploy from Mac
```

## Environment variables

| Variable              | Dev default               | Description                          |
|-----------------------|---------------------------|--------------------------------------|
| `VAULT_PATH`          | `./tests/sample_vault`    | Path to Obsidian vault               |
| `DB_PATH`             | `./data/brain.db`         | SQLite database path                 |
| `PORT`                | `8000`                    | FastAPI port                         |
| `NOTION_TOKEN`        | —                         | Notion integration token             |
| `NOTION_TASKS_DB`     | —                         | Notion Tasks database ID             |
| `NOTION_SCHEDULE_DB`  | —                         | Notion Schedule database ID          |
| `PERSONALITY_CONFIG`  | `./backend/personality.yaml` | Path to personality config        |

## Notion databases

See `.env.example` for where to put the IDs. Database schemas:

**Tasks DB:** Name (title), Status (select: Not started / In progress / Done),
Priority (select: High / Medium / Low), Due Date (date)

**Schedule DB:** Name (title), Date (date), Type (select: Class / Study / Personal / Meeting),
Notes (rich_text)

## SQLite schema

```sql
notes_meta(path PK, mtime REAL, indexed_at REAL)
notes_fts(path, title, body, tags)          -- FTS5, porter tokenizer
activity_log(date PK, opened INT, captured INT)  -- Phase 5 streak tracking
```

- `notes_meta` — tracks what's up to date (mtime = Unix epoch float)
- `notes_fts` — FTS5 virtual table. Vault paths: no prefix (e.g. `cs/note.md`).
  Notion paths: `notion/tasks/<id>`, `notion/schedule/<id>`.
  Indexer does DELETE + INSERT (FTS5 doesn't support UPDATE). BM25 score negated.
- `activity_log` — one row per day. `opened` incremented by `/heartbeat`,
  `captured` incremented by `/capture`. Used to compute streaks.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check |
| GET | `/search?q=` | FTS5 search across vault + Notion |
| GET | `/tasks` | Notion tasks (optional `?status=` filter) |
| GET | `/schedule` | Notion schedule (optional `?date=` filter) |
| GET | `/today` | Today's schedule + top tasks + neglected task |
| GET | `/briefing` | Personality greeting, streak, on-this-day, nudges |
| POST | `/heartbeat` | Record app open (fire-and-forget, never errors) |
| POST | `/capture` | Save voice/quick note to vault/captures/ |

## Phase 5 — personality layer

`backend/briefing.py` owns all logic:
- **Config loader** — reads `personality.yaml`, falls back to hardcoded defaults
- **Template renderer** — fills `{n_classes}`, `{overdue}`, `{project}`, `{days}` slots
- **Greeting picker** — 4 buckets in priority order: `project_neglected` → `packed_day` → `empty_day` → `default`
- **Streak calculator** — counts consecutive days with `opened > 0`; bonus flag if `captured > 0` today
- **On-this-day** — vault notes whose filename matches today's MM-DD from a prior year
- **Context gatherer** — calls Notion APIs + queries `notes_meta` for neglected projects; degrades gracefully if Notion is down

`backend/personality.yaml` — editable config (committed with defaults):
```yaml
sass_level: 2          # 1–5
context:
  packed_threshold: 3  # events >= this = packed day
  neglected_days: 7    # days without vault activity = neglected
greetings:
  packed_day: [...]
  empty_day: [...]
  project_neglected: [...]
  default: [...]
```

## Phase 6 — nudges

Rules computed in `generate_nudges()` in `briefing.py`. Returned in `/briefing` response as `nudges: [{id, icon, text}]`.

Rules:
- `overdue` — N tasks past due date
- `packed` — N classes today (>= packed_threshold)
- `neglected-<project>` — vault project not touched in 7+ days

Frontend `NudgeBanner.tsx` — dismissible per-session (sessionStorage). Reappears on next page load by design.

## Frontend layout

```
topbar: logo | clock | ⌘K
hero: greeting h1 | date | search bar | hint pills
NudgeBanner (if any nudges active)
BriefingCard: italic greeting | streak flame | stat pills (next event / overdue / on-this-day)
TodayPanel: schedule | tasks | on-this-day (3rd col appears when notes exist)
```

Time-of-day theming: dawn (5–8), morning (8–12), afternoon (12–17), evening (17–21), night (21–5).
CSS custom properties set on `:root` — `--accent`, `--bg`, `--bg-panel`, `--text`, etc.

## Security (repo is PUBLIC)
- `.gitignore` excludes: vault, data/, *.db, .env, captures/, .venv/, node_modules/
- All secrets in `.env` — never commit
- No server IPs, hostnames, usernames, or Tailscale details in committed files
- Tailscale-only access — no public ports
- Docker runs as root (home lab only — Tailscale is the security perimeter)

## Voice capture safety
`POST /capture` only ever CREATES new timestamped files in `vault/captures/`.
Never edits, overwrites, or deletes existing notes. `captures/` is gitignored.
