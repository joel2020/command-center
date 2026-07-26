"""Push channels. Deliberately hard to trigger.

Two channels, very different bars:

  macOS notification — local, free, disappears. Fires on real but ordinary urgency.
  SMS via Twilio     — costs money, wakes Joel up. Genuine emergencies only, max 2
                       per week, and off unless explicitly enabled.

PHASES.md: "If unsure whether something is push-worthy, it isn't." Every predicate
here defaults to False and requires a positive reason to fire.

SMS also touches manual action #3 (spending money), so it stays behind an explicit
`sms_enabled` flag. Reaching the weekly cap is not a rate-limit annoyance — it means
the threshold is wrong, and this module says so.
"""

import datetime
import json
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG = os.path.join(ROOT, "state", "push-config.json")
LOG = os.path.join(ROOT, "state", "push-log.jsonl")

SMS_WEEKLY_CAP = 2
NOTIFY_DEADLINE_HOURS = 4
CONSECUTIVE_FAILURES_FOR_PUSH = 2


def load_config(path=CONFIG):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"sms_enabled": False}


def _log(record, path=LOG):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def _read_log(path=LOG):
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


# ── decision predicates ───────────────────────────────────────────────────────

def should_notify_deadline(hours_until, has_deadline=True):
    """ACT item with a deadline inside 4 hours."""
    if not has_deadline or hours_until is None:
        return False, "no deadline"
    if hours_until < 0:
        return True, f"deadline passed {abs(hours_until):.1f}h ago"
    if hours_until <= NOTIFY_DEADLINE_HOURS:
        return True, f"deadline in {hours_until:.1f}h"
    return False, f"deadline in {hours_until:.1f}h — outside the {NOTIFY_DEADLINE_HOURS}h window"


def should_notify_task_failure(consecutive_failures):
    """A scheduled task that failed twice in a row. Once is noise."""
    n = consecutive_failures or 0
    if n >= CONSECUTIVE_FAILURES_FOR_PUSH:
        return True, f"{n} consecutive failures"
    return False, f"{n} failure(s) — needs {CONSECUTIVE_FAILURES_FOR_PUSH}"


def should_notify_expiring(days_until_expiry, time_sensitive):
    """A queue item about to expire on something time-sensitive."""
    if not time_sensitive:
        return False, "not time-sensitive"
    if days_until_expiry is None:
        return False, "unknown expiry"
    if days_until_expiry <= 1:
        return True, f"expires in {days_until_expiry}d and is time-sensitive"
    return False, f"expires in {days_until_expiry}d — not yet"


def sms_justified(same_day_money_or_legal=False, client_escalating=False,
                  consequences_outlast_today=False):
    """The only three reasons. Absence of a reason is a no."""
    reasons = []
    if same_day_money_or_legal:
        reasons.append("money or legal with a same-day deadline")
    if client_escalating:
        reasons.append("client explicitly escalating")
    if consequences_outlast_today:
        reasons.append("missing it today has consequences outlasting today")
    return (bool(reasons), reasons)


def sms_budget(now=None, path=LOG):
    """How many SMS remain this week, and whether the cap itself is the signal."""
    now = now or datetime.datetime.now().astimezone()
    cutoff = now - datetime.timedelta(days=7)
    sent = 0
    for r in _read_log(path):
        if r.get("channel") != "sms" or not r.get("sent"):
            continue
        try:
            ts = datetime.datetime.fromisoformat(r["ts"])
        except (KeyError, ValueError):
            continue
        if ts >= cutoff:
            sent += 1
    remaining = max(0, SMS_WEEKLY_CAP - sent)
    return {
        "sent_this_week": sent,
        "remaining": remaining,
        "cap": SMS_WEEKLY_CAP,
        "cap_reached": remaining == 0,
        "note": ("Weekly SMS cap reached. Per PHASES.md that means the threshold is "
                 "wrong, not that the message should wait — review what triggered these."
                 if remaining == 0 else None),
    }


# ── channels ──────────────────────────────────────────────────────────────────

def notify(title, message, subtitle="", dry_run=False, log_path=LOG):
    """macOS notification. Local and free — no approval needed."""
    rec = {"ts": datetime.datetime.now().astimezone().isoformat(), "channel": "macos",
           "title": title, "message": message, "sent": False}
    if dry_run:
        rec["reason"] = "dry run"
        _log(rec, log_path)
        return rec

    def esc(s):
        return str(s).replace("\\", "\\\\").replace('"', '\\"')

    script = (f'display notification "{esc(message)}" with title "{esc(title)}"'
              + (f' subtitle "{esc(subtitle)}"' if subtitle else ""))
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True,
                           text=True, timeout=20)
        rec["sent"] = r.returncode == 0
        if r.returncode != 0:
            rec["error"] = r.stderr.strip()[:200]
    except (subprocess.TimeoutExpired, OSError) as e:
        rec["error"] = str(e)
    _log(rec, log_path)
    return rec


def send_sms(message, justification, now=None, config_path=CONFIG, log_path=LOG,
             dry_run=False):
    """Twilio SMS. Refuses unless enabled, justified, configured, and under cap.

    Returns a record explaining exactly why it did or didn't send. This function
    never raises on a missing config — a push channel that crashes is worse than
    one that declines.
    """
    now = now or datetime.datetime.now().astimezone()
    cfg = load_config(config_path)
    rec = {"ts": now.isoformat(), "channel": "sms", "message": message,
           "justification": justification, "sent": False}

    justified, reasons = justification if isinstance(justification, tuple) \
        else (bool(justification), [str(justification)])
    if not justified:
        rec["reason"] = "not justified — if unsure whether it is push-worthy, it isn't"
        _log(rec, log_path)
        return rec

    if not cfg.get("sms_enabled"):
        rec["reason"] = "sms_enabled is false in state/push-config.json"
        _log(rec, log_path)
        return rec

    budget = sms_budget(now, log_path)
    if budget["cap_reached"]:
        rec["reason"] = budget["note"]
        _log(rec, log_path)
        return rec

    missing = [k for k in ("account_sid", "auth_token", "from_number", "to_number")
               if not cfg.get(k)]
    if missing:
        rec["reason"] = f"twilio not configured — missing {', '.join(missing)}"
        _log(rec, log_path)
        return rec

    if dry_run:
        rec["reason"] = "dry run — would have sent"
        _log(rec, log_path)
        return rec

    try:
        import urllib.parse
        import urllib.request
        url = (f"https://api.twilio.com/2010-04-01/Accounts/"
               f"{cfg['account_sid']}/Messages.json")
        data = urllib.parse.urlencode({
            "From": cfg["from_number"], "To": cfg["to_number"], "Body": message,
        }).encode()
        req = urllib.request.Request(url, data=data)
        auth = f"{cfg['account_sid']}:{cfg['auth_token']}"
        import base64
        req.add_header("Authorization",
                       "Basic " + base64.b64encode(auth.encode()).decode())
        with urllib.request.urlopen(req, timeout=20) as resp:
            rec["sent"] = 200 <= resp.status < 300
            rec["status"] = resp.status
    except Exception as e:  # noqa: BLE001 — a failed push must never break the run
        rec["error"] = f"{type(e).__name__}: {e}"[:200]
        rec["reason"] = "twilio request failed"
    rec["reasons"] = reasons
    _log(rec, log_path)
    return rec
