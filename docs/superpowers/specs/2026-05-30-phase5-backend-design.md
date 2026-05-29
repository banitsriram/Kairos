# Kairos Phase 5 — Personality & Daily Experience: Backend Design

**Date:** 2026-05-30  
**Scope:** Backend only. Frontend (BriefingCard, TodayPanel 3rd column) built separately by user.

---

## What We're Building

Four features delivered via one new endpoint (`/briefing`) and one lightweight endpoint (`/heartbeat`):

1. **Personality greeting** — context-aware text from `personality.yaml`, template-rendered
2. **Morning briefing** — next event, overdue count, assembled into the `/briefing` response
3. **Streaks** — daily activity log (opens + captures), streak count + bonus flag
4. **On-this-day** — vault notes whose filename matches today's month-day from a prior year

The frontend calls `/briefing` once on load and gets everything it needs to render the BriefingCard. It also fires a silent `POST /heartbeat` to record the open.

---

## New Endpoints

### `GET /briefing`

Returns a single structured object. No query params.

```json
{
  "greeting": "4 classes and 2 overdue tasks. You love chaos.",
  "context": {
    "n_classes": 4,
    "next_event": { "name": "CS101", "time": "10:00", "minutes_away": 23 },
    "overdue_count": 2,
    "neglected_project": { "name": "Kairos", "days": 7 }
  },
  "streak": {
    "count": 4,
    "bonus": false
  },
  "on_this_day": [
    { "path": "vault/cs/2025-05-30.md", "title": "Started OS notes", "year": 2025 }
  ]
}
```

If Notion is unavailable: `context` fields default to `0`/`null`, greeting falls back to `default` bucket.  
If `personality.yaml` is missing: hardcoded fallback lines used.

### `POST /heartbeat`

No body. Upserts `activity_log` row for today, increments `opened`. Returns `{"ok": true}`.  
Never returns an error to the client (catches all exceptions internally).

---

## Database Changes (`db.py`)

New table added to `init_db()`:

```sql
CREATE TABLE IF NOT EXISTS activity_log (
  date     TEXT PRIMARY KEY,   -- ISO date: "2026-05-30"
  opened   INTEGER DEFAULT 0,
  captured INTEGER DEFAULT 0
);
```

Existing `POST /capture` in `main.py` gets one added line to increment `captured` for today.

---

## New Module: `backend/briefing.py`

Owns all Phase 5 logic. Four responsibilities:

### 1. Config loader
Reads `personality.yaml` from path in env var `PERSONALITY_CONFIG` (default: `./personality.yaml`).  
Falls back to hardcoded defaults if file missing or malformed.

### 2. Context gatherer
Calls `get_today()` (existing Notion client) and extracts:
- `n_classes`: count of schedule events today
- `next_event`: soonest event with computed `minutes_away`
- `overdue_count`: tasks where due date < today and status != Done

Queries `notes_meta` for neglected projects. Vault paths are stored without a prefix (e.g. `cs/2025-05-30.md`); Notion entries use `notion/` prefix — we exclude those and group by first path component:
```sql
SELECT substr(path, 1, instr(path, '/') - 1) AS project,
       MAX(mtime) AS last_touch
FROM notes_meta
WHERE path NOT LIKE 'notion/%'
  AND path LIKE '%/%'
GROUP BY project
HAVING (strftime('%s','now') - last_touch) / 86400.0 >= ?
ORDER BY last_touch ASC
LIMIT 1
```
`mtime` is a Unix epoch float, so comparing against `strftime('%s','now')` (also epoch) works directly. The `path LIKE '%/%'` guard skips root-level notes that aren't in a project subfolder. Returns the most-neglected project (or `None`).

### 3. Greeting picker
Determines bucket in priority order:
1. `project_neglected` — if a neglected project exists
2. `packed_day` — if `n_classes >= packed_threshold` (config, default 3)
3. `empty_day` — if `n_classes == 0`
4. `default` — otherwise

Picks a random line from the bucket. Renders template slots:
`{n_classes}`, `{overdue}`, `{project}`, `{days}`, `{next_event}`.

