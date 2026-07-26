# Agent Instructions

Read by Codex, Cursor, Gemini CLI, and any other agent that honors `AGENTS.md`.
Claude Code reads `CLAUDE.md`. **These two files must say the same thing about limits.**
If you change one, change the other.

Full project context: `CLAUDE.md`. Build sequence: `PHASES.md`.

## The six permanent manual actions

Never automatic. No promotion path, no confidence threshold, no exception for having
done it before. Ask every time:

1. **Sending anything to another human** — email, Slack, comment, calendar invite
2. **Deleting anything**
3. **Spending money**
4. **File operations outside the approved taxonomy** (see `PROPOSED_STRUCTURE.md` once
   Phase 4 produces it; until then, outside `~/command-center` counts as outside)
5. **Credential, permission, or account changes**
6. **Accepting, declining, or moving a meeting**

Everything else here is reversible. These are not.

## You are not logged the way Claude Code is

Claude Code has a `PreToolUse` hook writing every tool call to
`state/automation-log.jsonl`. **That hook does not fire for you.** Your actions are
invisible to it.

Because of that, two obligations:

1. **Commit your work.** Git is the cross-agent audit trail — it catches file state
   changes regardless of which agent made them. Uncommitted work by a non-Claude-Code
   agent is genuinely untracked.
2. **Append a line to `state/automation-log.jsonl` yourself** for any action with side
   effects beyond the repo. Same shape:
   ```json
   {"ts":"<ISO8601>","tool":"<what>","target":"<path/url>","session":"codex","undo":"<how>"}
   ```

An action nobody can reconstruct later is worse than an action not taken.

## Working alongside Claude Code

**Don't both edit the same files at once.** Use `git worktree` for parallel work:

```bash
git worktree add ../cc-dashboard -b dashboard   # Claude Code here
git worktree add ../cx-audit     -b audit       # other agent here
```

Merge through git rather than by writing over each other. `memory/` and `state/` are
append-heavy and will conflict badly under concurrent edits — coordinate before touching
either, or stay out of them.

## Memory

`memory/*.md` holds durable context: preferences, corrections, project list, triage
rules. Read them before acting. Append when Joel corrects you — a correction that isn't
written down gets repeated.

You do not get these loaded automatically. Claude Code has a `SessionStart` hook that
injects them; you must read them explicitly.
