"""The approval queue — an anti-inbox.

The rules from CLAUDE.md live here as code rather than as judgment, because a cap
that depends on remembering to apply it is not a cap:

  * hard cap of 10 visible; overflow reported as a count
  * confidence below 40% goes to state/rejected-candidates.md, never the queue
  * unreviewed after 7 days is auto-declined, logged "expired unreviewed"
  * deduped against the last 30 days — the same proposal never appears twice

Nothing here executes a proposal. `approve()` marks intent; carrying it out is a
separate, deliberate act — and if the proposal is one of the six manual actions,
it is Joel's act, not Claude's.
"""

import datetime
import hashlib
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
QUEUE = os.path.join(ROOT, "state", "approval-queue.json")
REJECTED = os.path.join(ROOT, "state", "rejected-candidates.md")
TASK_RULES = os.path.join(ROOT, "memory", "task-rules.md")

VISIBLE_CAP = 10
MIN_CONFIDENCE = 0.40
EXPIRY_DAYS = 7
DEDUPE_DAYS = 30

PENDING, APPROVED, DECLINED, EXPIRED = "pending", "approved", "declined", "expired"

# The six permanent manual actions. An item touching one of these can be queued for
# Joel's decision, but is flagged so nothing downstream ever auto-executes it.
MANUAL_ACTION_PATTERNS = [
    (r"\b(send|email|reply|slack|comment|invite|message|dm|text)\b", "sending to a human"),
    (r"\b(delete|remove|rm\b|trash|purge|drop)\b", "deleting"),
    (r"\b(buy|purchase|pay|subscribe|upgrade|spend|invoice|charge)\b", "spending money"),
    (r"\b(credential|password|token|api key|permission|access|oauth|2fa)\b",
     "credentials or permissions"),
    (r"\b(accept|decline|reschedul|move the meeting|cancel the meeting)\b", "meetings"),
]


def fingerprint(kind, subject):
    """Stable identity for dedupe. Case- and whitespace-insensitive."""
    norm = re.sub(r"\s+", " ", f"{kind}|{subject}".strip().lower())
    return hashlib.sha256(norm.encode()).hexdigest()[:16]


def touches_manual_action(text):
    """Return a list of manual-action reasons this proposal appears to touch."""
    t = (text or "").lower()
    return [why for pat, why in MANUAL_ACTION_PATTERNS if re.search(pat, t)]


def load(path=QUEUE):
    try:
        with open(path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"items": []}
    data.setdefault("items", [])
    return data


def save(data, path=QUEUE):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _parse(ts):
    try:
        return datetime.datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def expire(data, now=None):
    """Auto-decline anything pending longer than EXPIRY_DAYS. Returns expired items."""
    now = now or datetime.datetime.now().astimezone()
    expired = []
    for it in data["items"]:
        if it.get("status") != PENDING:
            continue
        created = _parse(it.get("created_at"))
        if created is None:
            continue
        if (now - created).days >= EXPIRY_DAYS:
            it["status"] = EXPIRED
            it["resolved_at"] = now.isoformat()
            it["resolution"] = "expired unreviewed"
            expired.append(it)
    return expired


def _seen_recently(data, fp, now, days=DEDUPE_DAYS):
    for it in data["items"]:
        if it.get("fingerprint") != fp:
            continue
        ref = _parse(it.get("resolved_at") or it.get("created_at"))
        if ref is None or (now - ref).days < days:
            return it
    return None


def propose(data, kind, subject, confidence, detail="", source="", now=None,
            rejected_path=REJECTED):
    """Offer something for Joel's approval.

    Returns (outcome, item) where outcome is one of:
      queued | rejected_low_confidence | duplicate
    """
    now = now or datetime.datetime.now().astimezone()
    expire(data, now)

    fp = fingerprint(kind, subject)
    dup = _seen_recently(data, fp, now)
    if dup:
        return "duplicate", dup

    manual = touches_manual_action(f"{kind} {subject} {detail}")
    item = {
        "id": fp,
        "fingerprint": fp,
        "kind": kind,
        "subject": subject,
        "detail": detail,
        "source": source,
        "confidence": round(float(confidence), 3),
        "status": PENDING,
        "created_at": now.isoformat(),
        "manual_action": manual,
    }

    if confidence < MIN_CONFIDENCE:
        _log_rejected(item, rejected_path, now)
        return "rejected_low_confidence", item

    data["items"].append(item)
    return "queued", item


def _log_rejected(item, path, now):
    """Below the threshold: recorded, never queued. Queueing uncertainty is how
    this turns into a second inbox."""
    line = (f"- {now.date().isoformat()} | {int(item['confidence'] * 100)}% | "
            f"{item['kind']} | {item['subject']}"
            + (f" | {item['detail']}" if item["detail"] else ""))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    header_needed = not os.path.exists(path)
    with open(path, "a") as f:
        if header_needed:
            f.write("# Rejected Candidates\n\n")
        f.write(line + "\n")


def visible(data, now=None):
    """The capped view. Returns (items, overflow_count)."""
    now = now or datetime.datetime.now().astimezone()
    expire(data, now)
    pending = [i for i in data["items"] if i.get("status") == PENDING]
    pending.sort(key=lambda i: (-i.get("confidence", 0), i.get("created_at", "")))
    return pending[:VISIBLE_CAP], max(0, len(pending) - VISIBLE_CAP)


def resolve(data, item_id, status, note="", now=None):
    """Mark an item approved or declined. Does not execute anything."""
    if status not in (APPROVED, DECLINED):
        raise ValueError(f"resolve() takes {APPROVED} or {DECLINED}, got {status}")
    now = now or datetime.datetime.now().astimezone()
    for it in data["items"]:
        if it.get("id") == item_id:
            it["status"] = status
            it["resolved_at"] = now.isoformat()
            it["resolution"] = note
            return it
    return None


def age_days(item, now=None):
    now = now or datetime.datetime.now().astimezone()
    created = _parse(item.get("created_at"))
    return None if created is None else (now - created).days


def metrics(data, now=None, days=7):
    """Sunday numbers. High declines mean the wrong things are being proposed."""
    now = now or datetime.datetime.now().astimezone()
    cutoff = now - datetime.timedelta(days=days)
    out = {"approved": 0, "declined": 0, "expired": 0, "pending": 0, "window_days": days}
    for it in data["items"]:
        ref = _parse(it.get("resolved_at") or it.get("created_at"))
        if ref is None or ref < cutoff:
            continue
        out[it.get("status", PENDING)] = out.get(it.get("status", PENDING), 0) + 1
    decided = out["approved"] + out["declined"]
    out["approval_rate"] = round(out["approved"] / decided, 3) if decided else None
    return out


def promotion_candidates(data, threshold=5):
    """Patterns approved repeatedly with no edits.

    Returns kinds eligible to be *offered* for promotion to automatic. Never
    self-promote, and never offer a kind that touches a manual action — those have
    no promotion path at all.
    """
    counts, blocked = {}, set()
    for it in data["items"]:
        kind = it.get("kind")
        if it.get("manual_action"):
            blocked.add(kind)
        if it.get("status") == APPROVED and not it.get("resolution"):
            counts[kind] = counts.get(kind, 0) + 1
    return sorted(k for k, n in counts.items() if n >= threshold and k not in blocked)
