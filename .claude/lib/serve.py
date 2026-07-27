"""The cockpit server. Live state, lifecycle control, and the butler.

    python3 .claude/lib/serve.py            # http://127.0.0.1:7777
    python3 .claude/lib/serve.py --port N

Standard library only. This repo has no dependencies and should not gain any.

SECURITY. Everything before this was an inert HTML file. This can kill processes
and spawn agents, so it needs a real threat model rather than a convention:

  * Binds 127.0.0.1 ONLY, never 0.0.0.0. Asserted in a test, because that single
    character is the difference between a personal cockpit and process control
    exposed to the local network.
  * A token is required on every API route. Without it, ANY website open in
    Joel's browser could fetch('http://localhost:7777/api/control') and stop his
    agents — the same-origin policy does not stop the request being sent, only
    the reading of the reply, and a stop does not need a reply. The token is
    generated on first run into state/server-token, mode 600, gitignored.
  * GET / is unauthenticated because it must be: the page is where the token
    comes from. It serves markup only, no state.
  * Every control action is appended to state/control-log.jsonl.
  * Stop is SIGTERM, never SIGKILL.

The six manual actions are untouched. Dispatching an agent does not grant it
permission to send, delete, or spend — those gates live in the dispatched
agent's own settings and nothing here reaches into them.
"""

import argparse
import datetime
import json
import os
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agents as agentsmod       # noqa: E402
import build_dashboard           # noqa: E402
import control as controlmod     # noqa: E402
import projects as projectsmod   # noqa: E402
import feed as feedmod           # noqa: E402
import voice as voicemod         # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOKEN_FILE = os.path.join(ROOT, "state", "server-token")
PAGE = os.path.join(ROOT, "dashboard", "index.html")

HOST = "127.0.0.1"          # never 0.0.0.0
PORT = 7777
MAX_BODY = 64 * 1024


def get_token(path=None):
    """Read or mint the shared token. 600, gitignored."""
    path = path or TOKEN_FILE
    if os.path.exists(path):
        with open(path) as f:
            t = f.read().strip()
        if t:
            return t
    os.makedirs(os.path.dirname(path), exist_ok=True)
    t = secrets.token_urlsafe(32)
    with open(path, "w") as f:
        f.write(t + "\n")
    os.chmod(path, 0o600)
    return t


def state(now=None):
    """Everything the cockpit renders. One code path with the static build, so
    the live view and a rebuilt index.html can never disagree.

    No single reader may take down the page. A launchd-started server has fewer
    permissions than the same code run from a terminal — an unguarded listdir on
    iCloud Drive raised PermissionError here and 500'd the whole endpoint, so
    the cockpit read NOT LIVE while every other section was perfectly readable.
    Each part now degrades on its own and says so, which is the same rule the
    page itself runs on.
    """
    now = now or datetime.datetime.now().astimezone()
    errors = []

    try:
        data, _ = build_dashboard.build(want_calendar=False, out=os.devnull,
                                        now=now)
    except Exception as e:                                   # noqa: BLE001
        # Without the build there is no page, so this one is fatal — but it
        # returns a shaped, honest payload rather than an HTTP 500 the front
        # end can only render as "unreachable".
        return {"server": {"live": True, "degraded": True,
                           "generated_at": now.isoformat()},
                "fatal": f"build failed: {e}",
                "agents": {"available": False, "reason": f"build failed: {e}",
                           "items": [], "busy": 0},
                "projects": {"available": False, "reason": str(e), "items": []}}

    try:
        plist = projectsmod.load(feedmod.PROJECTS_MD)
        snap = agentsmod.snapshot(projects=plist, now=now)
    except Exception as e:                                   # noqa: BLE001
        errors.append(f"agents: {e}")
        snap = {"available": False, "reason": str(e), "items": [], "busy": 0}

    try:
        q = controlmod.pending_counts()
    except Exception as e:                                   # noqa: BLE001
        errors.append(f"inbox: {e}")
        q = {}

    for a in snap.get("items", []):
        a["queued_messages"] = q.get(a["session_id"], 0)

    try:
        log = controlmod.read_log(limit=20)
    except Exception as e:                                   # noqa: BLE001
        errors.append(f"control log: {e}")
        log = []

    data["agents"] = snap
    data["control_log"] = log
    data["queued_total"] = sum(q.values())
    data["server"] = {"live": True, "degraded": bool(errors),
                      "errors": errors, "generated_at": now.isoformat()}
    return data


