# File Audit — 26 Jul 2026

Read-only scan of `~` excluding `~/Library`, caches, `node_modules`, `.git` internals,
and the Photos library. **Nothing was moved, renamed, or deleted.**

**45,419 files · 34.26 GB · 0 unreadable**

## The headline: your Desktop is a copy of your Downloads

| | |
|---|---|
| Files on Desktop | 990 |
| Of those, also in Downloads at the **same relative path** | **986** |
| Desktop-only files | **4** |

`~/Desktop` is not a working folder. It is a 10.26 GB duplicate of a slice of your
14.09 GB Downloads folder — same subfolder structure (`personal/`, `Alex music/`),
same filenames, same bytes.

That single fact accounts for **8.09 GB of the 11.98 GB** of reclaimable duplication
across the whole drive.

Most likely cause: the migration's `rsync` of the old Mac's Desktop landed alongside
a Downloads folder that already contained the same material — so you now hold both
copies. Worth confirming before acting, but the evidence is strong.

## Totals

| Category | Count | Size |
|---|---|---|
| Duplicate groups | 3,574 | **11.98 GB** reclaimable |
| Files untouched 2+ years | 2,066 | 18.07 GB |
| Danger zones | 152 | — |
| Symlinks | 32 | — |
| Database files | 10 | — |

## Where the bulk sits

| Size | Files | Folder |
|---|---|---|
| 14.09 GB | 5,538 | `Downloads` |
| 10.26 GB | 990 | `Desktop` |
| 4.96 GB | 3,615 | `Claude` |
| 1.02 GB | 2,129 | `Documents` |
| 829 MB | 11,083 | `.hermes` |
| 625 MB | 2,360 | `.local` |
| 567 MB | 7,688 | `.codex` |
| 465 MB | 3,099 | `.claude` |
| 395 MB | 140 | `migration-logs` |

Note the file-count-to-size inversion: `Documents` holds 2,129 files in 1 GB, while
`Desktop` holds 990 files in 10 GB. The weight is in a small number of very large
media files, not in document sprawl.

## Where duplication lives

| Reclaimable | Groups | Between |
|---|---|---|
| **8.09 GB** | 135 | `Desktop` ↔ `Downloads` |
| 584 MB | 12 | `.claude` ↔ `Downloads` |
| 209 MB | 1 | within `Downloads` |

The `.claude` ↔ `Downloads` set is `claude-code-backup.tar.gz` and its unpacked
contents — session `.jsonl` transcripts from the old machine's `-Users-joelcarias`
path duplicating your current `-Users-joel` ones. Three copies of several 47–72 MB
transcripts.

## Largest single files

All eight of the largest files are duplicate pairs across Desktop/Downloads:

- 1.22 GB × 2 — `2.0. Real Estate Explanation of Investment James Videos & Pricing updated 2.1.pptx`
- 1.21 GB × 2 — `personal/Screen Recording 2022-05-18 at 11.42.06 AM.mov`
- 1.10 GB × 2 — `personal/colombia - HD 720p.mov`
- 1.10 GB × 2 — `personal/2021-05-05 19:03:04 - HD 720p.mov`

## DANGER ZONES — do not reorganize into these

| Count | Kind |
|---|---|
| 110 | node projects |
| 26 | git repos |
| **8** | **`.env` secrets files** |
| 5 | python projects |
| 2 | docker |
| 1 | rust crate |

**The 8 `.env` files matter beyond organization.** Secrets sitting in plaintext:

```
~/alivio-platform/.env
~/itslitneon/.env
~/stable-lights-creations/.env
~/Documents/Codex/2026-06-10/i-need-you-to-review-my/work/stable-lights-creations/.env
~/elite-funding-ad/oauth-demo/.env
~/orchids-aliviosearch-com/.env
```

That fourth path is a *copy* of a project `.env` sitting inside `Documents`. Duplicated
credentials in a documents folder are a real exposure, separate from any tidiness
question. Worth checking whether those keys are still live.

Git repos and node projects must be moved **as whole folders, never by their contents** —
relocating files inside them breaks the repo or the build.

## Recommendation

Do not start with a taxonomy. Start with the Desktop/Downloads collision, because it's
**8 GB, mechanical, and low-judgment** — and because any folder structure designed now
would be designed around files that shouldn't exist.

Proposed order:

1. **Confirm the Desktop↔Downloads relationship.** Spot-check 5 pairs byte-for-byte.
   If Desktop really is a subset, quarantine the 986 overlapping Desktop files to
   `~/_QUARANTINE_2026-07-26/` — not deleted, reversible, emptied by you in 30 days.
2. **Resolve the backup archive.** `claude-code-backup.tar.gz` exists in three places
   and its unpacked contents duplicate your live `.claude`. Keep one archive.
3. **Rotate or confirm the 8 `.env` files**, and remove the stray copy under `Documents`.
4. **Only then** design a taxonomy — against the ~22 GB that's actually unique.

Step 1 alone recovers roughly a third of your used space and makes everything after it
smaller and clearer.

---

*Raw data: `state/audit-raw.json`. Script: `.claude/bin/audit.py` — read-only, re-runnable.*
