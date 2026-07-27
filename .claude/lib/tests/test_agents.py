"""The live roster: who is working, on what, for which project."""

import datetime
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents  # noqa: E402
import projects  # noqa: E402

NOW = datetime.datetime(2026, 7, 26, 20, 0).astimezone()
LIVE_PID = os.getpid()          # certainly alive
DEAD_PID = 999999               # certainly not


def ms(dt_offset_s):
    return int((NOW.timestamp() + dt_offset_s) * 1000)


class Tree:
    """A throwaway ~/.claude for one test."""

    def __init__(self):
        self.d = tempfile.TemporaryDirectory()
        self.sessions = os.path.join(self.d.name, "sessions")
        self.tasks = os.path.join(self.d.name, "tasks")
        self.transcripts = os.path.join(self.d.name, "projects")
        for p in (self.sessions, self.tasks, self.transcripts):
            os.makedirs(p)

    def session(self, pid, sid, cwd="/tmp/x", name=None, status=None,
                started=-600, updated=0, broken=False):
        p = os.path.join(self.sessions, f"{pid}.json")
        with open(p, "w") as f:
            if broken:
                f.write("{not json")
                return self
            d = {"pid": pid, "sessionId": sid, "cwd": cwd,
                 "startedAt": ms(started), "updatedAt": ms(updated),
                 "kind": "interactive"}
            if name:
                d["name"] = name
            if status:
                d["status"] = status
            json.dump(d, f)
        return self

    def task(self, sid, tid, subject, status="pending", blocked_by=()):
        d = os.path.join(self.tasks, sid)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{tid}.json"), "w") as f:
            json.dump({"id": tid, "subject": subject, "status": status,
                       "blockedBy": list(blocked_by), "blocks": []}, f)
        return self

    def transcript(self, sid, cwd, records, pad=0):
        d = os.path.join(self.transcripts, agents._slug(cwd))
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{sid}.jsonl"), "w") as f:
            if pad:
                filler = json.dumps({"type": "user", "message":
                                     {"content": "x" * 200}})
                for _ in range(pad):
                    f.write(filler + "\n")
            for r in records:
                f.write(json.dumps(r) + "\n")
        return self

    def close(self):
        self.d.cleanup()


def tool_rec(name, inp, ts="2026-07-26T20:00:00Z"):
    return {"type": "assistant", "timestamp": ts,
            "message": {"content": [{"type": "tool_use", "name": name,
                                     "input": inp}]}}


class TestRoster(unittest.TestCase):

    def setUp(self):
        self.t = Tree()

    def tearDown(self):
        self.t.close()

    def test_lists_a_live_session(self):
        self.t.session(LIVE_PID, "s1", name="worker", status="busy")
        r = agents.roster(self.t.sessions, NOW)
        self.assertTrue(r["available"])
        self.assertEqual(len(r["items"]), 1)
        self.assertEqual(r["items"][0]["name"], "worker")
        self.assertEqual(r["items"][0]["status"], "busy")

    def test_drops_dead_processes(self):
        """A dead agent shown as idle implies parked work. It is abandoned."""
        self.t.session(LIVE_PID, "alive").session(DEAD_PID, "dead")
        r = agents.roster(self.t.sessions, NOW)
        self.assertEqual([a["session_id"] for a in r["items"]], ["alive"])

    def test_missing_status_means_idle_not_unknown(self):
        self.t.session(LIVE_PID, "s1")
        r = agents.roster(self.t.sessions, NOW)
        self.assertEqual(r["items"][0]["status"], "idle")

    def test_unreadable_directory_is_not_an_empty_roster(self):
        """The rule this whole codebase runs on."""
        r = agents.roster("/nope/not/here", NOW)
        self.assertFalse(r["available"])
        self.assertIn("does not exist", r["reason"])
        self.assertEqual(r["items"], [])

    def test_empty_directory_is_available_and_empty(self):
        r = agents.roster(self.t.sessions, NOW)
        self.assertTrue(r["available"], "nobody working is a real answer")
        self.assertEqual(r["items"], [])

    def test_malformed_session_file_is_counted_not_fatal(self):
        self.t.session(LIVE_PID, "good").session(12345, "x", broken=True)
        r = agents.roster(self.t.sessions, NOW)
        self.assertEqual(len(r["items"]), 1)
        self.assertEqual(r["unreadable"], 1)

    def test_stale_file_from_a_recycled_pid_is_dropped(self):
        self.t.session(LIVE_PID, "ancient", updated=-(agents.STALE_AFTER_S + 60))
        r = agents.roster(self.t.sessions, NOW)
        self.assertEqual(r["items"], [])

    def test_busy_sorts_before_idle(self):
        self.t.session(LIVE_PID, "idle1", name="i")
        # A second live entry: reuse our own pid, different file.
        p = os.path.join(self.t.sessions, "222.json")
        with open(p, "w") as f:
            json.dump({"pid": LIVE_PID, "sessionId": "busy1", "cwd": "/tmp",
                       "name": "b", "status": "busy",
                       "startedAt": ms(-100), "updatedAt": ms(0)}, f)
        r = agents.roster(self.t.sessions, NOW)
        self.assertEqual(r["items"][0]["session_id"], "busy1")

    def test_age_is_humanized(self):
        self.t.session(LIVE_PID, "s1", started=-7200)
        r = agents.roster(self.t.sessions, NOW)
        self.assertEqual(r["items"][0]["age_human"], "2h")


