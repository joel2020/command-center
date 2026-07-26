---
description: 6pm digest — what moved, what ran, what still needs Joel
---

The evening digest. 6pm daily.

## 1. What moved today

Compare against this morning:

- Linear issues that changed status
- Projects in `memory/projects.md` whose last movement is today
- Git commits across the repos named in the project list

## 2. What automation did

```bash
python3 -c "
import sys,json;sys.path.insert(0,'.claude/lib');import feed
a=feed.automation_summary(hours=12)
print(a['total'],'tool calls'); print(json.dumps(a['by_tool'],indent=2))"
```

Ground truth from the PreToolUse hook, not from memory of what happened.

## 3. FYI mail

Roll the day's FYI bucket into a few lines. Not a list of subjects — what actually
happened that Joel would want to know.

## 4. What still needs him

The queue's visible items and anything in `state/needs-me.md`. Same 10-item cap.

## 5. Anything done below 90% confidence

Every one of those should already be in `state/needs-me.md` per CLAUDE.md. If any
aren't, add them now and say so — the point of the rule is that low-confidence
actions get seen, and a rule that's silently skipped is worse than no rule.

## 6. Stamp

```bash
python3 .claude/lib/heartbeat.py evening-digest
```
