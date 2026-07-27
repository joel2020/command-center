# Command Center — session handoff

Last updated: 2026-07-26. Paste the block below into a fresh Claude Code session
run from `~/command-center`.

---

```
Continue with Command Center. Repo: ~/command-center. Read PHASES.md for the
roadmap, HANDOFF.md for where we stopped, CONNECTORS.md for what each data source
actually returns.

The project list is approved and the dashboard is complete. The scheduler is
installed and running. One approval gate is still open and waiting on me:
PROPOSED_STRUCTURE.md, the Phase 4 taxonomy. Nothing moves on disk until I
approve it. Walk me through that.
```

---

## Where things stand

| Phase | State |
|---|---|
| 0 — Light recon | ✅ **approved 2026-07-26** · memory/projects.md written |
| 1 — Dashboard | ✅ complete · 8 project cards, connectors loaded |
| 2 — Email triage | ✅ built · classifier rebuilt against real mail 2026-07-26 |
| 3 — Queue, push, schedule | ✅ built · **scheduler installed and loaded** |
| 4 — File audit | ✅ audit run · **taxonomy waiting on your approval** |

223 tests, all passing: `python3 .claude/lib/tests/run_all.py`

## What's blocking

**1. The taxonomy needs your approval.**
`PROPOSED_STRUCTURE.md`. Nothing moves until you say so. Three open questions in
it — which side of the Desktop/Downloads duplication wins, whether `Alex music` is
yours, and whether `Documents/Codex` is worth keeping.

**2. Two credential actions are yours alone.**
- WhatsApp is logged out. `cd ~/whatsapp-mcp && npm run login`, then scan the QR.
  Until then nothing can read the RLTRS.co group.
  (The $4,000 question this used to block is **resolved** — the Jul 16 Granola
  transcript confirms $4,000 plus $500 every Friday until completion, so the
  payment-schedule PDF is safe to send.)
- Google One storage. The earlier note here said the account was out of storage
  and could no longer send or receive; the Jul 26 notice actually says **87%
  full**, so it is approaching the limit, not past it. Still worth clearing
  before it stops receiving.

**3. Two real items surfaced by the first connector pull, neither tracked anywhere.**
- A Google Voice voicemail claiming an Apple account confirmation from **Baghdad,
  Iraq** — either a phishing pattern or a live takeover attempt. Flagged
  `security` severity, which is above `high`.
- **Eye appointment Wed 2026-07-29, 10:00am**, Dr. Sanseverino at Optic Gold.
  Confirmed by email, absent from Calendar.app. Nothing else will remind you.

## What was built

```
PHASES.md                        roadmap (yours; only the status line was updated)
PROJECT_LIST_PROPOSAL.md         Phase 0 output — APPROVED, see memory/projects.md
CONNECTORS.md                    what each data source actually returns
FILE_AUDIT.md                    Phase 4 measurements, read-only
PROPOSED_STRUCTURE.md            taxonomy — needs your approval
DO_NOT_TOUCH.md                  hard exclusions, enforced in filing.py

.claude/lib/projects.py          sole parser for memory/projects.md
.claude/lib/movement.py          derives real last-movement from git + Linear
.claude/lib/outcomes.py          append-only outcome log; the two missing metrics
.claude/lib/feed.py              local state + Calendar; "empty" ≠ "couldn't read"
.claude/lib/build_dashboard.py   assembles dashboard/index.html
.claude/lib/triage.py            ACT/FYI/NOISE/UNSURE; no send/delete code path
.claude/lib/queue.py             cap 10, 40% floor, 7d expiry, 30d dedupe
.claude/lib/push.py              macOS notify + Twilio, 2/week cap, off by default
.claude/lib/heartbeat.py         stamps state/heartbeat.json
.claude/lib/audit.py             read-only filesystem audit
.claude/lib/filing.py            plan/apply; refuses anything plan() didn't approve
.claude/lib/tests/run_all.py     223 tests
.claude/lib/tests/fixtures/      42 real inbox threads, hand-labeled
scheduler/install.sh             launchd agents; --load / --unload
.claude/bin/run-scheduled.sh     headless task runner used by launchd

.claude/commands/                dashboard, triage, queue, file,
                                 morning-brief, evening-digest, weekly-review
dashboard/template.html          the page; __CC_DATA__ replaced at build time
dashboard/index.html             generated — do not edit by hand
```

