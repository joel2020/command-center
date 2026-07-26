import sys, json, datetime
log = sys.argv[1]
try:
    d = json.loads(sys.stdin.read())
except Exception:
    d = {}
tool = d.get("tool_name", "unknown")
ti = d.get("tool_input", {}) or {}
target = (ti.get("file_path") or ti.get("path") or ti.get("url")
          or ti.get("to") or ti.get("recipient") or ti.get("command") or "")
if isinstance(target, (dict, list)):
    target = json.dumps(target)
target = str(target)[:300]
undo = {
    "Write": "git checkout -- <path>, or restore from git history",
    "Edit": "git checkout -- <path>, or restore from git history",
    "NotebookEdit": "git checkout -- <path>",
    "Bash": "review command; no automatic undo",
}.get(tool, "")
rec = {
    "ts": datetime.datetime.now().astimezone().isoformat(),
    "tool": tool,
    "target": target,
    "session": d.get("session_id", ""),
    "undo": undo,
}
with open(log, "a") as f:
    f.write(json.dumps(rec) + "\n")
