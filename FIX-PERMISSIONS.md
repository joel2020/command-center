# The one fix Command Center still needs

**Two minutes. It is the difference between the automation being real and being
theatre.**

## What is wrong

`.claude/settings.json` has `defaultMode: "auto"` and an **empty** `allow` list.
That is *more* restrictive than having no settings file at all — every scheduled
run has Bash and file writes denied.

The workspace is already trusted (`hasTrustDialogAccepted: true`), so that is not
the issue. It is purely the empty allow list.

## The evidence

13 hours of unattended running, every run correctly reporting failure:

```
21:19 → 09:30   email-triage × 10    exit=64   never stamped the heartbeat
06:01           morning-brief        exit=64   never stamped the heartbeat
                                     escalated: 2 consecutive failures
```

Nothing is broken about the detection — that is the runner doing its job. The
work simply cannot run.

## The fix

Replace `.claude/settings.json` with this. It keeps every existing deny rule and
adds only what the four scheduled commands actually need.

```json
{
  "permissions": {
    "defaultMode": "auto",
    "allow": [
      "Bash(python3 .claude/lib/*)",
      "Bash(python3 -c *)",
      "Bash(open dashboard/index.html)",
      "Bash(launchctl list*)",
      "Read",
      "Edit(state/*)",
      "Edit(dashboard/*)",
      "Edit(memory/*)",
      "mcp__claude_ai_Gmail__search_threads",
      "mcp__claude_ai_Gmail__get_thread",
      "mcp__claude_ai_Gmail__get_message",
      "mcp__claude_ai_Gmail__list_labels",
      "mcp__claude_ai_Gmail__create_label",
      "mcp__claude_ai_Gmail__label_thread",
      "mcp__claude_ai_Gmail__label_message",
      "mcp__claude_ai_Gmail__unlabel_thread",
      "mcp__claude_ai_Gmail__unlabel_message",
      "mcp__claude_ai_Linear__list_issues",
      "mcp__claude_ai_Linear__get_issue",
      "mcp__claude_ai_Linear__list_projects",
      "mcp__claude_ai_Granola__list_meetings",
      "mcp__claude_ai_Granola__get_meetings"
    ],
    "deny": [
      "Bash(rm -rf *)",
      "Bash(sudo *)",
      "Bash(git push --force*)",
      "mcp__claude_ai_Gmail__create_draft",
      "mcp__claude_ai_Gmail__update_draft",
      "mcp__claude_ai_Gmail__delete_label",
      "mcp__whatsapp__whatsapp_send_message",
      "mcp__whatsapp__whatsapp_send_media"
    ]
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          { "type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/pretooluse.sh" }
        ]
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          { "type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/sessionstart.sh" }
        ]
      }
    ]
  }
}
```

## Why an agent cannot apply this for you

Writing a permission allow list is itself a permission escalation, and the
auto-mode classifier refuses it — correctly. An assistant that could grant itself
Gmail access by editing a config file would make the whole permission system
decorative. This one is by hand, deliberately.

## Note on the deny list

The five new deny rules make `memory/email-rules.md`'s "never send, never delete"
structural rather than an instruction. Triage labels and archives; it has no path
to send a draft or delete a label, and now cannot acquire one by mistake.

## Verifying it worked

```bash
bash .claude/bin/run-scheduled.sh morning-brief /morning-brief
tail -1 state/run-log.jsonl        # want ok=true, not exit 64
python3 .claude/lib/heartbeat.py --status
```

`exit=64` means the session ran and never stamped the heartbeat — still blocked.
`ok=true` means it is finally doing the work.
