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

# The task's own definition of "I finished" is stamping the heartbeat, which is
# the last step of every scheduled command. Capture it before and after.
#
# `claude -p` exits 0 for a session that accomplished nothing — a run on
# 2026-07-26 had Bash and every MCP connector denied, produced no refresh, no
# build and no stamp, and was still recorded ok=true. That is exactly the
# failure runs.py exists to catch ("a task can run every hour and fail every
# time"), one level up. Trusting the exit code alone makes run health a lie.
read_stamp() {
  /usr/bin/python3 - "$TASK" <<'PY' 2>/dev/null || echo ""
import json, os, sys
p = os.path.expanduser("~/command-center/state/heartbeat.json")
try:
    with open(p) as f:
        print(json.load(f)["tasks"][sys.argv[1]]["last_run"] or "")
except Exception:
    print("")
PY
}

BEFORE=$(read_stamp)

echo "=== $(date -Iseconds) $TASK ($CMD) ===" >>"$LOG"
# --max-turns bounds a runaway session. Scheduled work is meant to be short;
# anything needing more turns than this should be surfaced, not ground through.
claude -p "$CMD" --max-turns 40 >>"$LOG" 2>&1
STATUS=$?
echo "=== exit=$STATUS ===" >>"$LOG"

AFTER=$(read_stamp)

END=$(date +%s)

NOTE=""
if [ "$STATUS" -eq 0 ] && [ "$BEFORE" = "$AFTER" ]; then
  # Clean exit, but the task never stamped itself. Treat as a failure so two in
  # a row escalate, rather than reporting a healthy task that does nothing.
  STATUS=64
  NOTE="exited 0 but never stamped the heartbeat — did the work actually run?"
  echo "=== heartbeat not advanced: recording as failure ===" >>"$LOG"
fi

/usr/bin/python3 "$CC/.claude/lib/runs.py" record "$TASK" "$STATUS" \
  --duration "$((END - START))" ${NOTE:+--note "$NOTE"} >>"$LOG" 2>&1

# Keep the log directory bounded. CLAUDE.md lists pruning as automatic.
find "$LOGDIR" -name '*.log' -mtime +30 -delete 2>/dev/null
/usr/bin/python3 "$CC/.claude/lib/runs.py" prune --keep-days 90 >>"$LOG" 2>&1

exit 0
