#!/usr/bin/env python3
"""Read-only drive audit. Moves nothing, renames nothing, deletes nothing.

Writes JSON to state/audit-raw.json for a separate reporting pass.
"""
import os, sys, json, hashlib, datetime, collections

HOME = os.path.expanduser("~")
OUT = os.path.join(HOME, "command-center/state/audit-raw.json")

# Directories never descended into. Excluded because their contents are either
# machine-managed (rebuildable) or would swamp the signal.
SKIP_DIRS = {
    "node_modules", ".git", ".venv", "venv", "__pycache__", ".next", ".cache",
    "Caches", ".Trash", "DerivedData", ".gradle", ".cargo", "vendor",
    "Photos Library.photoslibrary", ".npm", ".pnpm-store", "Pods", ".terraform",
}
SKIP_PREFIX = (
    os.path.join(HOME, "Library"),
    os.path.join(HOME, "command-center"),
    os.path.join(HOME, ".Trash"),
)

DANGER_MARKERS = {
    ".git": "git repo", "package.json": "node project", "Cargo.toml": "rust crate",
    "go.mod": "go module", "Podfile": "cocoapods", "pyvenv.cfg": "virtualenv",
    "requirements.txt": "python project", ".env": "SECRETS FILE",
    "docker-compose.yml": "docker", "Gemfile": "ruby project",
}
SYNC_ROOTS = ["Library/CloudStorage", "Dropbox", "Google Drive", "OneDrive", "iCloud"]
DB_EXT = {".sqlite", ".sqlite3", ".db", ".realm", ".mdb", ".accdb"}

now = datetime.datetime.now()
two_years = now - datetime.timedelta(days=730)

by_size = collections.defaultdict(list)
top_folders = collections.defaultdict(lambda: {"files": 0, "bytes": 0})
biggest, stale, danger, symlinks, dbs, secrets = [], [], [], [], [], []
total_files = total_bytes = errors = 0

def top_of(p):
    rel = os.path.relpath(p, HOME)
    return rel.split(os.sep)[0] if os.sep in rel else "(home root)"

for root, dirs, files in os.walk(HOME, topdown=True, followlinks=False):
    if root.startswith(SKIP_PREFIX):
        dirs[:] = []
        continue

    for marker, kind in DANGER_MARKERS.items():
        if marker in dirs or marker in files:
            danger.append({"path": root, "kind": kind})
            if marker == ".env":
                secrets.append(os.path.join(root, ".env"))

    dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".Trash")]

    for name in files:
        p = os.path.join(root, name)
        try:
            if os.path.islink(p):
                symlinks.append({"path": p, "target": os.readlink(p)})
                continue
            st = os.lstat(p)
        except OSError:
            errors += 1
            continue

        sz, mt = st.st_size, st.st_mtime
        total_files += 1
        total_bytes += sz
        t = top_of(p)
        top_folders[t]["files"] += 1
        top_folders[t]["bytes"] += sz

        if sz > 50 * 1024 * 1024:
            biggest.append({"path": p, "bytes": sz})
        if sz > 4096:
            by_size[sz].append(p)
        if mt < two_years.timestamp():
            stale.append({"path": p, "bytes": sz, "mtime": mt})
        if os.path.splitext(name)[1].lower() in DB_EXT:
            dbs.append({"path": p, "bytes": sz})

def sha(p, cap=200 * 1024 * 1024):
    """Full hash under cap; head+tail+size fingerprint above it."""
    h = hashlib.sha256()
    try:
        with open(p, "rb") as f:
            if os.path.getsize(p) <= cap:
                for blk in iter(lambda: f.read(1 << 20), b""):
                    h.update(blk)
            else:
                h.update(f.read(1 << 20))
                f.seek(-(1 << 20), 2)
                h.update(f.read(1 << 20))
                h.update(str(os.path.getsize(p)).encode())
    except OSError:
        return None
    return h.hexdigest()

dupes = []
for sz, paths in by_size.items():
    if len(paths) < 2:
        continue
    groups = collections.defaultdict(list)
    for p in paths:
        d = sha(p)
        if d:
            groups[d].append(p)
    for d, g in groups.items():
        if len(g) > 1:
            dupes.append({"bytes": sz, "count": len(g),
                          "reclaimable": sz * (len(g) - 1), "paths": sorted(g)})

biggest.sort(key=lambda x: -x["bytes"])
stale.sort(key=lambda x: -x["bytes"])
dupes.sort(key=lambda x: -x["reclaimable"])

json.dump({
    "generated_at": now.astimezone().isoformat(),
    "totals": {"files": total_files, "bytes": total_bytes,
               "unreadable": errors, "dupe_groups": len(dupes),
               "reclaimable": sum(d["reclaimable"] for d in dupes)},
    "top_folders": {k: v for k, v in sorted(
        top_folders.items(), key=lambda kv: -kv[1]["bytes"])},
    "biggest": biggest[:60],
    "stale": stale[:400],
    "stale_total": len(stale),
    "stale_bytes": sum(s["bytes"] for s in stale),
    "duplicates": dupes[:150],
    "danger_zones": danger,
    "symlinks": symlinks[:60],
    "databases": dbs[:60],
    "secrets_files": secrets,
    "sync_roots_note": SYNC_ROOTS,
}, open(OUT, "w"), indent=1)

print(f"DONE {total_files} files / {total_bytes/1e9:.1f} GB / "
      f"{len(dupes)} dupe groups / {errors} unreadable")
