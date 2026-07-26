#!/bin/bash
# PreToolUse — observes every tool call, never blocks.
# Writes one JSON line per call to state/automation-log.jsonl.
# NEVER writes to stdout: stdout would pollute Claude's context.
LOG="$HOME/command-center/state/automation-log.jsonl"
mkdir -p "$(dirname "$LOG")"
python3 "$HOME/command-center/.claude/hooks/_log.py" "$LOG" 2>/dev/null
exit 0
