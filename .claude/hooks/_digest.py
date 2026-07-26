import os, json, datetime, pathlib
CC = pathlib.Path(os.path.expanduser("~/command-center"))
out = []

def head(p, n):
    """First n non-empty lines, with HTML comment BLOCKS stripped (not just opening lines)."""
    f = CC / p
    if not f.exists():
        return []
    import re
    text = re.sub(r"<!--.*?-->", "", f.read_text(), flags=re.DOTALL)
    body = [l.rstrip() for l in text.splitlines() if l.strip()]
    return body[:n]

out.append("=== COMMAND CENTER CONTEXT (auto-loaded) ===")

for label, path, n in [
    ("ABOUT ME",   "memory/about-me.md",   12),
    ("PROJECTS",   "memory/projects.md",   14),
    ("TASK RULES", "memory/task-rules.md", 12),
]:
    lines = head(path, n)
    if lines:
        out.append(f"\n--- {label} ---")
        out.extend(lines)
    else:
        out.append(f"\n--- {label} --- (empty; populate {path})")

# Heartbeat: surface any scheduled task that missed its window
hb = CC / "state/heartbeat.json"
misses = []
if hb.exists():
    try:
        data = json.loads(hb.read_text())
        now = datetime.datetime.now().astimezone()
        for task, meta in (data.get("tasks") or {}).items():
            last = meta.get("last_run")
            maxage = meta.get("max_age_hours", 24)
            if not last:
                misses.append(f"{task}: never run")
                continue
            age = (now - datetime.datetime.fromisoformat(last)).total_seconds() / 3600
            if age > maxage:
                misses.append(f"{task}: {age:.0f}h since last run (limit {maxage}h)")
    except Exception as e:
        misses.append(f"heartbeat.json unreadable: {e}")

out.append("\n--- SCHEDULED TASK HEALTH ---")
out.extend([f"!! {m}" for m in misses] if misses else ["all tasks within window"])

out.append("\nSix actions are NEVER automatic. See CLAUDE.md.")
print("\n".join(out))