## Running it

```bash
python3 .claude/lib/tests/run_all.py                          # 127 tests
python3 .claude/lib/build_dashboard.py && open dashboard/index.html
python3 .claude/lib/heartbeat.py --status
python3 .claude/lib/audit.py                                  # read-only
```

Commands: `/dashboard` `/triage` `/queue` `/file` `/morning-brief` `/evening-digest`
`/weekly-review`

## Schedule — INSTALLED and loaded 2026-07-26

launchd agents, `com.joel.commandcenter.*`, written by `scheduler/install.sh --load`:

| Task | When | Command |
|---|---|---|
| morning-brief | 6:00am Mon–Fri | `/morning-brief` |
| email-triage | every 3600s | `/triage` |
| evening-digest | 6:00pm daily | `/evening-digest` |
| weekly-review | 5:00pm Sunday | `/weekly-review` |

```bash
launchctl list | grep com.joel.commandcenter     # is it loaded
python3 .claude/lib/runs.py health                # is it healthy
scheduler/install.sh --unload                     # stop everything, fully reversible
```

Each run goes through `.claude/bin/run-scheduled.sh`, which stamps the heartbeat,
records the outcome to `state/run-log.jsonl`, and always exits 0 — a non-zero exit
would make launchd retry blindly, which is worse than recording the failure and
waiting for the next slot.

**Triage is still in the label-only window.** `state/triage-mode.json` has
`archive_enabled: false`, and the 14-day clock starts on the first real run.
Nothing gets archived until Joel flips that flag by hand — time passing is not
consent. Note that the first hourly run will label real mail in Gmail.

launchd does not run agents while the Mac is asleep. A missed
StartCalendarInterval fires once on wake; StartInterval resumes on its normal
cadence. The heartbeat shows the gap either way.

## Design rule that governs everything

**"Nothing to do" and "I couldn't look" are different answers, and the page must
never confuse them.** Every section that fails to read its source says so in red.
The header turns red when connector data is missing, stale, or of unknown age.
Two bugs were already caught by this rule — the calendar silently reporting an
empty week when Calendar.app simply wasn't running, and the TODAY section claiming
the calendar was "genuinely empty" in the same breath as saying it was unavailable.

## Known gaps

- **Headless runs are permission-blocked.** The first live test of
  `run-scheduled.sh` had Bash and every MCP connector denied, so the brief was
  written from a stale feed and nothing was refreshed, built, or stamped.
  `.claude/settings.json` has `defaultMode: auto` and an **empty allow list**;
  scheduled runs need one before they can do anything. See "Scheduler" above.
- `dashboard/feed.json` doesn't exist until `/dashboard` runs, so the header reads
  `connectors NOT LOADED`. That's correct, not a bug.
- Slack and Notion have no MCP server connected. Those sections are omitted rather
  than rendered empty.
- `~/TASKS.md` doesn't exist. TODAY now reads it and reports it as unavailable
  rather than silently skipping it — create the file and it starts feeding TODAY.
- Your calendar has 3 real events in 90 days, all holidays. TODAY leans on Linear
  due dates and Granola instead — see CONNECTORS.md.
- SMS is unconfigured and off. macOS notifications work — verified live.
- Triage is in the label-only window and `state/triage-mode.json` has `started: null`,
  so the 14-day clock starts on the first real `/triage` run.
- Three projects report `declared` movement because they have no readable git repo
  or Linear project: RLTRS (the vault is not a repo), Alivio Supabase consolidation,
  and whatsapp-mcp. Their staleness is Joel's word, uncorroborated.
