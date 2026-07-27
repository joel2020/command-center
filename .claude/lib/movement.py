"""Derive when a project actually last moved, instead of trusting a typed date.

`last movement` in memory/projects.md is hand-written, so the 7-day red flag it
drives decays into "Joel forgot to edit the file." Two sources know better:

  git       the last commit date in each path listed under `- repos:`
  Linear    the newest updatedAt across issues in the `- linear:` project

The observed date wins only when it is MORE RECENT than the declared one. A
project can move in ways neither source sees — a phone call, a wire, a
conversation on WhatsApp — so a silent git repo is not evidence of inactivity
and must never make a project look staler than Joel says it is.

Reading git is a subprocess call, which is why this lives here and not in
projects.py: that module stays pure so it can be tested exhaustively offline.
Every failure here degrades to "no observation", never to a wrong date.
"""

import datetime
import os
import subprocess

GIT_TIMEOUT_S = 5


def _expand(path):
    return os.path.expanduser(os.path.expandvars(path.strip()))


def git_last_commit(path):
    """Last commit date as YYYY-MM-DD, or None if this isn't a readable repo.

    None means "couldn't look", which is a different answer from "no commits",
    and callers must not collapse the two.
    """
    p = _expand(path)
    if not os.path.isdir(os.path.join(p, ".git")):
        return None
    try:
        out = subprocess.run(
            ["git", "-C", p, "log", "-1", "--format=%cs"],
            capture_output=True, text=True, timeout=GIT_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    s = (out.stdout or "").strip()
    try:
        datetime.date.fromisoformat(s)
    except ValueError:
        return None
    return s


def linear_last_update(project_name, issues):
    """Newest updatedAt across issues belonging to `project_name`."""
    if not project_name:
        return None
    best = None
    for i in issues or []:
        if (i.get("project") or "") != project_name:
            continue
        ts = (i.get("updatedAt") or i.get("updated_at") or "")[:10]
        try:
            datetime.date.fromisoformat(ts)
        except ValueError:
            continue
        if best is None or ts > best:
            best = ts
    return best


def derive(project, linear_issues=None, today=None):
    """Observe a project's real last movement.

    Returns {date, source, days_stale, observations} — or date None when nothing
    could be observed. `observations` records every source that was consulted
    and what it said, including the ones that failed, so the dashboard can show
    why a project looks the way it does.
    """
    today = today or datetime.date.today()
    observations = []
    best, best_src = None, None

    for repo in project.repos:
        d = git_last_commit(repo)
        observations.append({"source": f"git:{repo}", "date": d,
                             "read": d is not None})
        if d and (best is None or d > best):
            best, best_src = d, f"git:{repo}"

    if project.linear:
        d = linear_last_update(project.linear, linear_issues)
        observations.append({"source": f"linear:{project.linear}", "date": d,
                            "read": d is not None})
        if d and (best is None or d > best):
            best, best_src = d, f"linear:{project.linear}"

    days = None
    if best:
        days = (today - datetime.date.fromisoformat(best)).days

    return {"date": best, "source": best_src, "days_stale": days,
            "observations": observations}


def derive_all(projects, linear_issues=None, today=None):
    """Map project name -> derive() result, for projects declaring a source."""
    out = {}
    for p in projects:
        if not p.repos and not p.linear:
            continue
        out[p.name] = derive(p, linear_issues, today)
    return out