class TestTasks(unittest.TestCase):

    def setUp(self):
        self.t = Tree()

    def tearDown(self):
        self.t.close()

    def test_splits_done_doing_and_next(self):
        (self.t.task("s1", 1, "first", "completed")
               .task("s1", 2, "second", "in_progress")
               .task("s1", 3, "third", "pending"))
        r = agents.tasks_for("s1", self.t.tasks)
        self.assertEqual(r["done"], ["first"])
        self.assertEqual(r["doing"], ["second"])
        self.assertEqual(r["next"], "third")
        self.assertEqual(r["pending"], 1)

    def test_next_skips_a_blocked_task(self):
        """A blocked task shown as 'next' is how a plan looks fine while
        nothing can actually move."""
        (self.t.task("s1", 1, "blocker", "pending")
               .task("s1", 2, "blocked", "pending", blocked_by=[1])
               .task("s1", 3, "free", "pending"))
        r = agents.tasks_for("s1", self.t.tasks)
        self.assertEqual(r["next"], "blocker")

    def test_next_is_none_when_everything_is_blocked(self):
        (self.t.task("s1", 1, "a", "pending", blocked_by=[9])
               .task("s1", 2, "b", "pending", blocked_by=[9]))
        r = agents.tasks_for("s1", self.t.tasks)
        self.assertIsNone(r["next"])
        self.assertEqual(r["pending"], 2)

    def test_unblocked_once_the_blocker_completes(self):
        (self.t.task("s1", 1, "blocker", "completed")
               .task("s1", 2, "now free", "pending", blocked_by=[1]))
        r = agents.tasks_for("s1", self.t.tasks)
        self.assertEqual(r["next"], "now free")

    def test_no_task_directory_is_reported(self):
        r = agents.tasks_for("nobody", self.t.tasks)
        self.assertFalse(r["available"])
        self.assertIsNone(r["next"])


class TestLastAction(unittest.TestCase):

    def setUp(self):
        self.t = Tree()

    def tearDown(self):
        self.t.close()

    def test_reads_the_most_recent_tool_call(self):
        self.t.transcript("s1", "/tmp/x", [
            tool_rec("Read", {"file_path": "/a"}),
            tool_rec("Bash", {"command": "git status"}),
        ])
        r = agents.last_action("s1", "/tmp/x", self.t.transcripts)
        self.assertEqual(r["tool"], "Bash")
        self.assertEqual(r["summary"], "git status")

    def test_only_reads_the_tail_of_a_large_transcript(self):
        """Transcripts reach 10MB and this is polled every 2s."""
        self.t.transcript("s1", "/tmp/x",
                          [tool_rec("Bash", {"command": "the last one"})],
                          pad=4000)
        path = os.path.join(self.t.transcripts, agents._slug("/tmp/x"),
                            "s1.jsonl")
        self.assertGreater(os.path.getsize(path), agents.TAIL_BYTES)
        r = agents.last_action("s1", "/tmp/x", self.t.transcripts)
        self.assertEqual(r["summary"], "the last one")

    def test_missing_transcript_is_unavailable_not_idle(self):
        r = agents.last_action("nope", "/tmp/x", self.t.transcripts)
        self.assertFalse(r["available"])

    def test_transcript_with_no_tool_calls(self):
        self.t.transcript("s1", "/tmp/x",
                          [{"type": "user", "message": {"content": "hi"}}])
        r = agents.last_action("s1", "/tmp/x", self.t.transcripts)
        self.assertTrue(r["available"], "read fine, there was just no tool call")
        self.assertIsNone(r["tool"])

    def test_malformed_lines_are_skipped(self):
        d = os.path.join(self.t.transcripts, agents._slug("/tmp/x"))
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "s1.jsonl"), "w") as f:
            f.write("garbage\n")
            f.write(json.dumps(tool_rec("Edit", {"file_path": "/z"})) + "\n")
        r = agents.last_action("s1", "/tmp/x", self.t.transcripts)
        self.assertEqual(r["tool"], "Edit")

    def test_summary_collapses_whitespace_and_truncates(self):
        self.t.transcript("s1", "/tmp/x",
                          [tool_rec("Bash", {"command": "a\n\n   b" + "c" * 200})])
        r = agents.last_action("s1", "/tmp/x", self.t.transcripts)
        self.assertNotIn("\n", r["summary"])
        self.assertLessEqual(len(r["summary"]), 80)


