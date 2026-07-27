"""Reads everything the dashboard renders, and knows the difference between
"zero" and "couldn't look".

Local state (projects, heartbeat, automation log, needs-me) is read directly.
Connector data (Gmail, Linear, Granola) can't be read from Python — MCP tools live
in Claude's session — so `/refresh` writes it to dashboard/feed.json first and this
module loads that, along with how old it is.
"""

import datetime
import json
import os
import re
import subprocess
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FEED = os.path.join(ROOT, "dashboard", "feed.json")
HEARTBEAT = os.path.join(ROOT, "state", "heartbeat.json")
AUTOMATION_LOG = os.path.join(ROOT, "state", "automation-log.jsonl")
NEEDS_ME = os.path.join(ROOT, "state", "needs-me.md")
PROJECTS_MD = os.path.join(ROOT, "memory", "projects.md")
# PHASES.md lists ~/TASKS.md as a Phase 1 data source. It lives outside the
# repo because it is Joel's file, not the system's.
TASKS_MD = os.path.expanduser("~/TASKS.md")

# A connector section older than this is shown as stale rather than current.
FEED_MAX_AGE_MIN = 90


def _missing(reason):
    return {"available": False, "reason": reason, "items": []}


def _unreadable(reason):
    """Consistent shape for every failure. A caller must never have to guess whether
    a key is absent because the feed was fine or because it wasn't read."""
    return {"present": False, "reason": reason, "age_min": None,
            "stale": False, "unknown_age": True, "data": {}}


def load_feed(path=None, now=None):
    """Load connector data written by /refresh. Never invents freshness.

    `path` resolves at call time rather than binding FEED as a default, so the
    module's paths are redirectable — for tests, and for anything that needs to
    point at a different repo.
    """
    path = path or FEED
    now = now or datetime.datetime.now().astimezone()
    if not os.path.exists(path):
        return _unreadable("dashboard/feed.json does not exist — run /refresh")
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return _unreadable(f"feed.json unreadable: {e}")

    age = None
    ts = data.get("generated_at")
    if ts:
        try:
            age = (now - datetime.datetime.fromisoformat(ts)).total_seconds() / 60
        except (ValueError, TypeError):
            age = None
    return {
        "present": True,
        "reason": None,
        "age_min": age,
        "stale": age is not None and age > FEED_MAX_AGE_MIN,
        "unknown_age": age is None,
        "data": data,
    }


def calendar_events(days=7, timeout=60):
    """Next `days` of calendar events via AppleScript.

    Returns {'available': bool, 'items': [...], 'reason': str}. A timeout or a
    denied permission is reported as unavailable — never as an empty calendar.
    """
    script = f'''
    set out to ""
    set d1 to (current date)
    set time of d1 to 0
    set d2 to d1 + ({days} * days)
    tell application "Calendar"
      repeat with c in calendars
        set evs to (every event of c whose start date >= d1 and start date < d2)
        repeat with e in evs
          set out to out & (name of c) & "\t" & (summary of e) & "\t" & ((start date of e) as string) & linefeed
        end repeat
      end repeat
    end tell
    return out
    '''
    def run():
        return subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout,
        )

    try:
        r = run()
        # -600 means Calendar.app simply isn't running. Start it hidden and retry
        # once — an unlaunched app must never be reported as an empty week.
        if r.returncode != 0 and "-600" in r.stderr:
            subprocess.run(["open", "-gj", "-a", "Calendar"],
                           capture_output=True, timeout=30)
            time.sleep(5)
            r = run()
    except subprocess.TimeoutExpired:
        return _missing(f"Calendar query timed out after {timeout}s")
    except (OSError, FileNotFoundError) as e:
        return _missing(f"osascript unavailable: {e}")
    if r.returncode != 0:
        return _missing(f"Calendar refused: {r.stderr.strip()[:160]}")

    items = []
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            items.append({"calendar": parts[0], "title": parts[1], "start": parts[2]})
    return {"available": True, "reason": None, "items": items}


def find_conflicts(events):
    """Detect overlapping calendar events. Flags only — never resolves.

    Compares by parsed start time where possible; events that don't parse are
    skipped rather than guessed at.
    """
    parsed = []
    for e in events:
        dt = _parse_applescript_date(e.get("start", ""))
        if dt:
            parsed.append((dt, e))
    parsed.sort(key=lambda x: x[0])
    conflicts = []
    for i in range(len(parsed) - 1):
        a_dt, a = parsed[i]
        b_dt, b = parsed[i + 1]
        # No end times available from the AppleScript above, so treat same-start
        # events as the conflict signal. Under-reports rather than crying wolf.
        if a_dt == b_dt:
            conflicts.append({"a": a.get("title"), "b": b.get("title"),
                              "when": a.get("start")})
    return conflicts


