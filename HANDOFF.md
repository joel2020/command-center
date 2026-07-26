# Command Center — session handoff

Last updated: 2026-07-26. Paste the block below into a fresh Claude Code session
run from `~/command-center`.

---

```
Continue with Command Center. Repo: ~/command-center. Read PHASES.md for the
roadmap, HANDOFF.md for where we stopped, CONNECTORS.md for what each data source
actually returns.

All five phases are built and tested (127 tests). Two approval gates are open and
waiting on me: PROJECT_LIST_PROPOSAL.md and PROPOSED_STRUCTURE.md. Walk me through
the project list first.
```

---

## Where things stand

| Phase | State |
|---|---|
| 0 — Light recon | ✅ built · **waiting on your sign-off** |
| 1 — Dashboard | ✅ built and rendering |
| 2 — Email triage | ✅ built · validated against your real inbox |
| 3 — Queue, push, schedule | ✅ built · notification channel live-tested |
| 4 — File audit | ✅ audit run · **taxonomy waiting on your approval** |

127 tests, all passing: `python3 .claude/lib/tests/run_all.py`

## What's blocking

**1. The project list needs your corrections.**
`PROJECT_LIST_PROPOSAL.md` proposes 9 active and 4 dormant projects with evidence
for each. PHASES.md says *"Do not proceed without sign-off"*, so `memory/projects.md`
is still empty and the dashboard's PROJECTS section correctly shows nothing.

Fastest path: open that file, fix what's wrong, and say "approved." The corrected
list gets written to `memory/projects.md` and the dashboard fills in.

Three questions in it that I can't answer for you:
- What is `~/stable-lights-creations`? Second-most-recent commit you have, no README.
- Is the job search a real project or noise? It changes email triage significantly.
- Are `~/alivio-search-partners` and `~/orchids-aliviosearch-com` separate projects,
  or part of Alivio Search Partners? I folded them in.

**2. The taxonomy needs your approval.**
`PROPOSED_STRUCTURE.md`. Nothing moves until you say so. Three open questions there
too — which side of the Desktop/Downloads duplication wins, whether `Alex music` is
yours, and whether `Documents/Codex` is worth keeping.

**3. Two credential actions are yours alone.**
- WhatsApp is logged out. `cd ~/whatsapp-mcp && npm run login`, then scan the QR.
  Until then nothing can read the RLTRS.co group — which is where the $4,000
  question with Steve has to be answered in writing.
- Gmail says the account is out of storage and can no longer send or receive.
  Triage runs fine, but against a mailbox that can't receive.

## What was built

```
PHASES.md                        roadmap (yours; only the status line was updated)
PROJECT_LIST_PROPOSAL.md         Phase 0 output — needs your corrections
CONNECTORS.md                    what each data source actually returns
FILE_AUDIT.md                    Phase 4 measurements, read-only
PROPOSED_STRUCTURE.md            taxonomy — needs your approval
DO_NOT_TOUCH.md                  hard exclusions, enforced in filing.py

.claude/lib/projects.py          sole parser for memory/projects.md
.claude/lib/feed.py              local state + Calendar; "empty" ≠ "couldn't read"
.claude/lib/build_dashboard.py   assembles dashboard/index.html
.claude/lib/triage.py            ACT/FYI/NOISE/UNSURE; no send/delete code path
.claude/lib/queue.py             cap 10, 40% floor, 7d expiry, 30d dedupe
.claude/lib/push.py              macOS notify + Twilio, 2/week cap, off by default
.claude/lib/heartbeat.py         stamps state/heartbeat.json
.claude/lib/audit.py             read-only filesystem audit
.claude/lib/filing.py            plan/apply; refuses anything plan() didn't approve
.claude/lib/tests/run_all.py     127 tests

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

## Schedule (per PHASES.md, not yet installed as cron)

6am weekdays `/morning-brief` · hourly `/triage` · 6pm `/evening-digest` ·
Sunday 5pm `/weekly-review`. Each stamps the heartbeat on completion.

## Design rule that governs everything

**"Nothing to do" and "I couldn't look" are different answers, and the page must
never confuse them.** Every section that fails to read its source says so in red.
The header turns red when connector data is missing, stale, or of unknown age.
Two bugs were already caught by this rule — the calendar silently reporting an
empty week when Calendar.app simply wasn't running, and the TODAY section claiming
the calendar was "genuinely empty" in the same breath as saying it was unavailable.

## Known gaps

- `dashboard/feed.json` doesn't exist until `/dashboard` runs, so the header reads
  `connectors NOT LOADED`. That's correct, not a bug.
- Slack and Notion have no MCP server connected. Those sections are omitted rather
  than rendered empty.
- `~/TASKS.md` doesn't exist. PHASES.md lists it as a data source.
- Your calendar has 3 real events in 90 days, all holidays. TODAY leans on Linear
  due dates and Granola instead — see CONNECTORS.md.
- The four scheduled runs exist as commands but **nothing schedules them yet.** No
  cron, no launchd. `heartbeat.json` will keep reporting "never run" until either you
  run them by hand or a scheduler is installed. That's honest, not broken.
- SMS is unconfigured and off. macOS notifications work — verified live.
- Triage is in the label-only window and `state/triage-mode.json` has `started: null`,
  so the 14-day clock starts on the first real `/triage` run.
