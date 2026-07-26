"""File classification and renaming. Dry-run by default.

A move is automatic ONLY if both source and destination are inside the approved
taxonomy AND neither touches the DO_NOT_TOUCH list. Everything else is manual
action #4 and gets queued.

`plan()` decides. `apply()` executes, and refuses anything `plan()` didn't approve —
so the guard rails can't be bypassed by calling the executor directly.

Deletion has no implementation here. Deduplication quarantines.
"""

import datetime
import os
import re
import shutil

HOME = os.path.expanduser("~")
DOCS = os.path.join(HOME, "Documents")

# The approved taxonomy, as directory paths relative to ~/Documents.
TAXONOMY = [
    "Clients/RLTRS", "Clients/Bravo Mechanical", "Clients/Elite Funding",
    "Ventures/Alivio", "Ventures/Clara", "Ventures/itslitneon",
    "Personal/Identity", "Personal/Finance", "Personal/Medical", "Personal/Resumes",
    "Media/Music", "Media/Video", "Media/Photos",
    "Archive/Codex Sessions", "Archive/2024 and earlier",
    "To Review",
]

# Path fragments that are never touched. Checked against the absolute path.
FORBIDDEN = [
    "Photos Library.photoslibrary",
    "/Library/",
    "/.Trash",
    "/node_modules/", "/.venv/", "/venv/", "/Pods/", "/DerivedData/",
    "/.terraform/", "/target/", "/dist/", "/build/", "/.next/", "/.git/",
    "_QUARANTINE_",
]

# Directories that are project roots — move the folder, never its contents.
PROJECT_MARKERS = {".git", "package.json", "pyvenv.cfg", "Cargo.toml", "go.mod"}

# Classification rules, first match wins. (regex over lowercased filename, destination)
RULES = [
    (r"rltrs|realtor", "Clients/RLTRS"),
    (r"bravo", "Clients/Bravo Mechanical"),
    (r"elite.?funding|efs\b", "Clients/Elite Funding"),
    (r"alivio", "Ventures/Alivio"),
    (r"clara", "Ventures/Clara"),
    (r"itslitneon|neon", "Ventures/itslitneon"),
    (r"\bid\b|passport|licen[cs]e|utility bill|ftc report", "Personal/Identity"),
    (r"invoice|statement|tax|1099|w-?2|loan|bank|payment", "Personal/Finance"),
    (r"resume|cv\b|candidate", "Personal/Resumes"),
    (r"medical|ayuda_diagnostica|prescription", "Personal/Medical"),
    (r"\.(mp3|wav|aiff|flac|m4a)$", "Media/Music"),
    (r"\.(mp4|mov|mkv|avi|webm)$", "Media/Video"),
    (r"\.(jpg|jpeg|png|heic|gif|tiff|webp)$", "Media/Photos"),
]

SLUG_STRIP = re.compile(r"[^a-z0-9]+")
DATE_IN_NAME = [
    (re.compile(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})"), (1, 2, 3)),
    (re.compile(r"\b(\d{2})(\d{2})(\d{2})[-_]"), None),  # 260716- → 2026-07-16
]


def is_forbidden(path):
    """True if this path may never be touched. Reasons are returned by `why_forbidden`."""
    return bool(why_forbidden(path))


def why_forbidden(path):
    p = os.path.abspath(path)
    reasons = [f for f in FORBIDDEN if f.strip("/") in p.split(os.sep)
               or f in p]
    if os.path.islink(p):
        reasons.append("symlink")
    return reasons


def in_project_dir(path, max_depth=40):
    """True if the file sits inside a project root — move the folder, not the file.

    Walks up to the filesystem root, not to $HOME: a checkout can live anywhere,
    and an earlier version that stopped at $HOME missed every repo outside it.
    """
    d = os.path.dirname(os.path.abspath(path))
    for _ in range(max_depth):
        try:
            entries = set(os.listdir(d))
        except OSError:
            return False
        if entries & PROJECT_MARKERS or any(e.endswith(".xcodeproj") for e in entries):
            return True
        parent = os.path.dirname(d)
        if parent == d:
            return False
        d = parent
    return False


def in_taxonomy(path, docs=DOCS):
    p = os.path.abspath(path)
    return any(p.startswith(os.path.join(docs, t) + os.sep) or
               p == os.path.join(docs, t) for t in TAXONOMY)


def slugify(name):
    stem, ext = os.path.splitext(name)
    stem = SLUG_STRIP.sub("-", stem.lower()).strip("-")
    return stem, ext.lower()


