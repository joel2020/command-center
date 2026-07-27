"""Off-disk backup for repos that exist in only one place.

The thing being defended against is a file that LOOKS like a backup and is not.
A corrupt bundle reported as success is worse than a loud failure, because it
converts a known risk into an unknown one.
"""

import datetime
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backup  # noqa: E402

NOW = datetime.datetime(2026, 7, 26, 12, 0)


def make_repo(path, commits=2, remote=False):
    os.makedirs(path, exist_ok=True)
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    subprocess.run(["git", "init", "-q"], cwd=path, check=True, env=env)
    for i in range(commits):
        with open(os.path.join(path, f"f{i}.txt"), "w") as f:
            f.write(f"content {i}")
        subprocess.run(["git", "add", "-A"], cwd=path, check=True, env=env)
        subprocess.run(["git", "commit", "-qm", f"c{i}"], cwd=path, check=True,
                       env=env)
    if remote:
        subprocess.run(["git", "remote", "add", "origin", "/tmp/nowhere.git"],
                       cwd=path, check=True, env=env)
    return path


class TestRepoState(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.d.cleanup()

    def test_detects_no_remote(self):
        p = make_repo(os.path.join(self.d.name, "solo"))
        s = backup.repo_state(p)
        self.assertTrue(s["is_repo"])
        self.assertFalse(s["has_remote"])
        self.assertEqual(s["commits"], 2)

    def test_detects_a_remote(self):
        p = make_repo(os.path.join(self.d.name, "safe"), remote=True)
        self.assertTrue(backup.repo_state(p)["has_remote"])

    def test_non_repo_is_reported_not_crashed(self):
        os.makedirs(os.path.join(self.d.name, "plain"))
        self.assertFalse(backup.repo_state(os.path.join(self.d.name, "plain"))["is_repo"])

    def test_missing_path_is_reported(self):
        self.assertFalse(backup.repo_state("/nope/nothing")["is_repo"])


class TestBundle(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.dest = os.path.join(self.d.name, "dest")

    def tearDown(self):
        self.d.cleanup()

    def test_bundle_is_created_and_verified(self):
        p = make_repo(os.path.join(self.d.name, "repo"), commits=3)
        r = backup.bundle(p, self.dest, NOW)
        self.assertTrue(r["ok"], r.get("reason"))
        self.assertTrue(r["verified"])
        self.assertTrue(os.path.exists(r["bundle"]))

    def test_bundle_actually_restores_to_the_same_head(self):
        """Verification is not restoration. This proves the real thing."""
        p = make_repo(os.path.join(self.d.name, "repo"), commits=3)
        head = subprocess.run(["git", "-C", p, "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
        r = backup.bundle(p, self.dest, NOW)
        out = os.path.join(self.d.name, "restored")
        subprocess.run(["git", "clone", "-q", r["bundle"], out], check=True)
        restored = subprocess.run(["git", "-C", out, "rev-parse", "HEAD"],
                                  capture_output=True, text=True).stdout.strip()
        self.assertEqual(head, restored)
        self.assertTrue(os.path.exists(os.path.join(out, "f2.txt")))

    def test_a_repo_with_no_commits_is_skipped_not_failed_silently(self):
        p = os.path.join(self.d.name, "empty")
        os.makedirs(p)
        subprocess.run(["git", "init", "-q"], cwd=p, check=True)
        r = backup.bundle(p, self.dest, NOW)
        self.assertFalse(r["ok"])
        self.assertIn("no commits", r["reason"])

    def test_non_repo_does_not_raise(self):
        os.makedirs(os.path.join(self.d.name, "plain"))
        r = backup.bundle(os.path.join(self.d.name, "plain"), self.dest, NOW)
        self.assertFalse(r["ok"])

    def test_all_branches_are_captured_not_just_head(self):
        p = make_repo(os.path.join(self.d.name, "repo"))
        subprocess.run(["git", "-C", p, "branch", "sidebranch"], check=True)
        r = backup.bundle(p, self.dest, NOW)
        listing = subprocess.run(["git", "bundle", "list-heads", r["bundle"]],
                                 capture_output=True, text=True).stdout
        self.assertIn("sidebranch", listing,
                      "a bundle that drops branches loses work")


class TestPrune(unittest.TestCase):

    def test_keeps_the_newest_and_removes_the_rest(self):
        with tempfile.TemporaryDirectory() as d:
            for i in range(8):
                open(os.path.join(d, f"repo-2026-07-{i+10:02d}-1200.bundle"), "w").close()
            removed = backup.prune("repo", d, keep=3)
            left = [f for f in os.listdir(d) if f.endswith(".bundle")]
            self.assertEqual(len(left), 3)
            self.assertEqual(len(removed), 5)

    def test_does_not_touch_other_repos_bundles(self):
        with tempfile.TemporaryDirectory() as d:
            for i in range(5):
                open(os.path.join(d, f"alpha-2026-07-{i+10:02d}-1200.bundle"), "w").close()
            open(os.path.join(d, "beta-2026-07-01-1200.bundle"), "w").close()
            backup.prune("alpha", d, keep=2)
            self.assertTrue(os.path.exists(os.path.join(d, "beta-2026-07-01-1200.bundle")))

    def test_prune_on_a_missing_directory_is_harmless(self):
        self.assertEqual(backup.prune("x", "/nope/nothing"), [])


class TestRun(unittest.TestCase):

    def test_reports_which_repos_still_lack_a_remote(self):
        with tempfile.TemporaryDirectory() as d:
            solo = make_repo(os.path.join(d, "solo"))
            safe = make_repo(os.path.join(d, "safe"), remote=True)
            res = backup.run([solo, safe], os.path.join(d, "dest"), NOW)
            self.assertEqual(res["backed_up"], 2)
            self.assertEqual(res["still_without_remote"], ["solo"],
                             "a bundle is insurance, not a substitute for a remote")

    def test_one_bad_repo_does_not_stop_the_others(self):
        with tempfile.TemporaryDirectory() as d:
            good = make_repo(os.path.join(d, "good"))
            res = backup.run([good, "/nope/missing"], os.path.join(d, "dest"), NOW)
            self.assertEqual(res["backed_up"], 1)
            self.assertEqual(len(res["failed"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