def _parse_applescript_date(s):
    for fmt in ("%A, %B %d, %Y at %I:%M:%S %p", "%A %d %B %Y at %H:%M:%S"):
        try:
            return datetime.datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


def heartbeat(path=None, now=None):
    """Scheduled task health. A task that never ran is a miss, not a blank."""
    path = path or HEARTBEAT
    now = now or datetime.datetime.now().astimezone()
    if not os.path.exists(path):
        return {"available": False, "reason": "heartbeat.json missing", "tasks": []}
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return {"available": False, "reason": f"heartbeat.json unreadable: {e}",
                "tasks": []}

    tasks = []
    for name, meta in (data.get("tasks") or {}).items():
        last = meta.get("last_run")
        max_age = meta.get("max_age_hours", 24)
        age_h, missed = None, True
        if last:
            try:
                age_h = (now - datetime.datetime.fromisoformat(last)).total_seconds() / 3600
                missed = age_h > max_age
            except (ValueError, TypeError):
                age_h, missed = None, True
        tasks.append({
            "name": name,
            "last_run": last,
            "never_run": not last,
            "age_hours": age_h,
            "max_age_hours": max_age,
            "missed": missed,
        })
    return {"available": True, "reason": None, "tasks": sorted(tasks, key=lambda t: t["name"])}


def automation_summary(path=None, hours=24, now=None):
    """What automation actually did, from the hook's ground-truth log."""
    path = path or AUTOMATION_LOG
    now = now or datetime.datetime.now().astimezone()
    if not os.path.exists(path):
        return {"available": False, "reason": "automation-log.jsonl missing",
                "total": 0, "by_tool": {}, "recent": []}

    cutoff = now - datetime.timedelta(hours=hours)
    by_tool, recent, total, unparsed = {}, [], 0, 0
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    ts = datetime.datetime.fromisoformat(rec["ts"])
                except (json.JSONDecodeError, KeyError, ValueError):
                    unparsed += 1
                    continue
                if ts < cutoff:
                    continue
                total += 1
                tool = rec.get("tool", "unknown")
                by_tool[tool] = by_tool.get(tool, 0) + 1
                recent.append({"ts": rec["ts"], "tool": tool,
                               "target": (rec.get("target") or "")[:120]})
    except OSError as e:
        return {"available": False, "reason": str(e), "total": 0,
                "by_tool": {}, "recent": []}

    recent.sort(key=lambda r: r["ts"], reverse=True)
    return {"available": True, "reason": None, "total": total, "by_tool": by_tool,
            "recent": recent[:25], "unparsed": unparsed, "window_hours": hours}


def tasks_file(path=None):
    """Read ~/TASKS.md, the data source PHASES.md lists and nothing ever read.

    It was neither parsed nor reported as unavailable, which is the one place the
    codebase broke its own rule that "nothing to do" and "I couldn't look" are
    different answers. If the file doesn't exist, that is now said out loud.

    Unchecked `- [ ]` items are open; `- [x]` are done and not returned.
    """
    path = path or TASKS_MD
    if not os.path.exists(path):
        return {"available": False, "reason": f"{path} does not exist", "items": []}
    items = []
    try:
        with open(path) as f:
            for line in f:
                s = line.strip()
                m = re.match(r"^[-*]\s*\[( |x|X)\]\s*(.+)$", s)
                if m:
                    if m.group(1) == " ":
                        items.append({"text": m.group(2).strip(), "done": False})
                    continue
                if s.startswith("- ") and not s.startswith("- ["):
                    items.append({"text": s[2:].strip(), "done": False})
    except OSError as e:
        return {"available": False, "reason": f"{path} unreadable: {e}", "items": []}
    return {"available": True, "reason": None, "items": items}


def needs_me_file(path=None):
    """Low-confidence actions and anything explicitly flagged for Joel."""
    path = path or NEEDS_ME
    if not os.path.exists(path):
        return {"available": False, "reason": "state/needs-me.md missing", "items": []}
    items = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("- ") and not line.startswith("- ["):
                    items.append({"text": line[2:].strip(), "source": "needs-me.md"})
                elif line.startswith("- [ ] "):
                    items.append({"text": line[6:].strip(), "source": "needs-me.md"})
    except OSError as e:
        return {"available": False, "reason": str(e), "items": []}
    return {"available": True, "reason": None, "items": items}