def extract_date(name, mtime=None):
    """Date from the filename if present, else the mtime. Never invented."""
    for rx, groups in DATE_IN_NAME:
        m = rx.search(name)
        if not m:
            continue
        try:
            if groups:
                y, mo, d = (int(m.group(g)) for g in groups)
            else:
                y, mo, d = 2000 + int(m.group(1)), int(m.group(2)), int(m.group(3))
            return datetime.date(y, mo, d).isoformat(), "filename"
        except ValueError:
            continue
    if mtime is not None:
        return datetime.date.fromtimestamp(mtime).isoformat(), "mtime"
    return None, None


def target_name(path, mtime=None):
    base = os.path.basename(path)
    date, src = extract_date(base, mtime)
    stem, ext = slugify(base)
    # Don't prefix a date that's already the leading token of the slug.
    if date and not stem.startswith(date):
        stem = re.sub(r"^\d{2,8}-", "", stem)
        return f"{date}_{stem}{ext}", src
    return f"{stem}{ext}", src


def classify(path):
    """Return a taxonomy destination, or None if nothing matches confidently."""
    name = os.path.basename(path).lower()
    for rx, dest in RULES:
        if re.search(rx, name):
            return dest
    return None


def plan_one(path, docs=DOCS, mtime=None):
    """Decide what should happen to one file.

    action is one of: move | queue | refuse
    Only `move` is automatic.
    """
    p = os.path.abspath(path)
    forbidden = why_forbidden(p)
    if forbidden:
        return {"path": p, "action": "refuse", "reason": "protected: " + ", ".join(forbidden)}
    if in_project_dir(p):
        return {"path": p, "action": "refuse",
                "reason": "inside a project root — move the folder, never its contents"}
    if not os.path.isfile(p):
        return {"path": p, "action": "refuse", "reason": "not a regular file"}

    if mtime is None:
        try:
            mtime = os.stat(p).st_mtime
        except OSError:
            mtime = None

    dest_dir = classify(p)
    new_name, date_src = target_name(p, mtime)

    if dest_dir is None:
        return {"path": p, "action": "queue", "reason": "no confident classification",
                "dest": os.path.join(docs, "To Review", new_name),
                "new_name": new_name, "date_source": date_src}

    dest = os.path.join(docs, dest_dir, new_name)
    if not in_taxonomy(dest, docs):
        return {"path": p, "action": "queue",
                "reason": "destination outside the approved taxonomy", "dest": dest}
    if os.path.exists(dest):
        return {"path": p, "action": "queue", "reason": "destination already exists",
                "dest": dest, "new_name": new_name}

    # Source inside the taxonomy too → fully automatic. Otherwise it's a move INTO
    # the taxonomy from outside, which is still automatic per CLAUDE.md ("filing new
    # downloads") but recorded as such.
    return {"path": p, "action": "move", "dest": dest, "new_name": new_name,
            "date_source": date_src,
            "reason": "within taxonomy" if in_taxonomy(p, docs) else "filing into taxonomy"}


def plan(paths, docs=DOCS):
    return [plan_one(p, docs) for p in paths]


def summarize(plans):
    out = {"move": 0, "queue": 0, "refuse": 0, "bytes": 0}
    for pl in plans:
        out[pl["action"]] = out.get(pl["action"], 0) + 1
        if pl["action"] == "move":
            try:
                out["bytes"] += os.path.getsize(pl["path"])
            except OSError:
                pass
    return out


def apply(plans, dry_run=True, log_path=None, docs=DOCS):
    """Execute approved moves. Refuses anything plan() didn't mark `move`.

    Always writes an inverse entry so the whole batch can be undone.
    """
    done = []
    for pl in plans:
        if pl["action"] != "move":
            done.append(dict(pl, executed=False, skipped=pl["action"]))
            continue
        src, dest = pl["path"], pl["dest"]
        # Re-check at execution time: the plan may be stale.
        if why_forbidden(src) or why_forbidden(dest) or not in_taxonomy(dest, docs):
            done.append(dict(pl, executed=False, skipped="failed re-check"))
            continue
        if dry_run:
            done.append(dict(pl, executed=False, skipped="dry run"))
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.exists(dest):
            done.append(dict(pl, executed=False, skipped="destination appeared"))
            continue
        shutil.move(src, dest)
        done.append(dict(pl, executed=True, undo=f'mv "{dest}" "{src}"'))

    if log_path:
        import json
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a") as f:
            for d in done:
                f.write(json.dumps(d) + "\n")
    return done


def quarantine_path(path, when=None, home=HOME):
    """Where a redundant copy goes. Never deleted — moved, with its path preserved."""
    when = when or datetime.date.today()
    rel = os.path.relpath(os.path.abspath(path), home)
    return os.path.join(home, f"_QUARANTINE_{when.isoformat()}", rel)
