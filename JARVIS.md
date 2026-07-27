# Jarvis — the live cockpit

**Owner:** Joel · **Trigger:** Always on · **Cadence:** 2s polling · **Last reviewed:** 2026-07-27

Open **http://127.0.0.1:7777/**. It starts at login and stays up.

## What it is

The dashboard, live. Same page as `dashboard/index.html`, but served by
`.claude/lib/serve.py`, which injects a token and turns on 2-second polling. The
AGENTS panel shows every Claude session running on this machine, joined to the
project it is working in, with what it is doing right now and what it has left
to do.

Opened as a plain file it is still the static dashboard. Nothing breaks.

## Control

Each agent card carries two buttons:

| Button | Does |
|---|---|
| **say…** | Message the agent. Delivers immediately if idle; **queues** if busy |
| **stop** | SIGTERM. Transcript preserved, session stays resumable |

Both confirm first. Every action appends to `state/control-log.jsonl`.

**Why "say" queues rather than interrupts.** There is no supported way to inject
a message into a busy session — the registry advertises `peerProtocol: 1` but it
is private and undocumented, so building on it means the cockpit breaks silently
at the next Claude Code update. A queued message is delivered the moment that
agent goes idle, with the pending count visible on its card so a queued message
never looks like a delivered one. Interrupting an agent between tool calls is
how half-finished work gets corrupted; a few seconds of latency buys correctness.

## Security

This is the first component that can kill processes and spawn agents, so:

- **Binds `127.0.0.1` only**, never `0.0.0.0`. Asserted in a test — one
  character is the difference between a personal cockpit and process control
  exposed to the network. Verified unreachable on the LAN IP.
- **Every API route requires a token** from `state/server-token` (mode 600,
  gitignored). Without it, any website open in your browser could
  `fetch('http://localhost:7777/api/control')` and stop your agents — the
  same-origin policy does not stop the request being sent, and a stop needs no
  readable reply.
- `GET /` is unauthenticated by necessity: it is where the token comes from. It
  serves markup only.
- **SIGTERM, never SIGKILL.**
- The six manual actions are untouched. Dispatching an agent grants it nothing.

## The butler

`state/voice-config.json` — gitignored, created on first run, **disabled by
default**.

To enable: set `enabled: true` and paste the ElevenLabs key (it is in
`~/clara/.env.local`). Voice is **George** — british, middle-aged, warm.
Alternate is Daniel (`onwK4e9ZLuTAKqWW03F9`), a colder broadcast read.

Triggers: on demand, morning brief, push-worthy events, and agent lifecycle.
Lifecycle is the chatty one, so it ships capped — agents that ran over 60s, six
announcements an hour, failures beating completions when the cap binds. Raise it
once you know how it feels. **Cap breaches are logged, never silently dropped.**

Audio is cached by `sha1(voice + text)`, so a repeated line costs nothing.

## Running it

```bash
launchctl list | grep cockpit                 # is it up
curl -s localhost:7777/api/health             # is it answering
python3 .claude/lib/serve.py --print-token    # the token
tail -5 state/control-log.jsonl               # what was done
scheduler/install.sh --unload                 # stop everything, reversible
```

## Known limits

- **Agents started from `~` cannot be attributed to a project.** The `cwd` join
  only works for sessions started inside a project directory. Two of the six
  running right now show `(unassigned)` for that reason. Showing it honestly
  beats guessing from which files they touched.
- The page re-renders fully on each poll rather than diffing. At this size that
  is under a millisecond, and a hand-written differ is a permanent source of
  subtle staleness. Scroll position and filter selection are preserved.
- When the server is unreachable the bar goes red and says it is showing the
  last successful poll. It never presents stale data as current.
