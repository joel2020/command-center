# Phases

Run in order. Each produces artifacts the next one reads. Do not skip ahead.

**File reorganization is Phase 4, deliberately.** It's the highest-risk, lowest-return
step — sorting Movies doesn't make Joel more effective, and a mistake there is expensive.
Build the thing that helps, prove it works, then let it touch the drive.

Status (2026-07-26): Phases 0–4 built and tested. **Two approval gates are open and
nothing proceeds past them:** the project list in `PROJECT_LIST_PROPOSAL.md` needs
Joel's corrections before `memory/projects.md` is written, and the taxonomy in
`PROPOSED_STRUCTURE.md` needs approval before a single file moves. See `HANDOFF.md`.

---

## Phase 0 — Light recon (read-only)

Find active work, not the file mess.

- Scan for directories modified in the last 90 days, excluding ~/Library and caches
- Git repos and their last commit date
- Any folder that looks like a client, project, or venture — name them
- Populate `memory/about-me.md` with inferred context
- Propose a PROJECT LIST: 5–12 live projects, each with evidence

Joel corrects the list. The corrected list goes in `memory/projects.md` and becomes the
backbone of everything downstream. **Do not proceed without sign-off.**

---

## Phase 1 — The Command Center

Build `dashboard/index.html` — self-contained, opened with `open dashboard/index.html`.

Before writing any of it: call each connector tool once and inspect the actual response
shape. Build parsers around what was observed, not what was assumed.

Data sources — every one connected: Gmail and all other mail accounts, Google Calendar,
Linear/tracker, Slack, Notion, `~/TASKS.md`, and the approved PROJECT LIST.

For anything NOT authorized, fall back to AppleScript against the native macOS app
(Apple Mail, Calendar, Reminders) rather than rendering an empty section. Write those as
`.scpt` under `.claude/skills/<name>/scripts/`. State which macOS Automation permissions
Joel must grant in System Settings.

Sections, in order:

1. **TODAY** — calendar blocks, what's due, what he said he'd do and hasn't
2. **NEEDS ME** — max 10 items, hard cap
3. **PROJECTS** — one card per item in `memory/projects.md`, nothing else. Shows status,
   next action, who's blocking, last movement, red flag at 7+ days stale.
4. **IN FLIGHT** — what automation ran, plus LAST-RUN TIMESTAMP per scheduled task from
   `state/heartbeat.json`. Renders loud red on a miss.
5. **LOOSE ENDS** — commitments found in email/Slack that never became tasks

localStorage for filter persistence. Chart.js or Grid.js from CDN, everything else inline.

---

## Phase 2 — Email triage

Hourly, not every 30 min — the extra frequency costs tokens and buys nothing.
Buckets, limits, and correction-learning are defined in `memory/email-rules.md`.

**First two weeks: label only, archive nothing.** Show what would have happened, then
turn it on.

---

## Phase 3 — Autonomy, approval queue, push

Queue mechanics and anti-inbox rules are in `CLAUDE.md`. Additional here:

**Push channels** — deliberately hard to trigger.

macOS notification (`display notification`) when: something in ACT has a deadline inside
4 hours; a scheduled task failed twice consecutively; a queue item is about to expire on
something time-sensitive.

SMS via Twilio — genuine emergencies only, max 2/week. If that cap is hit, the threshold
is wrong — say so. Reserved for: money or legal with a same-day deadline; a client
explicitly escalating; anything where missing it today has consequences outlasting today.

If unsure whether something is push-worthy, it isn't.

**Schedule** — 6am weekdays: refresh + briefing. Hourly: triage. 6pm: digest.
Sunday 5pm: weekly review.

**Success metrics, reported every Sunday:**

1. Of NEEDS ME items, what % did Joel act on? Below 50% = over-surfacing.
2. Of NOISE/FYI items, how many did he later dig out of the archive? Above zero = a miss.
3. Queue: approved vs. declined vs. expired. High declines = proposing the wrong things.
4. Projects stale 7+ days.
5. Push notifications sent, and how many were justified in hindsight.

---

## Phase 4 — File reorganization

**Audit first, read-only.** Counts and sizes by folder, 50 largest files, exact
duplicates (SHA-256 + size, not filename), files untouched 2+ years, and DANGER ZONES:
git repos, Xcode projects, virtualenvs, database files, cloud-sync roots, symlinks,
anything with hardcoded path dependencies.

Propose a taxonomy from what was ACTUALLY found — no generic PARA or Johnny-Decimal
template. Name the real projects and clients. Write `FILE_AUDIT.md`,
`PROPOSED_STRUCTURE.md`, `DO_NOT_TOUCH.md`. Stop and ask what's wrong with the taxonomy.

**Execute only after approval:**

- Reversible plan first — a `mv` script plus an inverse undo script. Show the diff
  summary (N files, M folders, X GB) before executing.
- Never move anything inside a git repo, package manager dir, or cloud-sync root. Move
  the repo folder itself, never its contents.
- Deduplicate by hardlinking or quarantining to `~/_QUARANTINE_<date>/`, never deleting.
- Log every operation to `~/organization-log-<date>.jsonl` with before/after paths.
- Any single operation touching 500+ files: pause and confirm.

Order, checkpointing after each: Desktop → Downloads → Documents → Pictures → Movies →
everything else.

**This phase is optional.** If Phases 1–3 work, the file tree may stop mattering — things
become findable through the system rather than the folder structure.