### 4. Streak calculator
```sql
SELECT date, opened, captured FROM activity_log
WHERE date <= ? ORDER BY date DESC LIMIT 60
```
Walks backwards from today: counts consecutive days where `opened > 0`.  
`bonus = True` if today's row has `captured > 0`.

### 5. On-this-day query
Vault notes have no path prefix; Notion entries start with `notion/`. Join with `notes_fts` to get the title (it's not in `notes_meta`):
```sql
SELECT m.path, f.title
FROM notes_meta m
JOIN notes_fts f ON f.path = m.path
WHERE m.path NOT LIKE 'notion/%'
  AND m.path LIKE '%-MM-DD%'
  AND m.path NOT LIKE '%-YYYY-%'
ORDER BY m.mtime DESC
LIMIT 5
```
`MM-DD` = today's month-day (e.g. `05-30`), `YYYY` = current year (excludes current year).  
Returns up to 5 results, most recently touched first.

---

## Config File: `backend/personality.yaml`

Committed to the repo with defaults. User edits on server without touching code.

```yaml
sass_level: 2  # 1–5 (stored in /briefing response for future frontend use)

context:
  packed_threshold: 3
  neglected_days: 7

greetings:
  packed_day:
    - "You have {n_classes} classes today. Godspeed."
    - "{n_classes} classes and {overdue} overdue. You love chaos."
    - "Packed schedule. Remember to eat."
  empty_day:
    - "Light day. Don't waste it."
    - "Only {n_classes} things scheduled. No excuses."
    - "You've got space to think. Use it."
  project_neglected:
    - "{project} misses you. It's been {days} days."
    - "You haven't touched {project} in {days} days. Just saying."
    - "{project} is gathering dust. {days} days."
  default:
    - "Here's your day."
    - "Let's get it."
    - "Make it count."

motivation:
  - "Small steps compound."
  - "You showed up. That's already something."
  - "Progress, not perfection."
```

---

## Modified Files

| File | Change |
|------|--------|
| `backend/db.py` | Add `activity_log` table to `init_db()` |
| `backend/main.py` | Add `GET /briefing` and `POST /heartbeat` routes; add capture increment to `POST /capture` |
| `backend/requirements.txt` | Add `PyYAML` |

## New Files

| File | Purpose |
|------|---------|
| `backend/briefing.py` | All Phase 5 logic |
| `backend/personality.yaml` | Default personality config |
| `tests/test_briefing.py` | Unit tests |

---

## Tests (`tests/test_briefing.py`)

| Test | Assertion |
|------|-----------|
| `test_bucket_packed` | n_classes=4 → `packed_day` bucket |
| `test_bucket_empty` | n_classes=0 → `empty_day` bucket |
| `test_bucket_neglected` | neglected project exists → `project_neglected` bucket (highest priority) |
| `test_bucket_default` | n_classes=1, no neglect → `default` bucket |
| `test_template_render` | `"You have {n_classes} classes"` + context → `"You have 4 classes"` |
| `test_template_unknown_slot` | `{foo}` in template → left as-is |
| `test_streak_consecutive` | 4 consecutive open days → count=4 |
| `test_streak_gap` | Gap 3 days ago → count=3 (not 4) |
| `test_streak_bonus` | captured > 0 today → bonus=True |
| `test_on_this_day` | Seed `notes_meta` with `vault/cs/2025-05-30.md` → returned for May 30 query |
| `test_on_this_day_excludes_current_year` | `vault/cs/2026-05-30.md` → not returned |

---

## Error Handling Summary

| Failure | Behaviour |
|---------|-----------|
| Notion API down | Skip context, use `default` greeting bucket, `next_event=null`, `overdue_count=0` |
| `personality.yaml` missing/malformed | Use hardcoded fallback lines (3 per bucket) |
| SQLite error in streak query | Return `streak: {count: 0, bonus: false}` |
| SQLite error in on-this-day query | Return `on_this_day: []` |
| `/heartbeat` any exception | Swallow, return `{"ok": true}` always |
