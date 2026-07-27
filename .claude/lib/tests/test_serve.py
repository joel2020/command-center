"""The cockpit server. Mostly a security test.

Everything before this was an inert HTML file. This one kills processes and
spawns agents, so the properties worth asserting are the ones that stop it
being a remote-control hole:

  * it binds loopback and nothing else
  * no API route answers without the token
  * the token is unguessable and not world-readable

The bind address in particular is one character away from exposing process
control to every device on the network, which is exactly the kind of thing that
gets changed during debugging and never changed back.
"""

import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import serve  # noqa: E402

PORT = 7791          # not the default, so a running cockpit is untouched
BASE = f"http://127.0.0.1:{PORT}"
TOKEN = "test-token-do-not-use"


def request(path, token=None, method="GET", body=None):
    req = urllib.request.Request(BASE + path, method=method,
                                 data=json.dumps(body).encode() if body else None)
    if token:
        req.add_header("X-CC-Token", token)
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except json.JSONDecodeError:
            return e.code, {}


class ServerTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.httpd = serve.serve("127.0.0.1", PORT, TOKEN)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()


class TestBinding(ServerTest):

    def test_binds_loopback_only(self):
        """One character from exposing process control to the LAN."""
        self.assertEqual(self.httpd.server_address[0], "127.0.0.1")

    def test_default_host_constant_is_loopback(self):
        self.assertEqual(serve.HOST, "127.0.0.1")
        self.assertNotEqual(serve.HOST, "0.0.0.0")


class TestAuth(ServerTest):

    def test_health_needs_no_token(self):
        code, body = request("/api/health")
        self.assertEqual(code, 200)
        self.assertTrue(body["ok"])

    def test_state_without_a_token_is_refused(self):
        code, _ = request("/api/state")
        self.assertEqual(code, 403)

    def test_state_with_a_wrong_token_is_refused(self):
        code, _ = request("/api/state", token="wrong")
        self.assertEqual(code, 403)

    def test_control_without_a_token_is_refused(self):
        """The attack this stops: any site open in the browser POSTing here.
        The same-origin policy does not prevent the request being sent, and a
        stop does not need a readable reply."""
        code, _ = request("/api/control", method="POST",
                          body={"verb": "stop", "target": "x"})
        self.assertEqual(code, 403)

    def test_speak_without_a_token_is_refused(self):
        code, _ = request("/api/speak", method="POST", body={"text": "hi"})
        self.assertEqual(code, 403)

    def test_state_with_the_token_works(self):
        code, body = request("/api/state", token=TOKEN)
        self.assertEqual(code, 200)
        for key in ("agents", "projects", "risk", "server"):
            self.assertIn(key, body)


class TestControlRoute(ServerTest):

    def test_unknown_verb_is_rejected_before_anything_happens(self):
        code, body = request("/api/control", token=TOKEN, method="POST",
                             body={"verb": "rm", "target": "x"})
        self.assertEqual(code, 400)
        self.assertIn("verb must be one of", body["error"])

    def test_missing_target_is_rejected(self):
        code, body = request("/api/control", token=TOKEN, method="POST",
                             body={"verb": "stop"})
        self.assertEqual(code, 400)

    def test_malformed_json_is_rejected(self):
        req = urllib.request.Request(BASE + "/api/control", method="POST",
                                     data=b"{not json")
        req.add_header("X-CC-Token", TOKEN)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                code = r.status
        except urllib.error.HTTPError as e:
            code = e.code
        self.assertEqual(code, 400)

    def test_stopping_a_nonexistent_session_fails_without_raising(self):
        code, body = request("/api/control", token=TOKEN, method="POST",
                             body={"verb": "stop", "target": "no-such-session"})
        self.assertEqual(code, 200)
        self.assertFalse(body["ok"])


class TestHeaders(ServerTest):

    def test_page_cannot_be_framed_or_sniffed(self):
        req = urllib.request.Request(BASE + "/api/health")
        with urllib.request.urlopen(req, timeout=10) as r:
            self.assertEqual(r.headers.get("X-Frame-Options"), "DENY")
            self.assertEqual(r.headers.get("X-Content-Type-Options"), "nosniff")
            self.assertEqual(r.headers.get("Cache-Control"), "no-store")


class TestToken(unittest.TestCase):

    def test_generated_token_is_long_and_random(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "token")
            t1 = serve.get_token(p)
            self.assertGreaterEqual(len(t1), 32)
            self.assertEqual(serve.get_token(p), t1, "must be stable across reads")

    def test_token_file_is_not_world_readable(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "token")
            serve.get_token(p)
            self.assertEqual(os.stat(p).st_mode & 0o077, 0,
                             "the token must not be readable by other users")

    def test_two_directories_get_different_tokens(self):
        import tempfile
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            self.assertNotEqual(serve.get_token(os.path.join(a, "t")),
                                serve.get_token(os.path.join(b, "t")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
