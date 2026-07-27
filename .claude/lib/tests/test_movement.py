"""Derived project movement, and the rules that keep it honest."""

import datetime
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import movement  # noqa: E402
import projects  # noqa: E402

TODAY = datetime.date(2026, 7, 26)


def make_repo(path, commit_date="2026-07-20"):
    os.makedirs(path, exist_ok=True)
    env = dict(os.environ,
               GIT_AUTHOR_DATE=f"{commit_date}T12:00:00",
               GIT_COMMITTER_DATE=f"{commit_date}T12:00:00",
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    subprocess.run(["git", "init", "-q"], cwd=path, check=True, env=env)
    with open(os.path.join(path, "f"), "w") as fh:
        fh.write("x")
    subprocess.run(["git", "add", "f"], cwd=path, check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "c"], cwd=path, check=True, env=env)
    return path


def project(name="P", last="", repos="", linear=""):
    fields = {"last movement": last}
    if repos:
        fields["repos"] = repos
    if linear:
        fields["linear"] = linear
    return projects.Project(name, "Active", fields)


class TestGit(unittest.TestCase):

    def test_reads_last_commit_date(self):
        with tempfile.TemporaryDirectory() as d:
            r = make_repo(os.path.join(d, "repo"), "2026-07-20")
            self.assertEqual(movement.git_last_commit(r), "2026-07-20")

    def test_non_repo_is_unread_not_zero(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(movement.git_last_commit(d))

    def test_missing_path_is_unread(self):
        self.assertIsNone(movement.git_last_commit("/nope/does/not/exist"))

    def test_expands_home(self):
        self.assertIsNone(movement.git_last_commit("~/definitely-not-a-repo-xyz"))


class TestLinear(unittest.TestCase):

    ISSUES = [
        {"project": "Alpha", "updatedAt": "2026-07-10T00:00:00.000Z"},
        {"project": "Alpha", "updatedAt": "2026-07-22T00:00:00.000Z"},
        {"project": "Beta", "updatedAt": "2026-07-25T00:00:00.000Z"},
        {"project": None, "updatedAt": "2026-07-26T00:00:00.000Z"},
        {"project": "Alpha"},
    ]

    def test_takes_newest_in_the_named_project(self):
        self.assertEqual(
            movement.linear_last_update("Alpha", self.ISSUES), "2026-07-22")

    def test_ignores_other_projects(self):
        self.assertEqual(
            movement.linear_last_update("Beta", self.ISSUES), "2026-07-25")

    def test_unknown_project_is_unread(self):
        self.assertIsNone(movement.linear_last_update("Gamma", self.ISSUES))

    def test_no_project_declared_is_unread(self):
        self.assertIsNone(movement.linear_last_update("", self.ISSUES))


class TestDerive(unittest.TestCase):

    def test_picks_the_most_recent_source(self):
        with tempfile.TemporaryDirectory() as d:
            r = make_repo(os.path.join(d, "repo"), "2026-07-10")
            p = project(repos=r, linear="Alpha")
            got = movement.derive(
                p, [{"project": "Alpha", "updatedAt": "2026-07-22T00:00:00Z"}], TODAY)
            self.assertEqual(got["date"], "2026-07-22")
            self.assertEqual(got["source"], "linear:Alpha")
            self.assertEqual(got["days_stale"], 4)

    def test_records_sources_it_could_not_read(self):
        p = project(repos="/nope/x, /nope/y")
        got = movement.derive(p, [], TODAY)
        self.assertIsNone(got["date"])
        self.assertEqual([o["read"] for o in got["observations"]], [False, False])

    def test_no_declared_sources_yields_nothing(self):
        got = movement.derive(project(), [], TODAY)
        self.assertIsNone(got["date"])
        self.assertEqual(got["observations"], [])


class TestStalenessPrecedence(unittest.TestCase):
    """A silent repo is not evidence of inactivity. Projects move by phone call
    and wire transfer too, so an observation may only ever make a project look
    FRESHER than Joel declared, never staler."""

    def test_newer_observation_wins(self):
        p = project(last="2026-07-10")
        d = p.to_dict(TODAY, {"date": "2026-07-24", "source": "git:~/x",
                              "days_stale": 2})
        self.assertEqual(d["days_stale"], 2)
        self.assertFalse(d["stale"])
        self.assertEqual(d["movement_source"], "git:~/x")
        self.assertEqual(d["declared_movement"], "2026-07-10",
                         "the declared date must stay visible")

    def test_matching_observation_is_reported_as_confirmation(self):
        """A corroborated date must not read the same as an unchecked one."""
        p = project(last="2026-07-20")
        d = p.to_dict(TODAY, {"date": "2026-07-20", "source": "git:~/x",
                              "days_stale": 6})
        self.assertEqual(d["days_stale"], 6)
        self.assertEqual(d["movement_source"], "confirmed by git:~/x")

    def test_older_observation_does_not_override(self):
        p = project(last="2026-07-25")
        d = p.to_dict(TODAY, {"date": "2026-07-16", "source": "linear:X",
                              "days_stale": 10})
        self.assertEqual(d["days_stale"], 1)
        self.assertEqual(d["movement_source"], "declared")
        self.assertFalse(d["stale"])

    def test_unreadable_sources_fall_back_to_declared(self):
        p = project(last="2026-07-14")
        d = p.to_dict(TODAY, {"date": None, "source": None, "days_stale": None})
        self.assertEqual(d["days_stale"], 12)
        self.assertTrue(d["stale"])
        self.assertEqual(d["movement_source"], "declared")

    def test_observation_rescues_a_project_with_no_declared_date(self):
        p = project(last="")
        d = p.to_dict(TODAY, {"date": "2026-07-26", "source": "git:~/x",
                              "days_stale": 0})
        self.assertEqual(d["days_stale"], 0)
        self.assertFalse(d["stale"])


class TestRoundTrip(unittest.TestCase):

    def test_optional_fields_survive_a_render_parse_cycle(self):
        p = project("P", last="2026-07-01",
                    repos="~/a, ~/b", linear="Some Project")
        out = projects.render([p])
        back = projects.parse(out)[0]
        self.assertEqual(back.repos, ["~/a", "~/b"])
        self.assertEqual(back.linear, "Some Project")

    def test_entries_without_optional_fields_do_not_gain_them(self):
        p = project("P", last="2026-07-01")
        out = projects.render([p])
        self.assertNotIn("- repos:", out)
        self.assertNotIn("- linear:", out)

    def test_real_project_file_round_trips(self):
        path = os.path.join(movement.__file__.rsplit("/.claude", 1)[0],
                            "memory", "projects.md")
        if not os.path.exists(path):
            self.skipTest("projects.md not present")
        ps = projects.load(path)
        again = projects.parse(projects.render(ps))
        self.assertEqual([p.name for p in ps], [p.name for p in again])
        self.assertEqual([p.repos for p in ps], [p.repos for p in again])
        self.assertEqual([p.linear for p in ps], [p.linear for p in again])


if __name__ == "__main__":
    unittest.main(verbosity=2)
