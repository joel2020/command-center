# Jarvis — live agent cockpit for Command Center

Design, 2026-07-26. Status: awaiting Joel's review.

## The goal, in Joel's words

> "I want this to be like a Jarvis where I see every single agent running and I can
> jump into individual projects, see what's done and what has to be done next, and
> have things running automatically."

Plus: an ElevenLabs British butler voice.

Today the dashboard is a static HTML file rebuilt by `build_dashboard.py`. It shows
projects, mail, and schedule health — but nothing about the agents actually doing
work, and it only changes when something rebuilds it. This turns it into a live
cockpit over the work already happening on the machine.

## What already exists (verified, not assumed)

Every signal this needs is already written to disk by Claude Code. Nothing here
requires new instrumentation.

| Source | Gives us | Verified |
|---|---|---|
| `~/.claude/sessions/<pid>.json` | pid, sessionId, cwd, name, kind, `status` (busy/idle), startedAt, updatedAt | 3 live sessions read |
| `~/.claude/tasks/<sessionId>/*.json` | per-agent task list: subject, status, blockedBy | read real task files |
| `~/.claude/projects/<slug>/<sessionId>.jsonl` | full transcript; tail = current action | read a live Bash call, 8s old |
| `memory/projects.md` `- repos:` | maps a `cwd` to one of Joel's projects | added 2026-07-26 |

`claude agents --json` returns the same roster, but shelling out on every 2-second
poll is wasteful. Read the session files directly and use the CLI only as a
fallback if the directory is unreadable.

The `cwd` → project join is what makes this a cockpit rather than a process list:
an agent working in `~/alivio-platform` appears *on the Alivio Search Partners
card*, not in an unrelated list of PIDs.

## Control: what is real and what is not

Verified against Claude Code 2.1.220.

| Verb | Mechanism | Available |
|---|---|---|
| Stop a session | `SIGTERM` to pid; transcript persists, session resumable | Yes |
| Dispatch new work | `claude --bg -p "<task>"` with `cwd` set to the project | Yes |
| Resume an idle session with a message | `claude --resume <sessionId> -p "<msg>"` | Yes |
| Inject into a **busy** session mid-turn | none supported | **No** |

The session registry advertises `peerProtocol: 1`, so internal peer messaging
exists, but it is private and undocumented. Building the control plane on it would
break on the next Claude Code upgrade, and a cockpit that silently stops working
is worse than one that never claimed the feature.

**Substitute, and it is the better design anyway:** a message sent to a busy agent
is queued in `state/agent-inbox.jsonl` and delivered via `--resume` the moment that
agent's status flips to idle. The queue is visible in the UI with its pending
count, so a queued message never looks like a delivered one. Interrupting an agent
between tool calls is how half-finished work gets corrupted; a few seconds of
latency buys correctness.

## Architecture

Four new units, each with one job and testable alone. This mirrors the existing
split where `feed.py` reads, `build_dashboard.py` assembles, and `projects.py` owns
one format.

### `.claude/lib/agents.py` — the roster

Pure reads, no subprocess in the hot path.

- `roster()` — parse `~/.claude/sessions/*.json`, drop entries whose pid is dead
  (`os.kill(pid, 0)`), return live agents.
- `tasks_for(session_id)` — read `~/.claude/tasks/<id>/*.json`, split into done /
  in-progress / next (first `pending` with no unmet `blockedBy`).
- `last_action(session_id, cwd)` — seek to the last ~64KB of the transcript,
  parse trailing JSONL, return the most recent `tool_use` as `{tool, summary, ts}`.
  Never read the whole file; transcripts reach 10MB.
- `join_projects(agents, projects)` — match each `cwd` against every project's
  `repos` list, longest path wins so `~/alivio-platform` beats `~`.

Failure is reported, never silently zero. If the sessions directory cannot be read
the roster returns `{"available": false, "reason": ...}` and the panel says so in
red. **"No agents running" and "I couldn't look" are different answers** — the rule
that already governs this codebase, extended to agents.

### `.claude/lib/voice.py` — the butler

- ElevenLabs, voice `JBFqnCBsd6RMkjVDRZzb` (George, british/middle_aged/male,
  "warm, captivating"). Alternate: `onwK4e9ZLuTAKqWW03F9` (Daniel, colder read).
- Key lives in `state/voice-config.json`, gitignored, same pattern as
  `push-config.json`. Never in the repo.
- `say(text)` returns a cached MP3 path, keyed on `sha1(voice_id + text)` under
  `state/voice-cache/`. Repeated lines cost zero credits.
- Degrades to silent + logged when the key is missing or the API fails. The
  cockpit never blocks on audio.

### `.claude/lib/serve.py` — the server

`http.server.ThreadingHTTPServer` bound to `127.0.0.1:7777`. Standard library
only; this repo has no dependencies and should not gain any.

| Route | Does | Token |
|---|---|---|
| `GET /` | the dashboard page, with the token embedded | no — chicken-and-egg |
| `GET /api/state` | full state: agents, projects, today, needs-me, in-flight | yes |
| `POST /api/control` | one of the four verbs below | yes |
| `POST /api/speak` | `{text}` → cached audio | yes |
| `GET /api/audio/<hash>` | serves a cached MP3 | yes |

The four control verbs:

