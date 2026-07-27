"""What is at risk right now — money, and work that exists in only one place.

Two questions the dashboard could not answer before this module.

**Money.** `build_dashboard` already reads an `amount` off every due Linear issue
and `template.html` already renders a `.money` span for it, but Linear has no
amount field, so the value was always None and the span never appeared. The
figures are sitting in the issue titles: "Week 1 — Submit RLTRS.co for
acceptance ($4,000 paid + $6,000 on signing)". Parsing them turns eight separate
overdue rows into one number Joel actually reacts to.

**Unbacked work.** A personal operating system that cannot survive its own
hardware is not one. On 2026-07-26 two repos had no remote at all: this one,
holding the entire system, and alivio-search-partners, holding a finished v2
design system in two local-only commits. Nothing anywhere reported that.

Both are read-only. This module never pushes, never commits, never writes to a
repo — it reports, and Joel decides.
"""

import datetime
import os
import re
import subprocess

GIT_TIMEOUT_S = 5

# "$4,000", "$2,000.50", "$10k". Deliberately narrow: a bare "2000" in a title
# is far more likely to be a row count or a port number than a fee.
MONEY_RE = re.compile(r"\$\s?([\d,]+(?:\.\d{1,2})?)\s*([kK])?\b")


def parse_amounts(text):
    """Every dollar figure in a string, largest first."""
    out = []
    for raw, k in MONEY_RE.findall(text or ""):
        try:
            v = float(raw.replace(",", ""))
        except ValueError:
            continue
        if k:
            v *= 1000
        out.append(v)
    return sorted(out, reverse=True)


def issue_amount(issue):
    """The money attached to one issue.

    Sums the figures in the title, because a milestone reading "$4,000 paid +
    $6,000 on signing" is worth $10,000 in total exposure, and the point of this
    number is to convey scale rather than to invoice from it.
    """
    amounts = parse_amounts(issue.get("title", ""))
    return sum(amounts) if amounts else None


def money_at_risk(issues, today=None):
    """Overdue and imminent money, from Linear issue titles.

    Overdue is the headline. Due-soon is included separately rather than merged
    in, because "you have missed this" and "this is coming" prompt different
    behaviour and blurring them makes the number easy to dismiss.
    """
    today = today or datetime.date.today()
    overdue, soon = [], []

    for i in issues or []:
        if i.get("statusType") in ("completed", "canceled"):
            continue
        d = (i.get("dueDate") or "")[:10]
        if not d:
            continue
        try:
            due = datetime.date.fromisoformat(d)
        except ValueError:
            continue
        amt = issue_amount(i)
        if amt is None:
            continue
        row = {"id": i.get("id"), "title": i.get("title", ""),
               "project": i.get("project"), "amount": amt, "due": d,
               "days": (today - due).days, "status": i.get("status")}
        if due < today:
            overdue.append(row)
        elif (due - today).days <= 14:
            soon.append(row)

    overdue.sort(key=lambda r: -r["days"])
    soon.sort(key=lambda r: r["due"])
    return {
        "available": True,
        "overdue": overdue,
        "soon": soon,
        "overdue_total": sum(r["amount"] for r in overdue),
        "soon_total": sum(r["amount"] for r in soon),
        "worst_days": max([r["days"] for r in overdue], default=0),
    }


def _git(path, *args):
    try:
        r = subprocess.run(["git", "-C", path, *args], capture_output=True,
                           text=True, timeout=GIT_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def repo_state(path):
    """Backup exposure for one repo. None if it isn't a git repo."""
    p = os.path.realpath(os.path.expanduser(path))
    if not os.path.isdir(os.path.join(p, ".git")):
        return None

    remotes = _git(p, "remote")
    has_remote = bool(remotes)
    dirty = _git(p, "status", "--porcelain")
    dirty_n = len([l for l in (dirty or "").splitlines() if l.strip()])
    branch = _git(p, "branch", "--show-current") or ""
    commits = _git(p, "rev-list", "--count", "HEAD")
    ahead = None
    if has_remote:
        a = _git(p, "rev-list", "--count", "@{u}..HEAD")
        ahead = int(a) if (a or "").isdigit() else None

    # Unbacked = the number of commits that exist nowhere else. With no remote
    # at all that is the entire history, which is the case worth shouting about.
    if not has_remote:
        unbacked = int(commits) if (commits or "").isdigit() else None
    else:
        unbacked = ahead

    return {
        "path": p,
        "name": os.path.basename(p),
        "branch": branch,
        "has_remote": has_remote,
        "dirty": dirty_n,
        "unbacked_commits": unbacked,
        "ahead": ahead,
        # No remote is categorically worse than being ahead of one: there is no
        # second copy at all, so a disk failure is total.
        "severity": ("no-remote" if not has_remote
                     else "unpushed" if (ahead or 0) > 0
                     else "dirty" if dirty_n else "ok"),
    }


def backup_exposure(paths):
    """Which of Joel's repos exist in only one place."""
    repos, unreadable = [], []
    for path in paths or []:
        try:
            s = repo_state(path)
        except Exception as e:                      # noqa: BLE001
            unreadable.append({"path": path, "reason": str(e)})
            continue
        if s is None:
            unreadable.append({"path": path, "reason": "not a git repo"})
            continue
        repos.append(s)

    order = {"no-remote": 0, "unpushed": 1, "dirty": 2, "ok": 3}
    repos.sort(key=lambda r: (order[r["severity"]], r["name"]))
    at_risk = [r for r in repos if r["severity"] in ("no-remote", "unpushed")]
    return {
        "available": True,
        "repos": repos,
        "at_risk": at_risk,
        "no_remote": [r for r in repos if not r["has_remote"]],
        "dirty": [r for r in repos if r["dirty"]],
        "unreadable": unreadable,
        "clean": not at_risk,
    }


def project_paths(projects):
    """Every repo path declared across the approved project list."""
    seen, out = set(), []
    for p in projects or []:
        for repo in p.repos:
            r = repo.strip()
            if r and r not in seen:
                seen.add(r)
                out.append(r)
    return out


def summary(issues, projects, today=None):
    """Both risks in one call, for the dashboard."""
    money = money_at_risk(issues, today)
    backup = backup_exposure(project_paths(projects))
    return {
        "money": money,
        "backup": backup,
        "headline": _headline(money, backup),
    }


def _headline(money, backup):
    """One line, or None when there is genuinely nothing to say."""
    bits = []
    if money["overdue_total"]:
        bits.append(f"${money['overdue_total']:,.0f} overdue "
                    f"({len(money['overdue'])} milestones, worst "
                    f"{money['worst_days']}d)")
    n = len(backup["no_remote"])
    if n:
        bits.append(f"{n} repo{'s' if n != 1 else ''} with no remote")
    unpushed = [r for r in backup["at_risk"] if r["has_remote"]]
    if unpushed:
        bits.append(f"{len(unpushed)} with unpushed commits")
    return " · ".join(bits) if bits else None
