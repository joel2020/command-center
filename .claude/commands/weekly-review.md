---
description: Sunday 5pm — success metrics, expired items, promotion candidates
---

The Sunday review. This is where the system is judged, not just run.

## 1. The five success metrics

Report all five every week, per PHASES.md. Say the number even when it's bad —
especially when it's bad.

**1. Of NEEDS ME items, what % did Joel act on?**
```bash
python3 -c "
import sys,json;sys.path.insert(0,'.claude/lib');import outcomes
print(json.dumps(outcomes.needs_me_metrics(days=7), indent=2))"
```
Below 50% means over-surfacing. The fix is a higher bar, not a longer list.

`clear_rate` is **resolution, not proof of action** — an item stops being surfaced
when its underlying condition changes. Report it as what it is. If `clear_rate` is
`null` there was no data this week; say that instead of reporting zero, because a
rate of zero means "you ignored everything" and an empty week does not.

Then walk the open list with Joel and record real verdicts, which outrank the
inferred ones:
```bash
python3 -c "
import sys;sys.path.insert(0,'.claude/lib');import outcomes
for r in outcomes.open_items(): print(r['key'], '|', r['ts'][:10], '|', r['text'][:70])"
```
```bash
python3 -c "
import sys;sys.path.insert(0,'.claude/lib');import outcomes
outcomes.mark('<key>', 'acted')"   # acted | ignored | not-mine
```

**2. Of NOISE/FYI items, how many did Joel later dig out of the archive?**

`/triage` records what it archives. Ask Gmail what came back — anything labeled by
triage that is now starred, unread-again, or back in the inbox:
```
search_threads  query: "(label:CC/Noise OR label:CC/FYI) (in:inbox OR is:starred)"
```
Feed the thread ids back in, then read the metric:
```bash
python3 -c "
import sys,json;sys.path.insert(0,'.claude/lib');import outcomes
outcomes.record_recovered(['<thread-id>'])
print(json.dumps(outcomes.archive_recovery_metrics(days=7), indent=2))"
```
Above zero is a miss. Each one is a correction owed to `memory/email-rules.md` —
and each is also a candidate for the fixture in
`.claude/lib/tests/fixtures/`, so the same mistake fails a test next time.

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
import sys,json,datetime;sys.path.insert(0,'.claude/lib')
import projects,feed,movement
ps=projects.load(feed.PROJECTS_MD)
fd=feed.load_feed(); issues=(fd.get('data',{}).get('linear') or {}).get('issues',[])
mv=movement.derive_all(ps,issues)
for p in ps:
    if p.section!='Active': continue
    d=p.to_dict(movement=mv.get(p.name))
    if d['stale']: print(f\"{d['name']} — {d['days_stale']}d ({d['movement_source']})\")"
```
Check the source on each. `declared` means the date is Joel's note with nothing
corroborating it, so the staleness may be bookkeeping rather than reality — those
are worth asking about directly. `confirmed by` or `observed via` means a repo or
tracker agrees, and the project really has not moved.

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
