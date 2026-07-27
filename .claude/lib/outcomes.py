"""Records what happened to the things the system surfaced.

PHASES.md defines five Sunday metrics. Three were computable from existing state.
Two were not, because nothing anywhere recorded an outcome:

  1. Of NEEDS ME items, what % did Joel act on?   (below 50% = over-surfacing)
  2. Of NOISE/FYI items, how many did he later dig out of the archive?

Both are the feedback loop. Without them the "raise the bar" correction in
PHASES.md can never fire, and the system cannot get better at what it shows —
it can only keep showing things.

## What "acted on" can honestly mean

Nobody is going to tick a box. So the observable proxy is disappearance: an item
that stopped being surfaced is one whose underlying condition changed — a blocked
project became unblocked, an overdue issue got closed, an ACT thread left the
inbox. That is evidence of resolution, not proof of action, and the vocabulary
here says `cleared` rather than `acted on` for exactly that reason.

Joel can always overrule the inference with mark(); an explicit outcome wins over
an observed one, the same way a correction in email-rules.md outranks a heuristic.

## Shape

state/outcomes.jsonl, one JSON object per line, append-only:

  {"ts", "kind": "surfaced"|"cleared"|"marked"|"archived"|"recovered",
   "key", "label", "text", "outcome"}

Append-only because an outcome log that can be rewritten measures nothing.
"""

import datetime
import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG = os.path.join(ROOT, "state", "outcomes.jsonl")

# An item still being surfaced after this long has been seen and passed over.
IGNORED_AFTER_DAYS = 7

VALID_MARKS = ("acted", "ignored", "not-mine")


def item_key(item):
    """Stable id for a NEEDS ME item across builds.

    Keyed on label + text because neither an index nor a timestamp survives the
    list being reordered, and reordering is normal — severity ranking changes as
    the world does.
    """
    # Normalize each component, not the joined string: the text is built with
    # f-strings upstream, and a stray space would otherwise mint a new key and
    # double-count one item as two.
    label = " ".join((item.get("label") or "").split()).lower()
    text = " ".join((item.get("text") or "").split()).lower()
    return hashlib.sha1(f"{label}|{text}".encode("utf-8")).hexdigest()[:16]


def _now(now=None):
    return (now or datetime.datetime.now().astimezone()).isoformat()


def append(records, path=None):
    path = path or LOG
    if not records:
        return 0
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(records)


def read(path=None):
    """Every record. A malformed line is skipped, never guessed at."""
    path = path or LOG
    if not os.path.exists(path):
        return []
    out = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return out


def snapshot(items, path=None, now=None):
    """Record this build's NEEDS ME list, and close out anything that vanished.

    Called on every dashboard build. Emits a `surfaced` record the first time an
    item appears and a `cleared` record the first time a previously-open item is
    absent, so the log stays proportional to change rather than to build count.
    """
    ts = _now(now)
    history = read(path)

    open_keys = {}
    for r in history:
        if r.get("kind") == "surfaced":
            open_keys[r["key"]] = r
        elif r.get("kind") in ("cleared", "marked"):
            open_keys.pop(r.get("key"), None)

    current = {item_key(i): i for i in items}
    new = []

    for k, i in current.items():
        if k not in open_keys:
            new.append({"ts": ts, "kind": "surfaced", "key": k,
                        "label": i.get("label", ""), "text": i.get("text", ""),
                        "severity": i.get("severity", "normal"),
                        "source": i.get("source", "")})

    for k, r in open_keys.items():
        if k not in current:
            new.append({"ts": ts, "kind": "cleared", "key": k,
                        "label": r.get("label", ""), "text": r.get("text", ""),
                        "outcome": "resolved-unobserved"})

    append(new, path)
    return {"surfaced": sum(1 for r in new if r["kind"] == "surfaced"),
            "cleared": sum(1 for r in new if r["kind"] == "cleared"),
            "open": len(current)}


def mark(key, outcome, note="", path=None, now=None):
    """Joel's explicit verdict on an item. Outranks the observed one."""
    if outcome not in VALID_MARKS:
        raise ValueError(f"outcome must be one of {VALID_MARKS}, got {outcome!r}")
    append([{"ts": _now(now), "kind": "marked", "key": key,
             "outcome": outcome, "note": note}], path)
    return key


