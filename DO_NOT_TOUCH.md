# Do not touch

Hard exclusions for any file operation, now or in any later phase. This list is
enforced in code, not by memory — `.claude/lib/filing.py` refuses paths matching it.

A move here isn't a mistake that costs a minute. It costs a repo, a photo library,
or a synced folder that propagates the damage before anyone notices.

---

## Never move, never rename, never descend into

**`~/Pictures/Photos Library.photoslibrary`**
A macOS package, not a folder. 97,970 files, 7.7 GB, containing Apple's own SQLite
databases. Moving anything inside corrupts the library. Finder shows it as one item
for a reason.

**`~/Library` and `~/Library/Mobile Documents`**
Application support and iCloud Drive. A local move inside a cloud root becomes a
remote move and syncs before you can undo it.

**The 8 active git repos at the top level of `~`**
`alivio-platform`, `alivio-search-partners`, `clara`, `command-center`,
`stable-lights-creations`, `orchids-aliviosearch-com`, `EliteFundingSolutions1`,
`bravo-verify` — plus `whatsapp-mcp`, `clara-agency`, and the other project dirs.

Move the *repo folder* if you want. Never move a file out of one. Git tracks paths;
imports resolve relative to them.

⚠️ `~/bravo-verify` has **uncommitted changes** on branch `fix/single-phone-number`.
Nothing may touch it until that work is committed or stashed — an uncommitted change
is the one thing git can't get back for you.

**The 6 danger zones inside `Documents/Codex`**
```
Documents/Codex/2026-05-28/you-are-taking-over-the-elite/repo
Documents/Codex/2026-05-28/you-are-taking-over-the-elite 2/repo
Documents/Codex/2026-06-10/i-need-you-to-review-my/work/stable-lights-creations
Documents/Codex/2026-06-10/i-need-you-to-review-my/work/video_ad/node_ffmpeg
Documents/Codex/2026-06-15/please-tell-me-what-was-done/outputs/callpipe
Documents/Codex/2026-06-16/did-you-respond-to-google-auth
```
Each contains a git repo, `node_modules`, or a JS project root.

**Anything inside `node_modules`, `.venv`, `venv`, `Pods`, `DerivedData`,
`.terraform`, `target`, `dist`, `build`, `.next`**
Package-manager territory. Reinstallable, and moving it breaks the build until it's
reinstalled.

**`~/.Trash`**
Already deleted. Leave it.

---

## Never delete — full stop

Deletion is manual action #2 and has no automated path in this system, ever.
Deduplication, when it happens, works by **quarantine**: move the redundant copy to
`~/_QUARANTINE_<date>/` preserving its original path underneath, and log it. You
delete the quarantine yourself, later, once you're sure.

The 9.9 GB of duplicates is not a deletion job. It's a quarantine job.

---

## Specific files flagged during the audit

**`~/Desktop/Daniel Vargas ID.jpeg`** and **`~/Documents/daniel vargas utility bill.pdf`**
Someone else's identity documents. Whatever the taxonomy says, these need a decision
from you about retention, not a filing rule.

**`~/Desktop/Joel Carias FTC Report.pdf`**, **`~/Documents/Important Notices.pdf`**,
loan and bank PDFs in `~/Documents`
Financial and legal records. File them, never touch their contents, never dedupe
them by heuristic.

**`~/.claude-pre-restore-snapshot.tar.gz`** (95 MB), **`~/Desktop/claude-code-backup.tar.gz`** (183 MB)
Backups. They look like waste and are the exact thing you'd want if a restore goes
wrong. Out of scope.

---

## The rule underneath all of this

A file operation is automatic **only if both source and destination are inside the
approved taxonomy** in `PROPOSED_STRUCTURE.md`. Everything else — including anything
that merely touches this list — is manual action #4 and gets queued for you.

When in doubt, the answer is queue it. A file in the wrong folder costs a minute.
Everything on this page costs more.