def project(name, repos):
    return projects.Project(name, "Active", {"repos": repos})


class TestProjectJoin(unittest.TestCase):
    """The join that makes this a cockpit instead of a process list."""

    def test_matches_an_agent_to_its_project(self):
        with tempfile.TemporaryDirectory() as d:
            repo = os.path.join(d, "alivio-platform")
            os.makedirs(repo)
            a = [{"cwd": repo}]
            agents.join_projects(a, [project("Alivio", repo)])
            self.assertEqual(a[0]["project"], "Alivio")

    def test_matches_a_subdirectory_of_the_repo(self):
        with tempfile.TemporaryDirectory() as d:
            repo = os.path.join(d, "clara")
            sub = os.path.join(repo, "src", "deep")
            os.makedirs(sub)
            a = [{"cwd": sub}]
            agents.join_projects(a, [project("Clara", repo)])
            self.assertEqual(a[0]["project"], "Clara")

    def test_longest_path_wins(self):
        """~ must not swallow an agent that is clearly inside one project."""
        with tempfile.TemporaryDirectory() as d:
            inner = os.path.join(d, "alivio-platform")
            os.makedirs(inner)
            a = [{"cwd": inner}]
            agents.join_projects(a, [project("Everything", d),
                                     project("Alivio", inner)])
            self.assertEqual(a[0]["project"], "Alivio")

    def test_no_match_is_none_not_a_guess(self):
        with tempfile.TemporaryDirectory() as d:
            a = [{"cwd": d}]
            agents.join_projects(a, [project("Other", "/somewhere/else")])
            self.assertIsNone(a[0]["project"])

    def test_a_sibling_directory_does_not_match_by_prefix(self):
        """~/clara must not claim ~/clara-agency."""
        with tempfile.TemporaryDirectory() as d:
            clara = os.path.join(d, "clara")
            agency = os.path.join(d, "clara-agency")
            os.makedirs(clara)
            os.makedirs(agency)
            a = [{"cwd": agency}]
            agents.join_projects(a, [project("Clara", clara)])
            self.assertIsNone(a[0]["project"],
                              "prefix match must respect path boundaries")

    def test_empty_cwd_is_none(self):
        a = [{"cwd": ""}]
        agents.join_projects(a, [project("X", "/tmp")])
        self.assertIsNone(a[0]["project"])


class TestSnapshot(unittest.TestCase):

    def setUp(self):
        self.t = Tree()

    def tearDown(self):
        self.t.close()

    def test_assembles_everything(self):
        self.t.session(LIVE_PID, "s1", cwd="/tmp/x", name="w", status="busy")
        self.t.task("s1", 1, "done it", "completed")
        self.t.task("s1", 2, "do this", "pending")
        self.t.transcript("s1", "/tmp/x", [tool_rec("Bash", {"command": "ls"})])
        snap = agents.snapshot([], self.t.sessions, self.t.tasks,
                               self.t.transcripts, NOW)
        self.assertTrue(snap["available"])
        self.assertEqual(snap["busy"], 1)
        a = snap["items"][0]
        self.assertEqual(a["tasks"]["next"], "do this")
        self.assertEqual(a["last_action"]["tool"], "Bash")

    def test_unavailable_roster_propagates(self):
        snap = agents.snapshot([], "/nope", self.t.tasks, self.t.transcripts, NOW)
        self.assertFalse(snap["available"])
        self.assertEqual(snap["items"], [])

    def test_groups_by_project(self):
        self.t.session(LIVE_PID, "s1", cwd="/tmp/x")
        snap = agents.snapshot([], self.t.sessions, self.t.tasks,
                               self.t.transcripts, NOW)
        self.assertIn("(unassigned)", snap["by_project"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
