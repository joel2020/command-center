#!/bin/bash
# SessionStart — loads persistent memory into context.
# stdout IS the payload here: everything printed enters Claude's context.
# Keep it under ~50 lines; this runs every session and costs tokens each time.
CC="$HOME/command-center"
python3 "$CC/.claude/hooks/_digest.py" 2>/dev/null
exit 0
