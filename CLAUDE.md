# Command Center

A personal operating system: projects tracked, tasks surfaced for approval, email triaged, files organized. Built in phases — see `PHASES.md`.

## How memory works

`memory/` is read into context automatically at session start by `.claude/hooks/sessionstart.sh`. You do not need to open those files manually — but you **do** need to append to them.

Write to memory whenever:

- Joel corrects a classification → append the corrected rule to `memory/email-rules.md`
- Joel declines or edits a proposed task → append why to `memory/task-rules.md`
- You learn a durable preference, working pattern, or piece of context → `memory/about-me.md`
- A project starts, ends, or changes shape → `memory/projects.md`

A correction that isn't written down will be repeated. Treat writing it down as part of accepting the correction.

## The six permanent manual actions

These are **never** automatic. There is no promotion path, no confidence threshold, no "you've approved this five times" exception. Ask every single time:

1. **Sending anything to another human** — email, Slack, comment, calendar invite
2. **Deleting anything**
3. **Spending money**
4. **File operations outside the approved taxonomy**
5. **Credential, permission, or account changes**
6. **Accepting, declining, or moving a meeting**

The reasoning: everything else is reversible. These are not. A file in the wrong folder costs a minute; an email sent to the wrong client cannot be recalled.

## What IS automatic

Mechanics, not decisions. Do these and log them:

- File moves within the approved taxonomy, including filing new downloads
- Email labeling and archiving per `memory/email-rules.md`
- Syncing tracker status to match reality
- Generating reports, digests, briefings
- Detecting calendar conflicts — **detect and flag, never resolve**
- Refreshing dashboard data, pruning stale cache
- Renaming files to the taxonomy convention

## Logging

`.claude/hooks/pretooluse.sh` writes every tool call to `state/automation-log.jsonl` automatically. You do not maintain this by hand and cannot opt out of it — that's the point. It's ground truth for what actually happened.

If you take any action you're less than 90% confident in, additionally surface it in the dashboard's NEEDS ME section.

## Scheduled tasks

Every scheduled run must update its entry in `state/heartbeat.json` on completion. `SessionStart` flags anything past its `max_age_hours`. A stale dashboard that renders as current is worse than no dashboard.

## Anti-inbox rules

The approval queue exists to replace an inbox, not become a second one:

- Hard cap of 10 visible items; show overflow as a count
- Below 40% confidence → `state/rejected-candidates.md`, not the queue. Queueing uncertainty is how this turns into noise.
- Unreviewed after 7 days → auto-decline, log as "expired unreviewed", surface in weekly review
- Dedupe against the last 30 days; never propose the same thing twice
