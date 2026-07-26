# Command Center — session handoff

Last updated: 2026-07-26. Paste the block below into a fresh Claude Code session
run from `~/command-center`.

---

```
Continue building Command Center. Repo: ~/command-center. Read PHASES.md for the
roadmap, HANDOFF.md for where we stopped, and CONNECTORS.md for what each data
source actually returns.

Phase 0 and Phase 1 are built. Two things are waiting on me — read
PROJECT_LIST_PROPOSAL.md and tell me what's wrong with the project list, then
pick up at Phase 2.
```

---

## Where things stand

| Phase | State |
|---|---|
| 0 — Light recon | ✅ built · **waiting on your sign-off** |
| 1 — Dashboard | ✅ built and rendering |
| 2 — Email triage | not started |
| 3 — Queue, push, schedule | not started |
| 4 — File reorganization | not started (optional per PHASES.md) |

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

**2. Two credential actions are yours alone.**
- WhatsApp is logged out. `cd ~/whatsapp-mcp && npm run login`, then scan the QR.
  Until then nothing can read the RLTRS.co group — which is where the $4,000
  question with Steve has to be answered in writing.
- Gmail says the account is out of storage and can no longer send or receive.
  Phase 2 is pointless until that's resolved.

## What was built

```
PHASES.md                        roadmap (yours, unchanged)
PROJECT_LIST_PROPOSAL.md         Phase 0 output — needs your corrections
CONNECTORS.md                    what each data source actually returns
.claude/lib/projects.py          the only parser for memory/projects.md
.claude/lib/feed.py              local state + Calendar; separates "empty" from "unread"
.claude/lib/build_dashboard.py   assembles dashboard/index.html
.claude/lib/tests/               19 tests, all passing
.claude/commands/dashboard.md    /dashboard
dashboard/template.html          the page; __CC_DATA__ is replaced at build time
dashboard/index.html             generated — do not edit by hand
state/needs-me.md                append-only, feeds the NEEDS ME section
```

## Running it

```bash
python3 .claude/lib/build_dashboard.py && open dashboard/index.html
python3 .claude/lib/tests/test_projects.py      # 19 tests
```

`/dashboard` does the full thing: refreshes connectors into `dashboard/feed.json`,
rebuilds, opens, stamps the heartbeat.

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
- `.claude/lib/heartbeat.py` is referenced by `/dashboard` step 4 but is a Phase 5
  deliverable and isn't written yet.
