"""Lifecycle control: stop, dispatch, resume, and the queue for busy agents.

Nothing here touches a real session. Every test injects a fake killer or
runner, because a test suite that can stop Joel's actual work is worse than no
test suite.
"""

import datetime
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import control  # noqa: E402

LIVE_PID = os.getpid()


class Fake:
    """A throwaway sessions dir plus captured side effects."""

    def __init__(self):
        self.d = tempfile.TemporaryDirectory()
        self.sessions = os.path.join(self.d.name, "sessions")
        os.makedirs(self.sessions)
        self.log = os.path.join(self.d.name, "control-log.jsonl")
        self.inbox = os.path.join(self.d.name, "inbox.jsonl")
        self.killed = []
        self.ran = []

    def session(self, sid, status="idle", cwd="/tmp", name=None, pid=LIVE_PID):
        with open(os.path.join(self.sessions, f"{pid}-{sid}.json"), "w") as f:
            json.dump({"pid": pid, "sessionId": sid, "cwd": cwd,
                       "name": name or sid, "status": status,
                       "startedAt": int(datetime.datetime.now().timestamp() * 1000),
                       "updatedAt": int(datetime.datetime.now().timestamp() * 1000)}, f)
        return self

    def kill(self, pid, sig):
        self.killed.append((pid, sig))

    def run(self, cmd, **kw):
        self.ran.append(cmd)

        class R:
            returncode = 0
            stdout = "ok"
            stderr = ""
        return R()

    def close(self):
        self.d.cleanup()


class TestStop(unittest.TestCase):

    def setUp(self):
        self.f = Fake()

    def tearDown(self):
        self.f.close()

    def test_sends_sigterm_not_sigkill(self):
        """SIGKILL would destroy the transcript. A dashboard button must not."""
        import signal
        self.f.session("s1")
        r = control.stop("s1", self.f.sessions, self.f.log, _kill=self.f.kill)
        self.assertTrue(r["ok"])
        self.assertEqual(self.f.killed, [(LIVE_PID, signal.SIGTERM)])
        self.assertIn("resumable", r["note"])

    def test_unknown_session_fails_cleanly_and_is_logged(self):
        r = control.stop("nope", self.f.sessions, self.f.log, _kill=self.f.kill)
        self.assertFalse(r["ok"])
        self.assertEqual(self.f.killed, [], "must not kill anything")
        self.assertEqual(len(control.read_log(self.f.log)), 1,
                         "a failed action is still a recorded action")

    def test_every_attempt_is_logged(self):
        self.f.session("s1")
        control.stop("s1", self.f.sessions, self.f.log, _kill=self.f.kill)
        control.stop("nope", self.f.sessions, self.f.log, _kill=self.f.kill)
        self.assertEqual(len(control.read_log(self.f.log)), 2)


class TestDispatch(unittest.TestCase):

    def setUp(self):
        self.f = Fake()

    def tearDown(self):
        self.f.close()

    def test_spawns_a_background_agent_in_the_right_directory(self):
        r = control.dispatch(self.f.d.name, "do the thing",
                             self.f.log, _run=self.f.run)
        self.assertTrue(r["ok"])
        self.assertEqual(self.f.ran[0][:3], ["claude", "--bg", "-p"])

    def test_refuses_a_directory_that_does_not_exist(self):
        r = control.dispatch("/nope/nothing", "x", self.f.log, _run=self.f.run)
        self.assertFalse(r["ok"])
        self.assertEqual(self.f.ran, [], "must not spawn into nowhere")


