---
description: Sunday 5pm — success metrics, expired items, promotion candidates
---

The Sunday review. This is where the system is judged, not just run.

## 1. The five success metrics

Report all five every week, per PHASES.md. Say the number even when it's bad —
especially when it's bad.

**1. Of NEEDS ME items, what % did Joel act on?**
Below 50% means over-surfacing. The fix is a higher bar, not a longer list.

**2. Of NOISE/FYI items, how many did Joel later dig out of the archive?**
Above zero is a miss. Each one is a correction owed to `memory/email-rules.md`.

**3. Queue: approved vs declined vs expired.**
```bash
python3 -c "
import sys,json;sys.path.insert(0,'.claude/lib');import queue as q
print(json.dumps(q.metrics(q.load(), days=7), indent=2))"
```
High declines mean the wrong things are being proposed. That's a problem with the
proposer, not with Joel.

**4. Projects stale 7+ days.**
```bash
python3 -c "
import sys;sys.path.insert(0,'.claude/lib');import projects,feed
for p in projects.load(feed.PROJECTS_MD):
    if p.section=='Active' and p.is_stale(): print(p.name, p.days_stale(),'days')"
```

**5. Push notifications sent, and how many were justified in hindsight.**
```bash
python3 -c "
import sys,json;sys.path.insert(0,'.claude/lib');import push
print(json.dumps(push.sms_budget(), indent=2))"
```
If the SMS cap was hit, say plainly that the threshold is wrong.

## 2. Expired items

```bash
python3 -c "
import sys;sys.path.insert(0,'.claude/lib');import queue as q
d=q.load()
for i in q.expire(d): print(i['id'], i['kind'], i['subject'])
q.save(d)"
```

Anything auto-declined after 7 days unreviewed. Surface every one — a silent
auto-decline is indistinguishable from the system losing things.

## 3. Rejected candidates

Read `state/rejected-candidates.md`. **If good ideas keep landing there, the 40%
threshold is wrong** — say so and propose a number.

## 4. Promotion candidates

```bash
python3 -c "
import sys;sys.path.insert(0,'.claude/lib');import queue as q
print(q.promotion_candidates(q.load()))"
```

Offer them. Never self-promote. Nothing touching the six manual actions is eligible,
ever, regardless of how many clean approvals it has.

## 5. Memory hygiene

Did every correction from this week get written down? A correction that isn't in
`memory/` will be repeated. Check `email-rules.md`, `task-rules.md`, `about-me.md`,
and `projects.md` against what actually happened this week.

## 6. Stamp

```bash
python3 .claude/lib/heartbeat.py weekly-review
```
