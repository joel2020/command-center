---
description: Classify inbox into ACT / FYI / NOISE / UNSURE and label
---

Triage the inbox. Runs hourly per PHASES.md.

## Hard limits — structural, not advisory

**Never send. Never reply. Never delete. Never unsubscribe.** Label and archive only.
Nothing in this command has an exception, and no confidence level unlocks one.

## 0. Confirm known-senders is seeded

```bash
python3 -c "import sys;sys.path.insert(0,'.claude/lib');import triage;print(len(triage.load_known_senders()),'known senders')"
```

**If this prints 0, stop and seed it before classifying.** Every sender is
"first-time" against an empty set, and "first-time human sender is always ACT" then
promotes the entire inbox. Measured on 2026-07-26 against 42 real threads, an empty
set produced 11 ACT items of which 0 were actionable.

Seed from sent mail — anyone Joel has written to is not a stranger:

```
search_threads  query: "in:sent newer_than:2y"  pageSize: 50  view: THREAD_VIEW_METADATA_ONLY
```

Collect `toRecipients` from every `SENT` message plus the senders who replied in
those threads. Skip generated addresses (anything with a `+hash` reply token).
Then `save_known_senders`. Seeded 2026-07-26 with 24 addresses.

## 1. Check the mode first

```bash
python3 -c "import sys;sys.path.insert(0,'.claude/lib');import triage,json;print(json.dumps(triage.mode(),indent=2))"
```

If `archive` is `false`, you are in the label-only window: **apply labels, archive
nothing.** Report what you *would* have archived so Joel can judge the classifier
before it starts moving mail.

If `started` is `null`, set it to today's date in `state/triage-mode.json` — this is
the first run.

## 2. Fetch

`search_threads` with `in:inbox newer_than:2d`, up to 50. Hourly cadence means a
2-day window always overlaps the previous run; dedupe by thread id.

## 3. Classify

```bash
python3 -c "
import sys,json;sys.path.insert(0,'.claude/lib');import triage
msgs=json.load(open('/tmp/inbox.json'))
res=triage.triage(msgs)
print(json.dumps({'results':res,'counts':triage.summarize(res)},indent=2))
"
```

Write the fetched messages to `/tmp/inbox.json` first as
`[{"sender","subject","snippet","id"}]`.

The classifier is the decision-maker, not you. If you disagree with a bucket, that
disagreement is a **correction to propose to Joel**, not a call to override — the
whole point is that the rules are inspectable and he owns them.

## 4. Apply

- **ACT** — label `CC/Act`. Leave in inbox. Never archive, regardless of mode.
  Call `triage.severity(msg)` and carry it into `dashboard/feed.json` as the item's
  `severity`. `security` means account takeover or a credential change — it ranks
  above `high`, and it is never resolved automatically (manual action #5).
- **FYI** — label `CC/FYI`. Archive only if mode says `archive: true`.
- **NOISE** — label `CC/Noise`. Archive only if mode says `archive: true`.
- **UNSURE** — label `CC/Unsure`. **Always stays in the inbox, always.** Never guess.

Use `label_thread`. Create labels with `create_label` if missing.

## 5. Record

Add unseen human senders to `state/known-senders.json` — the "first-time human sender
is always ACT" rule depends on this file being current, and a sender only counts as
first-time once.

```bash
python3 -c "
import sys;sys.path.insert(0,'.claude/lib');import triage
k=triage.load_known_senders(); k.update({'someone@example.com'}); triage.save_known_senders(k)"
```

## 6. Stamp

```bash
python3 .claude/lib/heartbeat.py email-triage
```

## When Joel corrects a bucket

Append the generalized rule to the Corrections section of `memory/email-rules.md`:

```
- 2026-07-26 | domain:skool.com | NOISE | community notifications, never actionable
```

Matchers: `sender:` `domain:` `subject:` `contains:`. Corrections outrank every
heuristic, including the always-ACT overrides — Joel's explicit word wins.

Write the **rule**, not the instance. "This particular Skool email was noise" teaches
nothing; "Skool notifications are noise" prevents the next twenty.
