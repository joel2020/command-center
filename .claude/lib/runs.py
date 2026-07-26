"""Records the outcome of every scheduled run, and decides when to escalate.

`heartbeat.json` answers "did this task run recently?" This answers "is it healthy?"
Those are different questions: a task can run every hour and fail every time, and the
heartbeat would look fine.

PHASES.md escalates a scheduled task that "failed twice consecutively." Consecutive
failures can't be derived from a last-run timestamp, so they're tracked here.
"""

import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUN_LOG = os.path.join(ROOT, "state", "run-log.jsonl")

TASKS = ["morning-brief", "email-triage", "evening-digest", "weekly-review"]


def record(task, exit_code, duration_s=None, note="", path=RUN_LOG, now=None):
    now = now or datetime.datetime.now().astimezone()
    rec = {
        "ts": now.isoformat(),
        "task": task,
        "exit_code": int(exit_code),
        "ok": int(exit_code) == 0,
        "duration_s": round(duration_s, 1) if duration_s is not None else None,
        "note": note,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def read(path=RUN_LOG):
    out = []
    if not os.path.exists(path):
        return out
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def consecutive_failures(task, path=RUN_LOG):
    """How many times in a row this task has failed, counting back from the latest."""
    runs = [r for r in read(path) if r.get("task") == task]
    n = 0
    for r in reversed(runs):
        if r.get("ok"):
            break
        n += 1
    return n


def health(path=RUN_LOG, tasks=None):
    out = []
    for t in (tasks or TASKS):
        runs = [r for r in read(path) if r.get("task") == t]
        fails = consecutive_failures(t, path)
        out.append({
            "task": t,
            "runs": len(runs),
            "last": runs[-1]["ts"] if runs else None,
            "last_ok": runs[-1]["ok"] if runs else None,
            "consecutive_failures": fails,
            "needs_escalation": fails >= 2,
        })
    return out


def prune(path=RUN_LOG, keep_days=90, now=None):
    """Bounded log. CLAUDE.md lists pruning as automatic; this is where it happens."""
    now = now or datetime.datetime.now().astimezone()
    cutoff = now - datetime.timedelta(days=keep_days)
    runs = read(path)
    kept = []
    for r in runs:
        try:
            if datetime.datetime.fromisoformat(r["ts"]) >= cutoff:
                kept.append(r)
        except (KeyError, ValueError):
            continue
    if len(kept) == len(runs):
        return 0
    with open(path, "w") as f:
        for r in kept:
            f.write(json.dumps(r) + "\n")
    return len(runs) - len(kept)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("record", help="record a run outcome and escalate if needed")
    r.add_argument("task")
    r.add_argument("exit_code", type=int)
    r.add_argument("--duration", type=float, default=None)
    r.add_argument("--note", default="")
    r.add_argument("--no-notify", action="store_true")

    sub.add_parser("health")
    p = sub.add_parser("prune")
    p.add_argument("--keep-days", type=int, default=90)

    args = ap.parse_args()

    if args.cmd == "record":
        rec = record(args.task, args.exit_code, args.duration, args.note)
        fails = consecutive_failures(args.task)
        print(json.dumps({**rec, "consecutive_failures": fails}))

        # Escalate only on the second consecutive failure. Once is noise.
        if fails >= 2 and not args.no_notify:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import push
            fire, why = push.should_notify_task_failure(fails)
            if fire:
                push.notify("Command Center — task failing",
                            f"{args.task}: {why}")
                print(f"escalated: {why}")
        return

    if args.cmd == "health":
        for h in health():
            flag = "!!" if h["needs_escalation"] else "  "
            last = h["last"][:16] if h["last"] else "never"
            print(f"{flag} {h['task']:<16} runs={h['runs']:<4} last={last:<17} "
                  f"consecutive_failures={h['consecutive_failures']}")
        return

    if args.cmd == "prune":
        print(f"pruned {prune(keep_days=args.keep_days)} records")


if __name__ == "__main__":
    main()
