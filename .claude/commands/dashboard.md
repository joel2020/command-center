---
description: Refresh connectors and rebuild dashboard/index.html
---

Refresh the Command Center dashboard, then open it.

## 1. Collect connector data

Call each of these once and write the results to `dashboard/feed.json`.
If a connector fails, record it as unavailable **with the reason** — never as empty.

- **Gmail** — `search_threads` with `in:inbox newer_than:7d`, up to 50.
  Classify each thread per `memory/email-rules.md` into ACT / FYI / NOISE / UNSURE.
  Only ACT items go in `gmail.act`. Do not label or archive here — that's `/triage`.
- **Linear** — `list_issues` ordered by `updatedAt`, limit 50. Keep everything whose
  `statusType` is not `completed`, plus anything with a `dueDate` in the next 7 days.
- **Granola** — `list_meetings` for `this_week`. Titles only; don't fetch transcripts.
- **Loose ends** — commitments visible in the Gmail threads and Granola titles that
  don't appear in Linear or `memory/projects.md`. Something Joel said he'd do that
  isn't tracked anywhere. Be conservative: a real promise, not a maybe.

Write `dashboard/feed.json`:

```json
{
  "generated_at": "<ISO 8601 with offset>",
  "gmail":   {"available": true, "act": [{"subject","sender","date","severity"}]},
  "linear":  {"available": true, "issues": [{"id","title","status","statusType","project","dueDate","url"}]},
  "granola": {"available": true, "meetings": [{"id","title","date"}]},
  "loose_ends": {"available": true, "items": [{"text","source","date","detail"}]}
}
```

`severity` is `high` only for money, legal, or a deadline inside 24 hours.

## 2. Build

```bash
python3 .claude/lib/build_dashboard.py
```

Reads `memory/projects.md`, `state/heartbeat.json`, `state/automation-log.jsonl`,
`state/needs-me.md`, and queries Calendar via AppleScript. Writes a self-contained
`dashboard/index.html`.

## 3. Open

```bash
open dashboard/index.html
```

## 4. Stamp the heartbeat

```bash
python3 .claude/lib/heartbeat.py morning-brief
```

Only stamp the task you actually ran.

## Rules

- PROJECTS renders only what's in `memory/projects.md`. Never add a project here.
- Anything done at under 90% confidence goes in `state/needs-me.md`.
- Calendar conflicts are flagged, never resolved.
