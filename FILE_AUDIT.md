# File audit — read-only

Run 2026-07-26 by `.claude/lib/audit.py`. Full data in `state/file-audit.json`.

**Nothing was moved, renamed, or deleted.** This is a measurement.

Scope: `Desktop`, `Downloads`, `Documents`, `Pictures`, `Movies`, `Music`.
Skipped: `~/Library`, `node_modules`, `.git` internals, build output, caches.
Symlinks were recorded, never followed.

```
files          102,262   (30.5 GB)
duplicates     367 groups, 9.9 GB reclaimable
stale 2y+      1,368 files
danger zones   6
symlinks       0
cloud roots    1  (~/Library/Mobile Documents)
```

---

## 1. The headline: Desktop and Downloads are the same folder twice

58 of the largest duplicate groups pair a file in `~/Desktop` with an identical file
in `~/Downloads` — **6.3 GB across just those 58 groups**, and the pattern holds
across three whole subtrees:

| Subtree | On Desktop | In Downloads |
|---|---|---|
| `Alex music/` | 4.1 GB, 274 files | 4.1 GB, 276 files |
| `personal/` | 4.0 GB, 195 files | 4.0 GB, 196 files |
| `Alivio/` | 178.4 MB, 494 files | 178.5 MB, 496 files |

Every pair verified by SHA-256, not filename. The counts differ by one or two files
per tree, so these are near-copies rather than exact mirrors — **something copied
instead of moved, and left both sides in place.**

`~/migration-logs` and `~/Documents/Mac Safe Organization Logs` are both dated
2026-07-25, hours before this audit. That is almost certainly where this came from.
Before anything gets deleted, that job's logs should be read to confirm which side
it considered authoritative.

**This one finding is 64% of all reclaimable space.** Resolving it is the whole of
Phase 4's value; everything below is small by comparison.

### Biggest individual offenders

| Wasted | Copies | File |
|---:|---:|---|
| 1.1 GB | 2 | `2.0. Real Estate Explanation of Investment James Videos & Pricing updated 2.1.pptx` |
| 1.1 GB | 2 | `personal/Screen Recording 2022-05-18 at 11.42.06 AM.mov` |
| 1.0 GB | 2 | `personal/colombia - HD 720p.mov` |
| 1.0 GB | 2 | `personal/2021-05-05 19:03:04 - HD 720p.mov` |
| 656 MB | 2 | `personal/90.Day.Fiance...mkv` |
| 366 MB | **3** | `claude-code-backup.tar.gz` — Desktop, Downloads, and `Downloads/... 2.tar.gz` |
| 199 MB | 2 | `spoke-phone-desktop.dmg` and `spoke-phone-desktop (1).dmg` — both in Downloads |

---

## 2. Where the space actually is

| Size | Files | Location |
|---:|---:|---|
| 7.7 GB | 97,970 | `Pictures/Photos Library.photoslibrary` ← **do not touch, see DO_NOT_TOUCH.md** |
| 4.1 GB | 276 | `Downloads/Alex music` |
| 4.1 GB | 274 | `Desktop/Alex music` |
| 4.0 GB | 39 | `Downloads` (loose files at top level) |
| 4.0 GB | 196 | `Downloads/personal` |
| 4.0 GB | 195 | `Desktop/personal` |
| 1.3 GB | 21 | `Desktop` (loose files at top level) |
| 435.7 MB | 1,208 | `Documents/Codex` |
| 246.5 MB | 31 | `Documents` (loose files at top level) |
| 178.5 MB | 496 | `Downloads/Alivio` |
| 178.4 MB | 494 | `Desktop/Alivio` |
| 159.6 MB | 16 | `Documents/Zoom` |

The Photos Library is 96% of the file count and 25% of the bytes. Excluding it, the
real organizable surface is about **4,300 files and 23 GB** — a much smaller problem
than "102,262 files" suggests.

---

## 3. Danger zones

Six directories contain live projects. The folder may be movable; **its contents are
not** — moving files individually out of these breaks git history, imports, or builds.

| Path | Why |
|---|---|
| `Documents/Codex/2026-05-28/you-are-taking-over-the-elite/repo` | git repo, node_modules, JS project |
| `Documents/Codex/2026-05-28/you-are-taking-over-the-elite 2/repo` | git repo, node_modules, JS project |
| `Documents/Codex/2026-06-10/i-need-you-to-review-my/work/stable-lights-creations` | git repo, node_modules, JS project |
| `Documents/Codex/2026-06-10/i-need-you-to-review-my/work/video_ad/node_ffmpeg` | node_modules, JS project |
| `Documents/Codex/2026-06-15/please-tell-me-what-was-done/outputs/callpipe` | JS project |
| `Documents/Codex/2026-06-16/did-you-respond-to-google-auth` | JS project |

Note `you-are-taking-over-the-elite` and `you-are-taking-over-the-elite 2` — a
duplicated git checkout. Also: a copy of `stable-lights-creations` lives inside
`Documents/Codex`, separate from `~/stable-lights-creations`. Which is authoritative
is a question for you, not a guess for me.

**Nothing in `~` above these — the 8 active repos at the top level of home — was in
scope. Those aren't Phase 4's business.**

## 4. Cloud roots

`~/Library/Mobile Documents` (iCloud Drive) exists and was **not** scanned. Files
under a cloud-sync root must never be moved by this system: a local move becomes a
remote move, and it propagates before anyone notices.

No Dropbox, Google Drive, or OneDrive roots found.

## 5. Databases and symlinks

Every `.sqlite`/`.db` found is inside the Photos Library — Apple's, not yours, and
off limits. One stray `.pkl` in `Downloads/blender-logo-work/deps/numpy` is test
data inside a dependency tree.

**Zero symlinks** in scope. That removes a whole category of risk.

## 6. Stale files

1,368 files untouched for 2+ years. Old is not the same as unwanted — `Desktop`
holds `Joel Carias FTC Report.pdf` (2025) and several `~$`-prefixed Word lock files
from 2020–2023 that are genuine junk. Staleness is a sorting hint here, not a
delete signal, and this audit proposes deleting nothing.

---

## What this audit does not tell you

- **Which side of a Desktop/Downloads pair is authoritative.** Both mtimes were
  rewritten by the 2026-07-25 migration.
- **Whether `Alex music` is yours or Alex's.** 8.2 GB across both copies, and the
  name suggests it belongs to someone else.
- **Whether the `Documents/Codex` trees are worth keeping** — they look like archived
  agent-session outputs, 1,208 files, some containing full repo checkouts.

Those three answers change the taxonomy. See `PROPOSED_STRUCTURE.md`.