| Verb | Target | Effect |
|---|---|---|
| `stop` | sessionId | SIGTERM to that pid |
| `dispatch` | project name | `claude --bg -p "<message>"` with `cwd` = project's first repo |
| `resume` | sessionId | `claude --resume <id> -p "<message>"`, idle agents only |
| `send` | sessionId | idle → same as `resume`; **busy → queued** to `agent-inbox.jsonl` and delivered on the next idle transition |

`send` is the verb the UI uses when Joel types at an agent. It never fails for
being busy; it queues and says so.

`GET /` is unauthenticated because it must be — the page is where the token comes
from. It serves markup only, no state, so an attacker fetching it learns nothing
they could not learn by reading this repo.

`/api/state` reuses `build_dashboard.build()` for everything that already works,
plus the agent roster. One code path, so the live view and any static rebuild can
never disagree.

### `dashboard/` — the page

Same file, extended. Polls `/api/state` every 2s and patches the DOM in place
rather than re-rendering, so a click doesn't get eaten mid-poll. New AGENTS panel
at the top; project cards gain an agent count and expand to show tasks, open
Linear issues, and next action.

Falls back to the static build when the server is not running, with the header
saying "static — server not running" rather than pretending it is live.

## Security

The current dashboard is an inert file. This one kills processes and spawns agents,
so it needs a real threat model.

- **Bind `127.0.0.1` only.** Never `0.0.0.0`. Asserted in a test, because this is
  the single change that would expose process control to the local network.
- **Token on every POST.** Generated on first run into `state/server-token`
  (gitignored, mode 600), embedded in the served page. Without it, any website
  open in Joel's browser could `fetch('http://localhost:7777/api/control')` and
  stop his agents — a same-origin policy does not prevent the request being sent.
  GETs of state are also gated; the roster reveals working directories.
- **Every control action is logged** to `state/control-log.jsonl` with verb,
  target, timestamp, and outcome. Same append-only ground-truth pattern as
  `automation-log.jsonl`.
- **Stop is SIGTERM, never SIGKILL.** The session flushes its transcript and stays
  resumable. Destroying work is not a thing a dashboard button should do.
- **The six manual actions are untouched.** Dispatching an agent does not grant it
  permission to send, delete, or spend. Those gates live in the dispatched agent's
  own settings and this feature does not reach into them.

## Voice policy

Joel chose all four triggers. Lifecycle announcements are the chatty one, so they
ship with a cap rather than unbounded.

| Trigger | Speaks |
|---|---|
| On demand | whenever asked |
| Morning brief | the 6am brief, once |
| Push-worthy | only what already clears `push.py` — money/legal inside 4h, a task failed twice, a queue item expiring |
| Agent lifecycle | an agent finishing or failing |

Lifecycle is rate-limited: only agents that ran longer than 60s, at most 6
announcements per hour, failures always beating completions when the cap is hit.
Configurable in `voice-config.json`; the default is deliberately low and Joel can
raise it once he knows how it feels. A butler that reads out every tool call gets
muted on day one, and a muted butler is worth nothing.

Cap breaches are logged, never silently dropped — consistent with the "no silent
caps" rule the NEEDS ME overflow counter already follows.

## Testing

Everything except the HTTP layer is pure functions over fixture directories.

- `agents.py`: a fake `~/.claude` tree — live pid, dead pid, unreadable dir,
  malformed JSON, 10MB transcript. Assert dead pids are dropped, unreadable
  reports `available: false`, and the tail parser never reads the whole file.
- `cwd` → project join: nested paths, no match, `~` as a repo, longest-path-wins.
- `voice.py`: cache hit returns without an API call; missing key degrades silent;
  the rate limiter drops completions before failures.
- `serve.py`: binds loopback only; POST without a token is 403; every verb writes
  a `control-log` line.
- The existing 223 tests must keep passing. `build_dashboard.build()` stays the
  single assembler.

## Out of scope, deliberately

- **Streaming full transcripts into the browser.** Real plumbing for something read
  for ten seconds. Last action plus task list answers "what is it doing"; the
  drill-down opens the real session for detail.
- **Remote access.** Loopback only. Remote Control already exists for that and is
  Anthropic's problem to secure, not this repo's.
- **Voice input.** Butler speaks; he does not listen. Wake-word capture is a
  separate project with its own privacy questions.
- **Rebuilding `claude agents`.** Its TUI already does the roster. This exists to
  join agents to Joel's projects, Linear issues, and next actions — the part
  nothing else can do.

## Dependencies

- **The permission allowlist is still unapproved** (task #5). It does not block
  this build — the cockpit reads local state and needs no MCP — but "things running
  automatically" stays broken until it lands, because every scheduled run is
  currently permission-denied. Worth doing first; it is a two-minute change.
- ElevenLabs key exists and was verified against `/v1/voices`. It must be copied
  from `~/clara/.env.local` into `state/voice-config.json`.

## Build order

1. `agents.py` + tests — the roster, joined to projects. Useful alone.
2. `serve.py` read-only — `GET /api/state`, loopback, token. Cockpit goes live.
3. Live front end — AGENTS panel, 2s polling, project drill-down.
4. Control — stop / dispatch / resume / queued send, with the control log.
5. `voice.py` — on-demand first, then the three automatic triggers.
6. launchd agent so it starts at login.

Each step ships something usable, and control does not land until the read-only
view has proven the roster is correct.
