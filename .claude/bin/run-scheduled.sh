#!/bin/bash
# Runs one Command Center scheduled task headlessly, under launchd.
#
#   .claude/bin/run-scheduled.sh <heartbeat-task-name> <slash-command>
#   .claude/bin/run-scheduled.sh email-triage /triage
#
# launchd provides almost no environment, so PATH is set explicitly.
#
# Always exits 0. A failed task is recorded and escalated by runs.py; letting
# launchd see a non-zero exit would make it retry blindly, which is worse than
# recording the failure and waiting for the next scheduled slot.

set -uo pipefail

TASK="${1:?usage: run-scheduled.sh <task> <slash-command>}"
CMD="${2:?usage: run-scheduled.sh <task> <slash-command>}"

CC="$HOME/command-center"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

LOGDIR="$CC/state/runs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/${TASK}-$(date +%Y-%m-%d).log"

cd "$CC" || exit 0

if ! command -v claude >/dev/null 2>&1; then
  echo "$(date -Iseconds) claude CLI not on PATH" >>"$LOG"
  /usr/bin/python3 "$CC/.claude/lib/runs.py" record "$TASK" 127 \
    --note "claude not found on PATH" >>"$LOG" 2>&1
  exit 0
fi

START=$(date +%s)

echo "=== $(date -Iseconds) $TASK ($CMD) ===" >>"$LOG"
# --max-turns bounds a runaway session. Scheduled work is meant to be short;
# anything needing more turns than this should be surfaced, not ground through.
claude -p "$CMD" --max-turns 40 >>"$LOG" 2>&1
STATUS=$?
echo "=== exit=$STATUS ===" >>"$LOG"

END=$(date +%s)

/usr/bin/python3 "$CC/.claude/lib/runs.py" record "$TASK" "$STATUS" \
  --duration "$((END - START))" >>"$LOG" 2>&1

# Keep the log directory bounded. CLAUDE.md lists pruning as automatic.
find "$LOGDIR" -name '*.log' -mtime +30 -delete 2>/dev/null
/usr/bin/python3 "$CC/.claude/lib/runs.py" prune --keep-days 90 >>"$LOG" 2>&1

exit 0
