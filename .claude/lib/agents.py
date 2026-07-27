"""Who is working right now, and on which of Joel's projects.

Claude Code already writes everything this needs; nothing here adds
instrumentation. Three sources, all local files:

    ~/.claude/sessions/<pid>.json          the roster — pid, cwd, status, name
    ~/.claude/tasks/<sessionId>/*.json     that agent's task list, with status
    ~/.claude/projects/<slug>/<id>.jsonl   its transcript; the tail is what it
                                           is doing right now

The join that matters is cwd -> project, via the `- repos:` field in
memory/projects.md. An agent running in ~/alivio-platform belongs on the Alivio
Search Partners card, not in a disconnected list of PIDs. Without that join this
is a process viewer; with it, it is a cockpit.

Read directly rather than shelling out to `claude agents --json`: this is polled
every couple of seconds and a subprocess per poll is pure waste. The CLI stays
the documented fallback if the directory is ever unreadable.

Same honesty rule as the rest of this repo, extended to agents: "nobody is
working" and "I could not look" are different answers, and an unreadable sessions
directory must never render as an empty roster.
"""

import datetime
import json
import os
import re

HOME = os.path.expanduser("~")
SESSIONS = os.path.join(HOME, ".claude", "sessions")
TASKS = os.path.join(HOME, ".claude", "tasks")
TRANSCRIPTS = os.path.join(HOME, ".claude", "projects")

# How much of a transcript's tail to read. They reach 10MB; the last action is
# always within a few KB of the end, and reading the whole file on every poll
# would make the cockpit cost more than the work it watches.
TAIL_BYTES = 64 * 1024

# A session whose file has not been touched in this long is stale — the process
# died without cleaning up. Pid liveness is the real check; this is the backstop
# for a pid that got recycled onto an unrelated process.
STALE_AFTER_S = 24 * 3600


def _read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def pid_alive(pid):
    """Signal 0 checks existence without touching the process."""
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def _slug(cwd):
    """Claude Code's transcript directory name for a working directory.

    /Users/joel/alivio-platform -> -Users-joel-alivio-platform
    """
    return re.sub(r"[^A-Za-z0-9]", "-", cwd or "")


def roster(sessions_dir=None, now=None):
    """Live sessions. Returns the standard available/reason/items shape.

    A session file whose process is gone is dropped rather than shown as idle —
    a dead agent listed as idle is worse than not listing it, because it implies
    work is parked when it is actually abandoned.
    """
    sessions_dir = sessions_dir or SESSIONS
    now = now or datetime.datetime.now().astimezone()

    if not os.path.isdir(sessions_dir):
        return {"available": False,
                "reason": f"{sessions_dir} does not exist", "items": []}
    try:
        names = os.listdir(sessions_dir)
    except OSError as e:
        return {"available": False,
                "reason": f"{sessions_dir} unreadable: {e}", "items": []}

    items, unreadable = [], 0
    for name in names:
        if not name.endswith(".json"):
            continue
        d = _read_json(os.path.join(sessions_dir, name))
        if not isinstance(d, dict) or "sessionId" not in d:
            unreadable += 1
            continue
        pid = d.get("pid")
        if not pid_alive(pid):
            continue

        started = d.get("startedAt")
        age_s = None
        if isinstance(started, (int, float)):
            age_s = max(0, now.timestamp() - started / 1000.0)

        updated = d.get("updatedAt")
        if isinstance(updated, (int, float)):
            if now.timestamp() - updated / 1000.0 > STALE_AFTER_S:
                continue

        items.append({
            "session_id": d["sessionId"],
            "pid": pid,
            "name": d.get("name") or d["sessionId"][:8],
            "cwd": d.get("cwd") or "",
            "kind": d.get("kind") or "unknown",
            # Absent status means idle: the field is only written when a session
            # starts working. Guessing "unknown" here would paint every calm
            # agent as a question mark.
            "status": d.get("status") or "idle",
            "started_at": started,
            "age_s": age_s,
            "age_human": _human_age(age_s),
        })

    items.sort(key=lambda a: (a["status"] != "busy", -(a["started_at"] or 0)))
    return {"available": True, "reason": None, "items": items,
            "unreadable": unreadable}


def _human_age(seconds):
    if seconds is None:
        return ""
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        return f"{s // 3600}h"
    return f"{s // 86400}d"


