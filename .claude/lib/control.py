"""Lifecycle control over running Claude sessions. Start, stop, resume, queue.

Verified against Claude Code 2.1.220. Three of the four verbs are real:

    stop      SIGTERM to the pid. The transcript persists and the session stays
              resumable — destroying work is not a thing a dashboard button
              should do, so it is never SIGKILL.
    dispatch  `claude --bg -p "<task>"` with cwd set to a project's repo.
    resume    `claude --resume <id> -p "<msg>"` — idle sessions only.

The fourth, injecting a message into a BUSY session mid-turn, has no supported
interface. The session registry advertises `peerProtocol: 1`, so internal peer
messaging exists, but it is private and undocumented — building on it means the
cockpit breaks silently at the next Claude Code update, and a control plane that
stops working without saying so is worse than one that never claimed the
feature.

So `send` to a busy agent QUEUES. state/agent-inbox.jsonl holds it and it is
delivered on the next idle transition, with the pending count visible in the UI
so a queued message never looks like a delivered one. Interrupting an agent
between tool calls is how half-finished work gets corrupted; a few seconds of
latency buys correctness.

Every action is appended to state/control-log.jsonl before it is attempted, so
a crash mid-action still leaves a record. Same append-only ground-truth pattern
as automation-log.jsonl.
"""

import datetime
import json
import os
import signal
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agents as agentsmod  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONTROL_LOG = os.path.join(ROOT, "state", "control-log.jsonl")
INBOX = os.path.join(ROOT, "state", "agent-inbox.jsonl")

VERBS = ("stop", "dispatch", "resume", "send")
SPAWN_TIMEOUT_S = 10


def _now():
    return datetime.datetime.now().astimezone().isoformat()


def _log(rec, path=None):
    path = path or CONTROL_LOG
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def read_log(path=None, limit=50):
    path = path or CONTROL_LOG
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out[-limit:]


# ── inbox for busy agents ────────────────────────────────────────────────

def queue_message(session_id, message, path=None):
    return _log({"ts": _now(), "session_id": session_id, "message": message,
                 "delivered": False}, path or INBOX)


def pending(session_id=None, path=None):
    """Queued messages not yet delivered."""
    path = path or INBOX
    if not os.path.exists(path):
        return []
    queued, delivered = [], set()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("delivered_marker"):
                delivered.add(r["key"])
            else:
                queued.append(r)
    out = [q for q in queued
           if f"{q['session_id']}|{q['ts']}" not in delivered
           and (session_id is None or q["session_id"] == session_id)]
    return out


def mark_delivered(msg, path=None):
    return _log({"ts": _now(), "delivered_marker": True,
                 "key": f"{msg['session_id']}|{msg['ts']}"}, path or INBOX)


def pending_counts(path=None):
    counts = {}
    for m in pending(path=path):
        counts[m["session_id"]] = counts.get(m["session_id"], 0) + 1
    return counts


# ── the verbs ────────────────────────────────────────────────────────────

def _find(session_id, sessions_dir=None):
    for a in agentsmod.roster(sessions_dir)["items"]:
        if a["session_id"] == session_id:
            return a
    return None


def stop(session_id, sessions_dir=None, log_path=None, _kill=None):
    """SIGTERM. The session flushes its transcript and stays resumable."""
    a = _find(session_id, sessions_dir)
    rec = {"ts": _now(), "verb": "stop", "target": session_id,
           "name": a["name"] if a else None}
    if not a:
        rec.update(ok=False, reason="no live session with that id")
        return _log(rec, log_path)
    try:
        (_kill or os.kill)(int(a["pid"]), signal.SIGTERM)
    except (OSError, ValueError) as e:
        rec.update(ok=False, reason=f"kill failed: {e}")
        return _log(rec, log_path)
    rec.update(ok=True, pid=a["pid"], signal="SIGTERM",
               note="transcript preserved; resumable with --resume")
    return _log(rec, log_path)