class TestResumeAndSend(unittest.TestCase):

    def setUp(self):
        self.f = Fake()

    def tearDown(self):
        self.f.close()

    def test_resume_delivers_to_an_idle_agent(self):
        self.f.session("s1", status="idle")
        r = control.resume("s1", "hello", self.f.sessions, self.f.log,
                           _run=self.f.run)
        self.assertTrue(r["ok"])
        self.assertIn("--resume", self.f.ran[0])

    def test_resume_refuses_a_busy_agent(self):
        self.f.session("s1", status="busy")
        r = control.resume("s1", "hello", self.f.sessions, self.f.log,
                           _run=self.f.run)
        self.assertFalse(r["ok"])
        self.assertEqual(self.f.ran, [],
                         "resuming a busy session would corrupt work in progress")

    def test_send_to_a_busy_agent_queues_rather_than_failing(self):
        """There is no supported way to interrupt a busy session, so send()
        never fails for being busy — it queues and says so."""
        self.f.session("s1", status="busy")
        r = control.send("s1", "later please", self.f.sessions, self.f.log,
                         self.f.inbox, _run=self.f.run)
        self.assertTrue(r["ok"])
        self.assertTrue(r["queued"])
        self.assertEqual(self.f.ran, [])
        self.assertEqual(len(control.pending("s1", self.f.inbox)), 1)

    def test_send_to_an_idle_agent_delivers_immediately(self):
        self.f.session("s1", status="idle")
        r = control.send("s1", "now", self.f.sessions, self.f.log,
                         self.f.inbox, _run=self.f.run)
        self.assertTrue(r["ok"])
        self.assertFalse(r["queued"])
        self.assertEqual(len(control.pending("s1", self.f.inbox)), 0)

    def test_send_to_an_unknown_agent_fails(self):
        r = control.send("ghost", "x", self.f.sessions, self.f.log,
                         self.f.inbox, _run=self.f.run)
        self.assertFalse(r["ok"])


class TestInbox(unittest.TestCase):

    def setUp(self):
        self.f = Fake()

    def tearDown(self):
        self.f.close()

    def test_queued_message_is_delivered_once_the_agent_goes_idle(self):
        self.f.session("s1", status="busy")
        control.send("s1", "queued msg", self.f.sessions, self.f.log,
                     self.f.inbox, _run=self.f.run)
        # nothing delivers while busy
        self.assertEqual(control.flush_inbox(self.f.sessions, self.f.log,
                                             self.f.inbox, _run=self.f.run), [])
        # agent goes idle
        self.f.session("s1", status="idle")
        out = control.flush_inbox(self.f.sessions, self.f.log, self.f.inbox,
                                  _run=self.f.run)
        self.assertEqual(len(out), 1)
        self.assertIn("--resume", self.f.ran[0])

    def test_a_delivered_message_is_not_delivered_twice(self):
        self.f.session("s1", status="busy")
        control.send("s1", "once", self.f.sessions, self.f.log, self.f.inbox,
                     _run=self.f.run)
        self.f.session("s1", status="idle")
        control.flush_inbox(self.f.sessions, self.f.log, self.f.inbox,
                            _run=self.f.run)
        again = control.flush_inbox(self.f.sessions, self.f.log, self.f.inbox,
                                    _run=self.f.run)
        self.assertEqual(again, [])
        self.assertEqual(control.pending("s1", self.f.inbox), [])

    def test_a_message_for_a_vanished_agent_stays_queued(self):
        """Not dropped. The agent may come back, and silently discarding a
        message Joel typed is the worst possible outcome."""
        self.f.session("s1", status="busy")
        control.send("s1", "hold", self.f.sessions, self.f.log, self.f.inbox,
                     _run=self.f.run)
        os.remove(os.path.join(self.f.sessions, f"{LIVE_PID}-s1.json"))
        control.flush_inbox(self.f.sessions, self.f.log, self.f.inbox,
                            _run=self.f.run)
        self.assertEqual(len(control.pending("s1", self.f.inbox)), 1)

    def test_pending_counts_group_by_session(self):
        self.f.session("a", status="busy").session("b", status="busy", pid=LIVE_PID)
        control.send("a", "1", self.f.sessions, self.f.log, self.f.inbox, _run=self.f.run)
        control.send("a", "2", self.f.sessions, self.f.log, self.f.inbox, _run=self.f.run)
        self.assertEqual(control.pending_counts(self.f.inbox).get("a"), 2)

    def test_empty_inbox_is_cheap_and_harmless(self):
        self.assertEqual(control.pending(path=self.f.inbox), [])
        self.assertEqual(control.flush_inbox(self.f.sessions, self.f.log,
                                             self.f.inbox, _run=self.f.run), [])


class TestApply(unittest.TestCase):

    def setUp(self):
        self.f = Fake()

    def tearDown(self):
        self.f.close()

    def test_unknown_verb_is_refused(self):
        r = control.apply("delete_everything", "s1")
        self.assertFalse(r["ok"])
        self.assertIn("unknown verb", r["reason"])

    def test_only_four_verbs_exist(self):
        self.assertEqual(control.VERBS, ("stop", "dispatch", "resume", "send"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
