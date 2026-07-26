"""Stamp state/heartbeat.json when a scheduled task completes.

Usage:
    python3 .claude/lib/heartbeat.py morning-brief
    python3 .claude/lib/heartbeat.py --status

A run that doesn't stamp didn't happen, as far as SessionStart is concerned.
That's deliberate: a dashboard that renders as current while being hours stale is
worse than no dashboard.
"""

import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATH = os.path.join(ROOT, "state", "heartbeat.json")

DEFAULT_MAX_AGE = {
    "morning-brief": 26,
    "email-triage": 2,
    "evening-digest": 26,
    "weekly-review": 176,
}


def load(path=PATH):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"tasks": {}}


def stamp(task, path=PATH, now=None):
    """Record that `task` just completed. Returns the ISO timestamp written."""
    now = now or datetime.datetime.now().astimezone()
    data = load(path)
    tasks = data.setdefault("tasks", {})
    entry = tasks.setdefault(task, {"max_age_hours": DEFAULT_MAX_AGE.get(task, 24)})
    entry["last_run"] = now.isoformat()
    entry.setdefault("max_age_hours", DEFAULT_MAX_AGE.get(task, 24))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    return entry["last_run"]


def status(path=PATH, now=None):
    now = now or datetime.datetime.now().astimezone()
    out = []
    for name, meta in sorted((load(path).get("tasks") or {}).items()):
        last = meta.get("last_run")
        limit = meta.get("max_age_hours", 24)
        if not last:
            out.append((name, None, limit, True))
            continue
        try:
            age = (now - datetime.datetime.fromisoformat(last)).total_seconds() / 3600
        except (ValueError, TypeError):
            out.append((name, None, limit, True))
            continue
        out.append((name, age, limit, age > limit))
    return out


def main():
    args = [a for a in sys.argv[1:]]
    if not args or args[0] in ("--status", "-s"):
        for name, age, limit, missed in status():
            age_s = "never run" if age is None else f"{age:.1f}h ago"
            print(f"{'!!' if missed else '  '} {name:<16} {age_s:<14} limit {limit}h")
        return
    for task in args:
        print(f"stamped {task} at {stamp(task)}")


if __name__ == "__main__":
    main()
