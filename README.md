<p align="center">
  <img src="frontend/src/assets/hero.png" width="130" alt="Kairos logo">
</p>

<h1 align="center">Kairos ⏳</h1>

<p align="center">
  A self-hosted personal "second brain" life dashboard — your Obsidian notes,<br>
  Notion schedule, and quick captures in one fast, beautiful page.
</p>

---

A **self-hosted personal "second brain" life dashboard** — your Obsidian notes, Notion schedule, and quick captures unified into one fast, beautiful page that feels alive, occasionally funny, and quietly motivating.

Runs on a home-lab server, reachable from any device over [Tailscale](https://tailscale.com) — **never exposed to the public internet**.

## What it does

- **🔎 Unified search** — full-text search across your Obsidian vault *and* Notion tasks/schedule in one box (SQLite FTS5, BM25-ranked).
- **📅 Today at a glance** — schedule, top tasks, and "on this day" notes from past years in a single panel.
- **🧠 Personality layer** — a context-aware greeting that reacts to your day: a packed schedule, an empty one, or a project you've been neglecting. Sass level is configurable.
- **🔥 Streaks** — counts consecutive days you've shown up, with a bonus for capturing something.
- **💬 Nudges** — gentle, dismissible banners for overdue tasks, packed days, and neglected projects.
- **🎙️ Voice capture** — `⌘K` → speak → it saves a timestamped note to your vault. Only ever *creates* files, never edits or deletes.
- **🎨 Time-of-day theming** — the whole UI shifts palette through dawn → morning → afternoon → evening → night.

## Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI (Python 3.9) |
| Search | SQLite FTS5 (porter + unicode61), embeddings-ready |
| Frontend | React 19 + TypeScript + Vite |
| Vault sync | Syncthing (Mac → server) |
| Reverse proxy | Caddy (`tls internal`) |
| Deploy | Docker Compose, one-command `./deploy.sh` |
| Access | Tailscale only |

## Architecture

```
Obsidian vault ──(Syncthing)──┐
                              ├──► FTS5 index ──► FastAPI ──► React dashboard
Notion (tasks + schedule) ────┘        ▲                          (Caddy + HTTPS,
        re-indexed every 15 min via cron┘                          Tailscale-only)
```

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Liveness check |
| `GET`  | `/search?q=` | FTS5 search across vault + Notion |
| `GET`  | `/tasks` | Notion tasks (`?status=` filter) |
| `GET`  | `/schedule` | Notion schedule (`?date=` filter) |
| `GET`  | `/today` | Today's schedule + top tasks + neglected task |
| `GET`  | `/briefing` | Greeting, streak, on-this-day, nudges |
| `POST` | `/heartbeat` | Record app open (fire-and-forget) |
| `POST` | `/capture` | Save a voice/quick note to the vault |

## Quick start (local dev)

```bash
# Backend
cd backend && python -m venv ../.venv && source ../.venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

Dev uses `tests/sample_vault` as the vault. Copy `.env.example` to `.env` and add your Notion token + database IDs to wire up tasks/schedule.

### Tests

```bash
.venv/bin/pytest tests/ -v
```

### Deploy

`./deploy.sh` from the project root: builds the frontend → rsyncs to the server → `docker compose build` → re-indexes vault + Notion → `docker compose up -d`.

## Security

This repo is public. All secrets and personal data are kept out of it:

- `.env`, the Obsidian `vault/`, the SQLite `data/`, and `captures/` are gitignored.
- No server IPs, hostnames, usernames, or Tailscale details are committed.
- Access is Tailscale-only — no public ports are ever opened.

## License

Personal project, shared for reference. No license granted.
