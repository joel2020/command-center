"""Read-only filesystem audit. Phase 4, step one.

This module cannot move, rename, or delete anything. It walks, measures, hashes,
and reports. The proposal it feeds into is Joel's to approve — PHASES.md is explicit
that execution happens only after sign-off.

Duplicate detection is by content: group by size, then SHA-256 within each group.
Filename matching would call `IMG_4180.jpeg` and `IMG_4180 2.jpeg` duplicates
without checking, which is exactly the mistake that loses a file.
"""

import argparse
import datetime
import hashlib
import json
import os

HOME = os.path.expanduser("~")

# Walked for the audit.
SCAN_ROOTS = ["Desktop", "Downloads", "Documents", "Pictures", "Movies", "Music"]

# Never descended into. Cheap to skip and nothing in them is Joel's to organize.
SKIP_DIRS = {
    "node_modules", ".git", ".venv", "venv", "env", "__pycache__", ".next",
    ".turbo", "dist", "build", ".cache", "Library", ".Trash", ".pnpm-store",
    "vendor", "Pods", ".gradle", "DerivedData", ".terraform", "target",
}

# A directory containing any of these is a danger zone: moving its contents breaks
# something. The folder itself may be movable; its insides are not.
DANGER_MARKERS = {
    ".git": "git repository",
    ".xcodeproj": "Xcode project",
    ".xcworkspace": "Xcode workspace",
    "pyvenv.cfg": "python virtualenv",
    "node_modules": "installed dependencies",
    "package.json": "javascript project",
    "Cargo.toml": "rust project",
    "go.mod": "go module",
    ".terraform": "terraform state",
    "docker-compose.yml": "docker project",
}

CLOUD_ROOTS = ["Dropbox", "Google Drive", "OneDrive", "iCloud Drive", "Creative Cloud",
               "Library/Mobile Documents", "Sync"]

DB_EXTS = {".db", ".sqlite", ".sqlite3", ".realm", ".mdb", ".accdb", ".pkl"}

STALE_YEARS = 2
LARGEST_N = 50
MIN_DUP_BYTES = 1024 * 1024  # ignore tiny files; the win isn't worth the hashing


def _sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while True:
                b = f.read(chunk)
                if not b:
                    break
                h.update(b)
    except OSError:
        return None
    return h.hexdigest()


def walk(roots=None, home=HOME):
    """Yield (path, stat) for every regular file under roots. Symlinks are recorded
    but never followed — following them is how an audit ends up outside its scope."""
    roots = roots or SCAN_ROOTS
    symlinks = []
    for root in roots:
        base = os.path.join(home, root)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base, topdown=True):
            dirnames[:] = [d for d in dirnames
                           if d not in SKIP_DIRS and not d.startswith(".")]
            for name in filenames:
                p = os.path.join(dirpath, name)
                if os.path.islink(p):
                    symlinks.append(p)
                    continue
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                yield p, st, symlinks


def collect(roots=None, home=HOME):
    files, symlinks = [], []
    for p, st, syms in walk(roots, home):
        files.append((p, st.st_size, st.st_mtime))
        symlinks = syms
    return files, symlinks


def by_folder(files, home=HOME, depth=2):
    """Counts and bytes grouped by top folders."""
    agg = {}
    for p, size, _ in files:
        rel = os.path.relpath(p, home)
        parts = rel.split(os.sep)
        key = os.sep.join(parts[:depth]) if len(parts) > depth else os.sep.join(parts[:-1])
        e = agg.setdefault(key or ".", {"count": 0, "bytes": 0})
        e["count"] += 1
        e["bytes"] += size
    return dict(sorted(agg.items(), key=lambda kv: -kv[1]["bytes"]))


def largest(files, n=LARGEST_N):
    return sorted(files, key=lambda f: -f[1])[:n]


def stale(files, years=STALE_YEARS, now=None):
    now = now or datetime.datetime.now().timestamp()
    cutoff = now - years * 365.25 * 86400
    return [f for f in files if f[2] < cutoff]