def record_archived(thread_ids, bucket, path=None, now=None):
    """Threads triage filed away. The denominator for metric 2."""
    ts = _now(now)
    return append([{"ts": ts, "kind": "archived", "key": t, "label": bucket}
                   for t in thread_ids], path)


def record_recovered(thread_ids, path=None, now=None):
    """Threads Joel pulled back out of the archive. Each one is a misfile.

    Above zero means the classifier is wrong about something, and each is a
    correction owed to memory/email-rules.md.
    """
    ts = _now(now)
    return append([{"ts": ts, "kind": "recovered", "key": t} for t in thread_ids],
                  path)


def _within(records, days, now=None):
    now = now or datetime.datetime.now().astimezone()
    cutoff = now - datetime.timedelta(days=days)
    out = []
    for r in records:
        try:
            ts = datetime.datetime.fromisoformat(r["ts"])
        except (KeyError, ValueError, TypeError):
            continue
        if ts >= cutoff:
            out.append(r)
    return out


def needs_me_metrics(days=7, path=None, now=None):
    """Metric 1. Returns counts plus a clear rate, or None when there's no data.

    `clear_rate` is None rather than 0 when nothing was surfaced — a rate of zero
    means "you ignored everything", and an empty week does not mean that.
    """
    now = now or datetime.datetime.now().astimezone()
    history = read(path)
    window = _within(history, days, now)

    surfaced = [r for r in window if r.get("kind") == "surfaced"]
    cleared = [r for r in window if r.get("kind") == "cleared"]
    marked = [r for r in window if r.get("kind") == "marked"]

    explicit_acted = sum(1 for r in marked if r.get("outcome") == "acted")
    explicit_ignored = sum(1 for r in marked if r.get("outcome") == "ignored")

    # Anything surfaced and still open past the threshold has been passed over.
    closed_keys = {r["key"] for r in history
                   if r.get("kind") in ("cleared", "marked")}
    stale_open = 0
    for r in surfaced:
        if r["key"] in closed_keys:
            continue
        try:
            age = (now - datetime.datetime.fromisoformat(r["ts"])).days
        except (ValueError, TypeError):
            continue
        if age >= IGNORED_AFTER_DAYS:
            stale_open += 1

    resolved = len(cleared) + explicit_acted
    passed_over = stale_open + explicit_ignored
    denom = resolved + passed_over

    return {
        "window_days": days,
        "surfaced": len(surfaced),
        "cleared": len(cleared),
        "explicit_acted": explicit_acted,
        "explicit_ignored": explicit_ignored,
        "still_open_past_threshold": stale_open,
        "clear_rate": (resolved / denom) if denom else None,
        "over_surfacing": (denom > 0 and (resolved / denom) < 0.5),
        "note": ("clear_rate is resolution, not proof of action — an item stops "
                 "being surfaced when its condition changes"),
    }


def archive_recovery_metrics(days=7, path=None, now=None):
    """Metric 2. Anything above zero is a classifier miss owed a correction."""
    now = now or datetime.datetime.now().astimezone()
    window = _within(read(path), days, now)
    archived = [r for r in window if r.get("kind") == "archived"]
    recovered = [r for r in window if r.get("kind") == "recovered"]
    archived_keys = {r["key"] for r in archived}
    return {
        "window_days": days,
        "archived": len(archived),
        "recovered": len(recovered),
        "recovered_from_this_window": sum(
            1 for r in recovered if r["key"] in archived_keys),
        "recovered_ids": [r["key"] for r in recovered],
        "clean": len(recovered) == 0,
    }


def open_items(path=None):
    """Surfaced and not yet closed, oldest first — the mark() worklist."""
    history = read(path)
    opened, closed = {}, set()
    for r in history:
        if r.get("kind") == "surfaced":
            opened[r["key"]] = r
        elif r.get("kind") in ("cleared", "marked"):
            closed.add(r.get("key"))
    return sorted((r for k, r in opened.items() if k not in closed),
                  key=lambda r: r.get("ts", ""))
