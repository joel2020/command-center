# Proposed structure

Derived from what the audit actually found — real client names, real ventures, the
folders you already made. No PARA, no Johnny-Decimal, no template.

**Nothing has been moved.** PHASES.md requires your approval, and I want you to tell
me what's wrong with this before anything runs.

---

## The shape you already use

You already sort by **who it's for**, not by what kind of file it is: `Desktop/Alivio`,
`Desktop/personal`, `Documents/Business/Client Projects`, `Documents/rltrs-vault`.
This proposal follows that instinct rather than replacing it.

```
~/Documents/
  Clients/
    RLTRS/            Jason + Steve. Contracts, payment schedules, the Obsidian vault
    Bravo Mechanical/ Audit, deliverables
    Elite Funding/    CRM-era docs and handoffs
  Ventures/
    Alivio/           Agreements, recruitment contracts, brand assets
    Clara/            Curriculum, student material
    itslitneon/       Brand and ad assets
  Personal/
    Identity/         IDs, reports, government letters
    Finance/          Statements, loans, tax
    Medical/
    Resumes/
  Media/
    Music/            "Alex music" lands here if it's yours — see question 2
    Video/
    Photos/           Loose images only. The Photos Library stays where it is.
  Archive/
    Codex Sessions/   The 1,208-file Documents/Codex tree
    2024 and earlier/
  To Review/          The one inbox. Anything unclassifiable waits here for you.
```

`~/Desktop` and `~/Downloads` become **transit, not storage**. Desktop holds what
you're working on this week. Downloads is a landing strip that gets filed.

## Naming

`YYYY-MM-DD_<slug>.<ext>` — the convention already visible in
`260716-RLTRSRevisedPaymentSchedule.pdf`, just normalized to sort correctly.

```
260716-RLTRSRevisedPaymentSchedule.pdf
  → 2026-07-16_rltrs-revised-payment-schedule.pdf
```

Files whose date can't be determined from name or content keep their mtime date and
get flagged, not guessed.

---

## What automatic means here

**Automatic** — moves where source *and* destination are both inside the tree above:
filing a new download, renaming to the convention, moving `To Review` items once you
classify them once.

**Queued for you** — everything else. Anything touching `DO_NOT_TOUCH.md`, anything
leaving the taxonomy, anything I'm under 90% sure about.

**Never** — deletion. The 9.9 GB of duplicates gets quarantined to
`~/_QUARANTINE_2026-07-26/` with original paths preserved, plus an inverse script
that puts every file back. You delete the quarantine when you're satisfied.

---

## Execution plan, if you approve

Reversible before anything else. For every batch:

1. Generate `move.sh` **and** `undo.sh` — the inverse, file by file
2. Print the diff summary (N files, M folders, X GB) and stop
3. Execute only after you say go
4. Log every operation to `~/organization-log-2026-07-26.jsonl` with before/after paths
5. Any single operation touching 500+ files pauses and asks again

Order, with a checkpoint after each: **Desktop → Downloads → Documents → Pictures →
Movies → everything else.** Nothing proceeds to the next until you've looked.

The Desktop/Downloads duplication is step zero — resolving 6.3 GB of exact copies
makes every later step smaller.

---

## Three questions I can't answer for you

**1. Which side of the Desktop/Downloads duplication is authoritative?**
Both trees were touched by the 2026-07-25 migration, so mtimes don't tell me. I can
read `~/migration-logs` and `~/Documents/Mac Safe Organization Logs` to find out what
that job intended — say the word and I will. Until then I won't assume.

**2. Is `Alex music` yours?**
8.2 GB across both copies, 550 files, Beatport downloads from 2022–2023. Your
`~/Documents/rekordbox` folder and the Granola note *"DJ set in Medellín — Pink
Panther brand collaboration"* say DJing is a real thread. But the folder is named
for someone else. If it's Alex's, it belongs on an external drive, not in the
taxonomy at all.

**3. Is `Documents/Codex` worth keeping?**
1,208 files, 435 MB of archived agent-session output — including two full checkouts
of the Elite Funding repo and a copy of `stable-lights-creations`. If those sessions
are disposable, this is the easiest 435 MB you'll ever recover. If they're your only
record of that work, they need to be archived properly rather than left in dated
folders named after prompts.

---

## What I think you should do first

Not the reorganization. **Resolve the duplication.** It's 64% of the reclaimable
space, it's mechanical once you tell me which side wins, and it's fully reversible
via quarantine. The taxonomy can wait until the tree isn't doubled.

And per PHASES.md, this whole phase is optional: *"If Phases 1–3 work, the file tree
may stop mattering."* You have 8 active repos and a dashboard that finds things by
project. The 30 GB is real, but so is the possibility that you never need to open
`Downloads/personal` again.
