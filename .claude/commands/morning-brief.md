---
description: 6am weekday briefing — refresh, brief, push if warranted
---

The morning briefing. 6am weekdays.

## 1. Refresh

Run `/dashboard` steps 1–3: collect connectors into `dashboard/feed.json`, rebuild,
open.

## 2. Brief, in this order

1. **What's due today** — Linear `dueDate`, anything overdue first
2. **Calendar** — today's blocks, and any conflict (flag it, never resolve it)
3. **Needs me** — top items from the queue, capped at 10
4. **Blocked projects** — from `memory/projects.md`
5. **Overnight** — ACT-bucket mail since yesterday's digest

Keep it short enough to read standing up. Joel's preference is concise and direct;
a briefing he skims is worse than three lines he reads.

## 3. Push only if warranted

```bash
python3 -c "
import sys;sys.path.insert(0,'.claude/lib');import push
print(push.should_notify_deadline(<hours_until>))
print(push.should_notify_task_failure(<consecutive>))
"
```

macOS notification fires when a predicate returns True — an ACT deadline inside 4
hours, a scheduled task that failed twice consecutively, or a time-sensitive queue
item about to expire.

```bash
python3 -c "
import sys;sys.path.insert(0,'.claude/lib');import push
push.notify('Command Center','<message>')"
```

SMS is a different bar entirely: money or legal with a same-day deadline, a client
explicitly escalating, or consequences that outlast today. If unsure, it isn't.

## 4. Stamp

```bash
python3 .claude/lib/heartbeat.py morning-brief
```

A run that doesn't stamp didn't happen.
