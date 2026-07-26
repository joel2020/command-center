---
description: Show the approval queue and record decisions
---

Show what's waiting for Joel's approval, and record what he decides.

## Show it

```bash
python3 -c "
import sys,json;sys.path.insert(0,'.claude/lib');import queue as q
d=q.load(); items,over=q.visible(d); q.save(d)
for i in items:
    flag=' [MANUAL: '+', '.join(i['manual_action'])+']' if i['manual_action'] else ''
    print(f\"{i['id']}  {int(i['confidence']*100):>3}%  {i['kind']:<14} {i['subject']}{flag}\")
print(f'--- {len(items)} shown, {over} held back')
"
```

Read out at most 10. If there's overflow, say the count — never the items. The cap
exists so this replaces an inbox instead of becoming one.

Items flagged `MANUAL` touch one of the six permanent manual actions. Approval means
**Joel will do it**, not that Claude may.

## Record a decision

```bash
python3 -c "
import sys;sys.path.insert(0,'.claude/lib');import queue as q
d=q.load(); q.resolve(d,'<id>',q.APPROVED)  # or q.DECLINED, note='why'
q.save(d)"
```

Pass `note=` when Joel **edits** rather than accepts outright. A clean approval has
no note — that's what makes it count toward promotion.

## When Joel declines

Append the generalized reason to the "Never propose" section of
`memory/task-rules.md`. The reason generalizes; the instance doesn't.

## When Joel edits

Append to "Shape corrections" in `memory/task-rules.md` — the task was right, the
framing was wrong. That's a different lesson from a decline and gets recorded
differently.

## Promotion

```bash
python3 -c "
import sys;sys.path.insert(0,'.claude/lib');import queue as q
print(q.promotion_candidates(q.load()))"
```

Five clean approvals with no edits makes a pattern eligible to be **offered** for
promotion to automatic. Offer it; never self-promote. Anything touching the six
manual actions has no promotion path and is excluded in code, not by memory.

## Proposing something new

```bash
python3 -c "
import sys;sys.path.insert(0,'.claude/lib');import queue as q
d=q.load()
print(q.propose(d,'<kind>','<subject>',<confidence>,detail='<why>',source='<where>')[0])
q.save(d)"
```

Confidence below 0.40 routes to `state/rejected-candidates.md` automatically. Don't
round up to clear the bar — that file is reviewed weekly precisely to find out
whether the bar is set right.