def duplicates(files, min_bytes=MIN_DUP_BYTES):
    """Exact duplicates by SHA-256, size-grouped first so we hash as little as possible."""
    by_size = {}
    for p, size, _ in files:
        if size < min_bytes:
            continue
        by_size.setdefault(size, []).append(p)

    groups = []
    hashed = 0
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        by_hash = {}
        for p in paths:
            h = _sha256(p)
            hashed += 1
            if h:
                by_hash.setdefault(h, []).append(p)
        for h, ps in by_hash.items():
            if len(ps) > 1:
                groups.append({"hash": h, "size": size, "paths": sorted(ps),
                               "wasted_bytes": size * (len(ps) - 1)})
    groups.sort(key=lambda g: -g["wasted_bytes"])
    return groups, hashed


def danger_zones(roots=None, home=HOME):
    """Directories whose contents must never be moved individually."""
    roots = roots or SCAN_ROOTS
    found = []
    for root in roots:
        base = os.path.join(home, root)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base, topdown=True):
            entries = set(dirnames) | set(filenames)
            hits = set()
            for marker, why in DANGER_MARKERS.items():
                if marker in entries or any(e.endswith(marker) for e in entries):
                    hits.add(why)
            if hits:
                found.append({"path": dirpath, "reasons": sorted(hits)})
                dirnames[:] = []  # don't descend — the whole tree is off limits
                continue
            dirnames[:] = [d for d in dirnames
                           if d not in SKIP_DIRS and not d.startswith(".")]
    return found


def cloud_roots(home=HOME):
    return [os.path.join(home, c) for c in CLOUD_ROOTS
            if os.path.exists(os.path.join(home, c))]


def databases(files):
    return [f for f in files if os.path.splitext(f[0])[1].lower() in DB_EXTS]


def human(n):
    for unit in ("B", "K", "M", "G", "T"):
        if abs(n) < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}P"


def run(roots=None, home=HOME, skip_dupes=False):
    files, symlinks = collect(roots, home)
    dupes, hashed = ([], 0) if skip_dupes else duplicates(files)
    return {
        "generated_at": datetime.datetime.now().astimezone().isoformat(),
        "roots": roots or SCAN_ROOTS,
        "file_count": len(files),
        "total_bytes": sum(f[1] for f in files),
        "by_folder": by_folder(files, home),
        "largest": [{"path": p, "bytes": s} for p, s, _ in largest(files)],
        "stale": [{"path": p, "bytes": s,
                   "mtime": datetime.date.fromtimestamp(m).isoformat()}
                  for p, s, m in sorted(stale(files), key=lambda f: -f[1])[:100]],
        "stale_count": len(stale(files)),
        "duplicates": dupes[:60],
        "duplicate_group_count": len(dupes),
        "wasted_bytes": sum(g["wasted_bytes"] for g in dupes),
        "files_hashed": hashed,
        "danger_zones": danger_zones(roots, home),
        "cloud_roots": cloud_roots(home),
        "symlinks": symlinks[:50],
        "databases": [{"path": p, "bytes": s} for p, s, _ in databases(files)][:50],
    }


def main():
    ap = argparse.ArgumentParser(description="Read-only filesystem audit.")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__),
                                                  "..", "..", "state", "file-audit.json"))
    ap.add_argument("--skip-dupes", action="store_true")
    ap.add_argument("--roots", nargs="*", default=None)
    args = ap.parse_args()

    r = run(args.roots, skip_dupes=args.skip_dupes)
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(r, f, indent=2)

    print(f"files          {r['file_count']:,}  ({human(r['total_bytes'])})")
    print(f"duplicates     {r['duplicate_group_count']} groups, "
          f"{human(r['wasted_bytes'])} reclaimable  ({r['files_hashed']} hashed)")
    print(f"stale 2y+      {r['stale_count']:,}")
    print(f"danger zones   {len(r['danger_zones'])}")
    print(f"symlinks       {len(r['symlinks'])}")
    print(f"cloud roots    {len(r['cloud_roots'])}")
    print(f"\nwrote {out}")
    print("\ntop folders by size:")
    for k, v in list(r["by_folder"].items())[:12]:
        print(f"  {human(v['bytes']):>8}  {v['count']:>6} files  {k}")


if __name__ == "__main__":
    main()
