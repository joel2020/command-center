"""Assemble dashboard/index.html from local state + connector feed.

Usage:
    python3 .claude/lib/build_dashboard.py [--no-calendar] [--out PATH]

Reads memory/projects.md, state/*, and dashboard/feed.json, queries Calendar via
AppleScript, and writes a single self-contained HTML file. No network, no CDN —
the page opens offline with `open dashboard/index.html`.

Rule enforced throughout: a section that could not be read says so. It never
renders as empty, because "nothing to do" and "I couldn't look" are different
answers and only one of them is safe.
"""

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import feed as feedmod  # noqa: E402
import projects as projectsmod  # noqa: E402

ROOT = feedmod.ROOT
TEMPLATE = os.path.join(ROOT, "dashboard", "template.html")
OUT = os.path.join(ROOT, "dashboard", "index.html")

NEEDS_ME_CAP = 10


def build_today(fd, want_calendar=True, today=None):
    today = today or datetime.date.today()
    data = fd.get("data", {})

    cal = feedmod.calendar_events() if want_calendar else \
        {"available": False, "reason": "skipped (--no-calendar)", "items": []}

    due = []
    linear = data.get("linear") or {}
    for i in linear.get("issues", []):
        d = i.get("dueDate")
        if not d or i.get("statusType") == "completed":
            continue
        try:
            dd = datetime.date.fromisoformat(d[:10])
        except (ValueError, TypeError):
            continue
        if (dd - today).days > 7:
            continue
        due.append({
            "title": i.get("title", ""),
            "id": i.get("id", ""),
            "source": "linear",
            "detail": i.get("project", ""),
            "due_human": ("overdue " + str((today - dd).days) + "d" if dd < today
                          else "due " + d[:10]),
            "overdue": dd < today,
            "amount": i.get("amount"),
        })
    due.sort(key=lambda x: (not x["overdue"], x["id"]))

    granola = data.get("granola") or {}
    meetings = [m for m in granola.get("meetings", [])][:3]

    return {
        "date_human": today.strftime("%a %b %-d, %Y"),
        "calendar": cal,
        "conflicts": feedmod.find_conflicts(cal.get("items", [])) if cal.get("available") else [],
        "due": due,
        "meetings": meetings,
    }


def build_needs_me(fd, project_list, hb, today=None):
    """Assemble NEEDS ME from every source, then apply the hard cap of 10.

    Order is severity-first: money and deadlines beat hygiene.
    """
    today = today or datetime.date.today()
    items = []

    # 1. Explicitly flagged (sub-90%-confidence actions, and anything Claude escalated)
    nm = feedmod.needs_me_file()
    for i in nm.get("items", []):
        items.append({"text": i["text"], "source": "needs-me.md",
                      "severity": "high", "label": "flagged"})

    # 2. Connector-surfaced ACT items
    data = fd.get("data", {})
    for a in (data.get("gmail") or {}).get("act", []):
        items.append({"text": a.get("subject", ""), "detail": a.get("sender", ""),
                      "source": "gmail", "severity": a.get("severity", "normal"),
                      "label": "act", "age": a.get("date", "")})

    # 3. Blocked projects
    for p in project_list:
        if p.section == "Active" and p.is_blocked():
            items.append({"text": f"{p.name} — blocked by {p.blocked_by}",
                          "detail": p.next_action, "source": "memory/projects.md",
                          "severity": "high", "label": "blocked",
                          "age": p.last_movement})

    # 4. Stale projects
    for p in project_list:
        if p.section == "Active" and p.is_stale(today) and not p.is_blocked():
            items.append({"text": f"{p.name} — no movement in {p.days_stale(today)} days",
                          "detail": p.next_action, "source": "memory/projects.md",
                          "severity": "normal", "label": "stale",
                          "age": p.last_movement})

    # 5. Scheduled tasks that missed their window
    for t in hb.get("tasks", []):
        if t["missed"]:
            items.append({
                "text": f"{t['name']} — " + ("never run" if t["never_run"]
                        else f"{round(t['age_hours'])}h since last run"),
                "source": "heartbeat.json", "severity": "normal", "label": "schedule"})

    rank = {"high": 0, "normal": 1}
    items.sort(key=lambda i: rank.get(i.get("severity"), 1))
    overflow = max(0, len(items) - NEEDS_ME_CAP)
    return {"items": items[:NEEDS_ME_CAP], "overflow": overflow}


def build(want_calendar=True, out=OUT, now=None):
    now = now or datetime.datetime.now().astimezone()
    today = now.date()

    fd = feedmod.load_feed(now=now)
    plist = projectsmod.load(feedmod.PROJECTS_MD)
    hb = feedmod.heartbeat(now=now)
    au = feedmod.automation_summary(now=now)

    projects_available = os.path.exists(feedmod.PROJECTS_MD)
    data = {
        "generated_at": now.isoformat(),
        "generated_human": now.strftime("%a %b %-d, %-I:%M %p"),
        "feed": {k: fd.get(k) for k in
                 ("present", "reason", "age_min", "stale", "unknown_age")},
        "today": build_today(fd, want_calendar, today),
        "needs_me": build_needs_me(fd, plist, hb, today),
        "projects": {
            "available": projects_available,
            "reason": None if projects_available else "memory/projects.md missing",
            "items": [p.to_dict(today) for p in plist if p.section == "Active"],
        },
        "in_flight": {"heartbeat": hb, "automation": au},
        "loose_ends": (fd.get("data", {}).get("loose_ends")
                       or {"available": False,
                           "reason": "not collected — run /dashboard to refresh connectors",
                           "items": []}),
    }

    with open(TEMPLATE) as f:
        html = f.read()

    # JSON goes inside a <script type="application/json"> block, so the only
    # sequence that can break out is a literal "</script>".
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = html.replace("__CC_DATA__", blob)

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(html)
    return data, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-calendar", action="store_true",
                    help="skip the AppleScript calendar query")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    data, out = build(want_calendar=not args.no_calendar, out=args.out)

    nm = data["needs_me"]
    print(f"built {out}")
    print(f"  projects   {len(data['projects']['items'])} active"
          f"{'' if data['projects']['available'] else ' (SOURCE MISSING)'}")
    print(f"  needs me   {len(nm['items'])} shown, {nm['overflow']} held back")
    print(f"  today      {len(data['today']['due'])} due, "
          f"{len(data['today']['calendar'].get('items', []))} events, "
          f"{len(data['today']['conflicts'])} conflicts")
    misses = [t["name"] for t in data["in_flight"]["heartbeat"].get("tasks", [])
              if t["missed"]]
    if misses:
        print(f"  !! stale   {', '.join(misses)}")
    if not data["feed"]["present"]:
        print(f"  !! feed    {data['feed']['reason']}")


if __name__ == "__main__":
    main()
