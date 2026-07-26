# Email Rules

<!-- Triage corrections. Read before every triage run. -->

## Buckets
- ACT   — a named human waits on something specific, or money/legal/deadline
- FYI   — real information, no action. Label, archive, roll into evening digest.
- NOISE — newsletters, receipts, notifications, marketing. Label, archive silently.
- UNSURE— stays in inbox, flagged. Never guess.

## Always ACT regardless of classifier
- accountant, lawyer, bank
- any first-time human sender

## Hard limits
Never send. Never reply. Never delete. Never unsubscribe. Label and archive only.

## Corrections

<!-- Claude: every time Joel moves something between buckets, write the
     generalized rule here with the date.

     These lines are PARSED by .claude/lib/triage.py, so the format matters:

       - YYYY-MM-DD | <matcher>:<value> | <BUCKET> | <why>

     Matchers:  sender:  exact-ish match on the address
                domain:  matches the sending domain
                subject: substring of the subject
                contains: substring of subject, snippet, or sender

     Corrections outrank every heuristic — including the always-ACT overrides
     above. Joel's explicit word wins over anything the classifier believes.

     Write the RULE, not the instance. "That Skool email was noise" teaches
     nothing. "Skool notifications are noise" prevents the next twenty.

     Lines that don't match the format are ignored, not guessed at — so prose
     notes are safe to leave here alongside real rules.

     Example (not active, remove the leading dot to enable):
     . - 2026-07-26 | domain:skool.com | NOISE | community notifications, never actionable
-->
