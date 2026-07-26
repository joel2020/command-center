---
description: Propose a filing plan; execute only in-taxonomy moves
---

File loose documents into the approved taxonomy. **Dry-run by default.**

Read `PROPOSED_STRUCTURE.md` and `DO_NOT_TOUCH.md` before running this. If the
taxonomy hasn't been approved by Joel yet, stop — say so and don't propose moves.

## 1. Plan

```bash
python3 -c "
import sys,json,glob,os;sys.path.insert(0,'.claude/lib');import filing
paths=[p for p in glob.glob(os.path.expanduser('~/Downloads/*')) if os.path.isfile(p)]
plans=filing.plan(paths)
print(json.dumps(filing.summarize(plans),indent=2))
for p in plans:
    print(f\"{p['action']:<7} {os.path.basename(p['path'])[:50]:<52} {p.get('reason','')}\")
"
```

Three outcomes, and only one is automatic:

- **move** — both ends inside the taxonomy, nothing protected. Automatic.
- **queue** — unclassifiable, destination occupied, or leaving the taxonomy.
  Goes to the approval queue as manual action #4.
- **refuse** — protected path, project root, or symlink. Never proposed at all.

## 2. Show Joel the diff summary before executing

N files, M folders, X GB. If a single batch touches 500+ files, stop and confirm
again — that's a separate decision from the first approval.

## 3. Execute

```bash
python3 -c "
import sys,json;sys.path.insert(0,'.claude/lib');import filing
plans=json.load(open('/tmp/plans.json'))
res=filing.apply(plans, dry_run=False,
                 log_path='/Users/joel/organization-log-$(date +%F).jsonl')
print(sum(1 for r in res if r['executed']),'moved')
"
```

`apply()` re-checks every guard at execution time and refuses anything `plan()`
didn't mark `move`. A hand-edited plan cannot bypass the protections.

Every executed move records its inverse (`mv <dest> <src>`) in the log. That log is
the undo script.

## 4. Queue the rest

```bash
python3 -c "
import sys;sys.path.insert(0,'.claude/lib');import queue as q
d=q.load(); q.propose(d,'file-move','<file> → <dest>',0.8,detail='<why>',source='/file'); q.save(d)"
```

## Deduplication

Never deletion. Move the redundant copy to `~/_QUARANTINE_<date>/` with its original
path preserved underneath:

```bash
python3 -c "
import sys;sys.path.insert(0,'.claude/lib');import filing
print(filing.quarantine_path('/Users/joel/Downloads/personal/x.mov'))"
```

Joel deletes the quarantine himself once he's satisfied. There is no code path in
this system that deletes a file.

## The rule

A move is automatic **only** if source and destination are both inside the approved
taxonomy. Everything else is manual action #4. When in doubt, queue it — a file in
the wrong folder costs a minute, and the alternatives cost more.