def tasks_for(session_id, tasks_dir=None):
    """That agent's work, split into done / doing / next.

    `next` is the first pending task whose blockers are all complete — the thing
    it can actually pick up, not merely the next one in the file. A blocked task
    presented as "next" is how a plan looks fine while nothing can move.
    """
    tasks_dir = tasks_dir or TASKS
    d = os.path.join(tasks_dir, session_id)
    if not os.path.isdir(d):
        return {"available": False, "reason": "no task directory",
                "done": [], "doing": [], "next": None, "pending": 0}

    try:
        names = sorted(os.listdir(d))
    except OSError as e:
        return {"available": False, "reason": str(e),
                "done": [], "doing": [], "next": None, "pending": 0}

    by_id, order = {}, []
    for n in names:
        if not n.endswith(".json"):
            continue
        t = _read_json(os.path.join(d, n))
        if isinstance(t, dict) and "id" in t:
            by_id[str(t["id"])] = t
            order.append(str(t["id"]))

    def done(tid):
        t = by_id.get(str(tid))
        return bool(t) and t.get("status") == "completed"

    doing = [by_id[i]["subject"] for i in order
             if by_id[i].get("status") == "in_progress"]
    completed = [by_id[i]["subject"] for i in order
                 if by_id[i].get("status") == "completed"]

    nxt = None
    pending = 0
    for i in order:
        t = by_id[i]
        if t.get("status") != "pending":
            continue
        pending += 1
        if nxt is None and all(done(b) for b in (t.get("blockedBy") or [])):
            nxt = t.get("subject")

    return {"available": True, "reason": None, "done": completed,
            "doing": doing, "next": nxt, "pending": pending,
            "total": len(order)}


def last_action(session_id, cwd, transcripts_dir=None):
    """The most recent tool call, from the tail of the transcript.

    Seeks rather than reads: transcripts reach 10MB and this is polled.
    """
    transcripts_dir = transcripts_dir or TRANSCRIPTS
    path = os.path.join(transcripts_dir, _slug(cwd), f"{session_id}.jsonl")
    if not os.path.exists(path):
        return {"available": False, "reason": "no transcript", "tool": None}

    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(max(0, size - TAIL_BYTES))
            chunk = f.read()
    except OSError as e:
        return {"available": False, "reason": str(e), "tool": None}

    lines = chunk.decode("utf-8", "ignore").splitlines()
    if size > TAIL_BYTES and lines:
        # The first line is almost certainly cut in half by the seek.
        lines = lines[1:]

    found = None
    for line in lines:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        content = (rec.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                found = {"tool": block.get("name", "?"),
                         "summary": _summarize(block.get("name"),
                                               block.get("input")),
                         "ts": rec.get("timestamp", "")}
    if not found:
        return {"available": True, "reason": None, "tool": None}
    return {"available": True, "reason": None, **found}


def _summarize(tool, inp):
    """One short line describing a tool call, for a dashboard row."""
    if not isinstance(inp, dict):
        return ""
    for key in ("command", "file_path", "pattern", "query", "path", "url",
                "prompt", "subject"):
        v = inp.get(key)
        if isinstance(v, str) and v.strip():
            v = " ".join(v.split())
            return v[:80]
    return ""


def join_projects(agents, projects):
    """Attach each agent to the project whose repo contains its cwd.

    Longest match wins, so an agent in ~/alivio-platform lands on Alivio Search
    Partners rather than on any project that happens to list ~ as a repo.
    """
    claims = []
    for p in projects:
        for repo in p.repos:
            expanded = os.path.realpath(os.path.expanduser(repo.strip()))
            if expanded:
                claims.append((len(expanded), expanded, p.name))
    claims.sort(reverse=True)

    for a in agents:
        a["project"] = None
        cwd = a.get("cwd") or ""
        if not cwd:
            continue
        real = os.path.realpath(os.path.expanduser(cwd))
        for _, path, name in claims:
            if real == path or real.startswith(path + os.sep):
                a["project"] = name
                break
    return agents


def snapshot(projects=None, sessions_dir=None, tasks_dir=None,
             transcripts_dir=None, now=None):
    """Everything the AGENTS panel renders, in one call."""
    r = roster(sessions_dir, now)
    if not r["available"]:
        return {"available": False, "reason": r["reason"], "items": [],
                "busy": 0, "by_project": {}}

    for a in r["items"]:
        a["tasks"] = tasks_for(a["session_id"], tasks_dir)
        a["last_action"] = last_action(a["session_id"], a["cwd"],
                                       transcripts_dir)
    join_projects(r["items"], projects or [])

    by_project = {}
    for a in r["items"]:
        by_project.setdefault(a["project"] or "(unassigned)", []).append(
            a["session_id"])

    return {"available": True, "reason": None, "items": r["items"],
            "busy": sum(1 for a in r["items"] if a["status"] == "busy"),
            "by_project": by_project, "unreadable": r.get("unreadable", 0)}