class Handler(BaseHTTPRequestHandler):
    server_version = "CommandCenter/1.0"
    token = None

    def log_message(self, *a):
        pass                      # the control log is the record that matters

    # ── helpers ──────────────────────────────────────────────────────────
    def _send(self, code, payload, ctype="application/json"):
        body = payload if isinstance(payload, bytes) else \
            json.dumps(payload, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # This page must never be embedded or read by another origin.
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _authed(self):
        got = self.headers.get("X-CC-Token") or ""
        want = self.token or ""
        # Constant-time so the token cannot be recovered by timing.
        return bool(want) and secrets.compare_digest(got, want)

    def _deny(self):
        self._send(403, {"ok": False,
                         "error": "missing or bad X-CC-Token",
                         "hint": "the page injects it; open http://127.0.0.1:7777/"})

    # ── routes ───────────────────────────────────────────────────────────
    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/":
            # Unauthenticated by necessity: this is where the token comes from.
            if not os.path.exists(PAGE):
                return self._send(404, {"error": "dashboard/index.html not built — "
                                                 "run build_dashboard.py"},
                                  "text/plain")
            with open(PAGE, "rb") as f:
                html = f.read().decode("utf-8", "replace")
            inject = (f'<script>window.CC_TOKEN={json.dumps(self.token)};'
                      f'window.CC_LIVE=true;</script>')
            html = html.replace("</head>", inject + "</head>", 1)
            return self._send(200, html.encode(), "text/html; charset=utf-8")

        if path == "/api/health":
            return self._send(200, {"ok": True, "live": True})

        if not self._authed():
            return self._deny()

        if path == "/api/state":
            # Deliver anything queued for agents that have gone idle. Cheap when
            # the inbox is empty, which is almost always.
            try:
                controlmod.flush_inbox()
            except Exception as e:                       # noqa: BLE001
                pass
            return self._send(200, state())

        if path.startswith("/api/audio/"):
            h = os.path.basename(path)
            p = os.path.join(voicemod.CACHE, h)
            if not os.path.isfile(p) or not h.endswith(".mp3"):
                return self._send(404, {"error": "no such audio"})
            with open(p, "rb") as f:
                return self._send(200, f.read(), "audio/mpeg")

        return self._send(404, {"error": "no such route"})

    def do_POST(self):
        path = self.path.split("?")[0]
        if not self._authed():
            return self._deny()

        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n > MAX_BODY:
            return self._send(413, {"ok": False, "error": "body too large"})
        raw = self.rfile.read(n) if n else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"ok": False, "error": "body is not JSON"})

        if path == "/api/control":
            verb = body.get("verb")
            target = body.get("target")
            message = body.get("message", "")
            if verb not in controlmod.VERBS:
                return self._send(400, {"ok": False,
                                        "error": f"verb must be one of {controlmod.VERBS}"})
            if not target:
                return self._send(400, {"ok": False, "error": "target is required"})
            try:
                return self._send(200, controlmod.apply(verb, target, message))
            except Exception as e:                        # noqa: BLE001
                return self._send(500, {"ok": False, "error": str(e)})

        if path == "/api/speak":
            text = (body.get("text") or "").strip()
            if not text:
                return self._send(400, {"ok": False, "error": "text is required"})
            r = voicemod.speak(text, body.get("trigger", "on_demand"))
            if r.get("ok") and r.get("path"):
                r["url"] = "/api/audio/" + os.path.basename(r["path"])
            return self._send(200, r)

        return self._send(404, {"ok": False, "error": "no such route"})


def serve(host=HOST, port=PORT, token=None):
    Handler.token = token or get_token()
    httpd = ThreadingHTTPServer((host, port), Handler)
    return httpd


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--print-token", action="store_true")
    a = ap.parse_args(argv)

    token = get_token()
    if a.print_token:
        print(token)
        return 0

    httpd = serve(HOST, a.port, token)
    print(f"cockpit  http://{HOST}:{a.port}/")
    print(f"  bound to {HOST} only — not reachable from the network")
    print(f"  token in state/server-token (600); every API route requires it")
    print(f"  control actions log to state/control-log.jsonl")
    print("  ctrl-c to stop")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
