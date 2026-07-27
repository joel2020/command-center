"""Off-disk backup for repositories that exist in only one place.

On 2026-07-26 three repositories had no git remote at all: command-center
(the whole personal OS), alivio-ops-os (the agency's operating system, its
books, and its client records), and alivio-search-partners (a finished v2 design
system in two local-only commits). One disk failure loses all three.

`git bundle` writes a repository's complete history — every commit, branch, and
tag — into a single verifiable file. Copied to iCloud Drive, that history now
exists on at least two devices and Apple's servers.

WHY THIS AND NOT A GIT REMOTE: pushing to GitHub means creating an account
resource and choosing a visibility for a repository containing client names,
invoices, and business policy. Getting that wrong is not reversible in any way
that matters, so it stays Joel's decision. This is the safe half of the problem
— it publishes nothing to a third-party code host, creates no account, and can
be deleted by dragging a folder to the trash.

IT IS NOT A REPLACEMENT for a real remote. It is what stands between Joel and
total loss until he makes that call.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys

HOME = os.path.expanduser("~")
DEST = os.path.join(HOME, "Library", "Mobile Documents",
                    "com~apple~CloudDocs", "AlivioBackups")

# Repos worth protecting. A repo WITH a working remote is already backed up;
# these are checked anyway, and skipped with a note if they gain one.
REPOS = [
    os.path.join(HOME, "command-center"),
    os.path.join(HOME, "alivio-ops-os"),
    os.path.join(HOME, "alivio-search-partners"),
]

KEEP = 5   # bundles per repo


def _git(path, *args, check=True):
    r = subprocess.run(["git", "-C", path, *args],
                       capture_output=True, text=True, timeout=120)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()[:200]}")
    return r.stdout.strip()


def repo_state(path):
    """Is this a repo, does it have a remote, and how much is unbacked?"""
    if not os.path.isdir(os.path.join(path, ".git")):
        return {"path": path, "is_repo": False}
    try:
        remotes = _git(path, "remote", check=False)
        commits = _git(path, "rev-list", "--count", "HEAD", check=False)
        dirty = _git(path, "status", "--porcelain", check=False)
        head = _git(path, "rev-parse", "HEAD", check=False)
    except (RuntimeError, subprocess.SubprocessError, OSError) as e:
        return {"path": path, "is_repo": True, "error": str(e)}
    return {
        "path": path, "name": os.path.basename(path), "is_repo": True,
        "has_remote": bool(remotes), "commits": int(commits or 0),
        "dirty_files": len([l for l in dirty.splitlines() if l.strip()]),
        "head": head,
    }


def bundle(path, dest=None, now=None):
    """Write a verified bundle. Returns a result dict; never raises."""
    dest = dest or DEST
    now = now or datetime.datetime.now()
    st = repo_state(path)
    if not st.get("is_repo"):
        return {**st, "ok": False, "reason": "not a git repository"}
    if st.get("error"):
        return {**st, "ok": False, "reason": st["error"]}
    if st["commits"] == 0:
        return {**st, "ok": False, "reason": "no commits to bundle"}

    os.makedirs(dest, exist_ok=True)
    stamp = now.strftime("%Y-%m-%d-%H%M")
    out = os.path.join(dest, f"{st['name']}-{stamp}.bundle")

    try:
        # --all captures every branch and tag, not just the current HEAD.
        _git(path, "bundle", "create", out, "--all")
    except (RuntimeError, subprocess.SubprocessError, OSError) as e:
        return {**st, "ok": False, "reason": f"bundle failed: {e}"}

    # A bundle that cannot be verified is not a backup. Check it before
    # reporting success, and delete it if it is bad — a corrupt file that looks
    # like a backup is worse than no file.
    #
    # `-C path` is load-bearing: `git bundle verify` needs a repository context
    # and fails with "need a repository to verify a bundle" without one. Called
    # bare, this deletes a perfectly good bundle whenever the process happens to
    # run outside a repo — which is every invocation except the launchd job that
    # sets WorkingDirectory. Silent data loss disguised as a failed backup.
    v = subprocess.run(["git", "-C", path, "bundle", "verify", out],
                       capture_output=True, text=True, timeout=120)
    if v.returncode != 0:
        try:
            os.unlink(out)
        except OSError:
            pass
        return {**st, "ok": False,
                "reason": f"bundle failed verification: {v.stderr.strip()[:200]}"}

    return {**st, "ok": True, "bundle": out,
            "size_mb": round(os.path.getsize(out) / 1048576, 1),
            "verified": True}


def prune(name, dest=None, keep=KEEP):
    """Keep the newest `keep` bundles per repo."""
    dest = dest or DEST
    if not os.path.isdir(dest):
        return []
    mine = sorted([f for f in os.listdir(dest)
                   if f.startswith(name + "-") and f.endswith(".bundle")])
    removed = []
    for f in mine[:-keep] if len(mine) > keep else []:
        try:
            os.unlink(os.path.join(dest, f))
            removed.append(f)
        except OSError:
            pass
    return removed


def run(repos=None, dest=None, now=None):
    dest = dest or DEST
    results = [bundle(p, dest, now) for p in (repos or REPOS)]
    for r in results:
        if r.get("ok"):
            r["pruned"] = prune(r["name"], dest)
    return {
        "ts": (now or datetime.datetime.now()).isoformat(),
        "destination": dest,
        "results": results,
        "backed_up": sum(1 for r in results if r.get("ok")),
        "failed": [r for r in results if not r.get("ok")],
        "still_without_remote": [r["name"] for r in results
                                 if r.get("is_repo") and not r.get("has_remote")],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Bundle unbacked repos to iCloud Drive")
    ap.add_argument("--dest", default=DEST)
    ap.add_argument("--status", action="store_true",
                    help="report exposure without writing anything")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if a.status:
        for p in REPOS:
            s = repo_state(p)
            if not s.get("is_repo"):
                print(f"  {os.path.basename(p):26} not a git repo")
                continue
            tag = "has remote" if s["has_remote"] else "NO REMOTE"
            print(f"  {s['name']:26} {s['commits']:>4} commits  "
                  f"{s['dirty_files']} dirty  {tag}")
        if os.path.isdir(a.dest):
            b = sorted(f for f in os.listdir(a.dest) if f.endswith(".bundle"))
            print(f"\n  {len(b)} bundle(s) in {a.dest}")
            for f in b[-6:]:
                print(f"    {f}")
        else:
            print(f"\n  no backups yet at {a.dest}")
        return 0

    res = run(dest=a.dest)
    if a.json:
        print(json.dumps(res, indent=2))
        return 0 if not res["failed"] else 1

    print(f"backing up to {res['destination']}")
    for r in res["results"]:
        if r.get("ok"):
            print(f"  OK   {r['name']:26} {r['commits']:>4} commits  "
                  f"{r['size_mb']:>6} MB  verified")
            if r.get("pruned"):
                print(f"       pruned {len(r['pruned'])} old bundle(s)")
        else:
            print(f"  SKIP {os.path.basename(r['path']):26} {r.get('reason')}")
    if res["still_without_remote"]:
        print(f"\n  Still without a git remote: "
              f"{', '.join(res['still_without_remote'])}")
        print("  This bundle is off-disk insurance, not a substitute for one.")
    return 0 if not res["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
