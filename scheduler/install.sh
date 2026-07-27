#!/bin/bash
# Installs the Command Center launchd agents.
#
#   scheduler/install.sh            # write the plists, print what to run next
#   scheduler/install.sh --load     # write AND load them
#   scheduler/install.sh --unload   # stop and remove them
#
# Writing plists does nothing on its own. Nothing is scheduled until you load it,
# and `--unload` fully reverses this.
#
# Schedule, per PHASES.md. Times are LOCAL — launchd's StartCalendarInterval uses
# local time, so there is no UTC conversion to get wrong.
#
#   morning-brief    6:00am, Mon–Fri
#   email-triage     hourly
#   evening-digest   6:00pm, daily
#   weekly-review    5:00pm, Sunday
#   backup           9:00pm, daily — git bundles to iCloud Drive

set -euo pipefail

CC="$HOME/command-center"
AGENTS="$HOME/Library/LaunchAgents"
RUNNER="$CC/.claude/bin/run-scheduled.sh"
PREFIX="com.joel.commandcenter"

TASKS=(morning-brief email-triage evening-digest weekly-review backup)

if [ ! -x "$RUNNER" ]; then
  echo "runner is not executable: $RUNNER"
  echo "  chmod +x $RUNNER"
  exit 1
fi

# ── unload ────────────────────────────────────────────────────────────────────
if [ "${1:-}" = "--unload" ]; then
  for t in "${TASKS[@]}"; do
    plist="$AGENTS/$PREFIX.$t.plist"
    launchctl unload "$plist" 2>/dev/null || true
    rm -f "$plist"
    echo "removed $t"
  done
  echo
  echo "All Command Center agents removed. Nothing is scheduled."
  exit 0
fi

mkdir -p "$AGENTS"

# ── plist writers ─────────────────────────────────────────────────────────────
# $1 task name, $2 slash command, $3 the <key>schedule</key> XML fragment
write_plist() {
  local task="$1" cmd="$2" schedule="$3"
  local plist="$AGENTS/$PREFIX.$task.plist"
  cat >"$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$PREFIX.$task</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$RUNNER</string>
    <string>$task</string>
    <string>$cmd</string>
  </array>
$schedule
  <key>WorkingDirectory</key><string>$CC</string>
  <key>StandardOutPath</key><string>$CC/state/runs/launchd-$task.out</string>
  <key>StandardErrorPath</key><string>$CC/state/runs/launchd-$task.err</string>
  <key>ProcessType</key><string>Background</string>
  <key>LowPriorityIO</key><true/>
  <key>Nice</key><integer>5</integer>
</dict>
</plist>
PLIST
  echo "wrote $plist"
}

mkdir -p "$CC/state/runs"

# 6:00am Mon–Fri. launchd Weekday: 1=Mon … 5=Fri.
write_plist morning-brief /morning-brief "$(cat <<'X'
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>6</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>2</integer><key>Hour</key><integer>6</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>3</integer><key>Hour</key><integer>6</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>4</integer><key>Hour</key><integer>6</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>5</integer><key>Hour</key><integer>6</integer><key>Minute</key><integer>0</integer></dict>
  </array>
X
)"

# Hourly. PHASES.md is explicit: hourly, not every 30 minutes — "the extra
# frequency costs tokens and buys nothing."
write_plist email-triage /triage "$(cat <<'X'
  <key>StartInterval</key><integer>3600</integer>
X
)"

write_plist evening-digest /evening-digest "$(cat <<'X'
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
X
)"

# Sunday 5:00pm. launchd Weekday: 0 = Sunday.
write_plist weekly-review /weekly-review "$(cat <<'X'
  <key>StartCalendarInterval</key>
  <dict><key>Weekday</key><integer>0</integer><key>Hour</key><integer>17</integer><key>Minute</key><integer>0</integer></dict>
X
)"

# ── load ──────────────────────────────────────────────────────────────────────
echo
if [ "${1:-}" = "--load" ]; then
  for t in "${TASKS[@]}"; do
    plist="$AGENTS/$PREFIX.$t.plist"
    launchctl unload "$plist" 2>/dev/null || true
    launchctl load "$plist"
    echo "loaded $t"
  done
  echo
  echo "Scheduled. Check status with:"
  echo "  launchctl list | grep $PREFIX"
  echo "  python3 $CC/.claude/lib/runs.py health"
else
  echo "Plists written but NOT loaded. Nothing is scheduled yet."
  echo
  echo "To start the schedule:"
  echo "  scheduler/install.sh --load"
  echo
  echo "To test one task right now, without waiting:"
  echo "  .claude/bin/run-scheduled.sh email-triage /triage"
  echo
  echo "To remove everything:"
  echo "  scheduler/install.sh --unload"
fi

echo
echo "Note: launchd does not run agents while the Mac is asleep. A missed"
echo "StartCalendarInterval fires once on wake; StartInterval resumes on its"
echo "normal cadence. The heartbeat will show the gap either way."