def dispatch(cwd, message, log_path=None, _run=None):
    """Start a new background agent in a project directory."""
    rec = {"ts": _now(), "verb": "dispatch", "target": cwd,
           "message": message[:200]}
    cwd = os.path.realpath(os.path.expanduser(cwd))
    if not os.path.isdir(cwd):
        rec.update(ok=False, reason=f"not a directory: {cwd}")
        return _log(rec, log_path)
    runner = _run or subprocess.run
    try:
        r = runner(["claude", "--bg", "-p", message], cwd=cwd,
                   capture_output=True, text=True, timeout=SPAWN_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError) as e:
        rec.update(ok=False, reason=f"spawn failed: {e}")
        return _log(rec, log_path)
    rec.update(ok=r.returncode == 0,
               reason=None if r.returncode == 0 else (r.stderr or "")[:200],
               stdout=(r.stdout or "")[:200])
    return _log(rec, log_path)


def resume(session_id, message, sessions_dir=None, log_path=None, _run=None):
    """Send a message to an IDLE session by resuming it."""
    a = _find(session_id, sessions_dir)
    rec = {"ts": _now(), "verb": "resume", "target": session_id,
           "message": message[:200], "name": a["name"] if a else None}
    if not a:
        rec.update(ok=False, reason="no live session with that id")
        return _log(rec, log_path)
    if a["status"] == "busy":
        rec.update(ok=False, reason="session is busy — use send(), which queues")
        return _log(rec, log_path)
    runner = _run or subprocess.run
    try:
        r = runner(["claude", "--resume", session_id, "-p", message],
                   cwd=a["cwd"] or os.path.expanduser("~"),
                   capture_output=True, text=True, timeout=SPAWN_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError) as e:
        rec.update(ok=False, reason=f"resume failed: {e}")
        return _log(rec, log_path)
    rec.update(ok=r.returncode == 0,
               reason=None if r.returncode == 0 else (r.stderr or "")[:200])
    return _log(rec, log_path)


def send(session_id, message, sessions_dir=None, log_path=None,
         inbox_path=None, _run=None):
    """Talk to an agent. Delivers if idle, queues if busy.

    Never fails for being busy. It queues and says so — which is the honest
    answer, since there is no supported way to interrupt a session mid-turn.
    """
    a = _find(session_id, sessions_dir)
    if not a:
        return _log({"ts": _now(), "verb": "send", "target": session_id,
                     "ok": False, "reason": "no live session with that id"},
                    log_path)
    if a["status"] == "busy":
        queue_message(session_id, message, inbox_path)
        return _log({"ts": _now(), "verb": "send", "target": session_id,
                     "name": a["name"], "ok": True, "queued": True,
                     "message": message[:200],
                     "note": "agent is busy — queued, delivers when it goes idle"},
                    log_path)
    out = resume(session_id, message, sessions_dir, log_path, _run)
    out["queued"] = False
    return out


def flush_inbox(sessions_dir=None, log_path=None, inbox_path=None, _run=None):
    """Deliver queued messages to agents that have gone idle.

    Called on each poll by the server. Cheap when the inbox is empty.
    """
    msgs = pending(path=inbox_path)
    if not msgs:
        return []
    roster = {a["session_id"]: a for a in agentsmod.roster(sessions_dir)["items"]}
    delivered = []
    for m in msgs:
        a = roster.get(m["session_id"])
        if not a:
            continue                      # agent is gone; leave it queued
        if a["status"] == "busy":
            continue
        r = resume(m["session_id"], m["message"], sessions_dir, log_path, _run)
        if r.get("ok"):
            mark_delivered(m, inbox_path)
            delivered.append(m)
    return delivered


def apply(verb, target, message="", **kw):
    """Single entry point for the server."""
    if verb not in VERBS:
        return {"ok": False, "reason": f"unknown verb {verb!r}; expected {VERBS}"}
    if verb == "stop":
        return stop(target, **{k: v for k, v in kw.items() if k in
                               ("sessions_dir", "log_path", "_kill")})
    if verb == "dispatch":
        return dispatch(target, message, **{k: v for k, v in kw.items()
                                            if k in ("log_path", "_run")})
    if verb == "resume":
        return resume(target, message, **{k: v for k, v in kw.items() if k in
                                          ("sessions_dir", "log_path", "_run")})
    return send(target, message, **{k: v for k, v in kw.items() if k in
                                    ("sessions_dir", "log_path", "inbox_path",
                                     "_run")})
