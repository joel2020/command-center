"""Money at risk, and work that exists in only one place."""

import datetime
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import projects  # noqa: E402
import risk  # noqa: E402

TODAY = datetime.date(2026, 7, 26)


def issue(iid, title, due=None, status_type="unstarted", project="P"):
    return {"id": iid, "title": title, "dueDate": due,
            "statusType": status_type, "project": project, "status": "Todo"}


class TestParseAmounts(unittest.TestCase):

    def test_plain_and_comma_separated(self):
        self.assertEqual(risk.parse_amounts("costs $4,000 today"), [4000.0])

    def test_multiple_largest_first(self):
        self.assertEqual(
            risk.parse_amounts("$4,000 paid + $6,000 on signing"),
            [6000.0, 4000.0])

    def test_k_suffix(self):
        self.assertEqual(risk.parse_amounts("about $10k"), [10000.0])

    def test_decimals(self):
        self.assertEqual(risk.parse_amounts("$53.61/mo"), [53.61])

    def test_ignores_bare_numbers(self):
        """A bare 2000 in a title is a row count or a port, not a fee."""
        self.assertEqual(risk.parse_amounts("scale to 2000 users"), [])

    def test_no_money(self):
        self.assertEqual(risk.parse_amounts("Refactor the parser"), [])

    def test_handles_none(self):
        self.assertEqual(risk.parse_amounts(None), [])

    def test_issue_amount_sums_total_exposure(self):
        """'$4,000 paid + $6,000 on signing' is $10,000 of exposure."""
        self.assertEqual(
            risk.issue_amount(issue("A-1", "Week 1 ($4,000 paid + $6,000)")),
            10000.0)

    def test_issue_without_money_is_none(self):
        self.assertIsNone(risk.issue_amount(issue("A-2", "Fix the header")))


class TestMoneyAtRisk(unittest.TestCase):

    def test_overdue_is_counted(self):
        r = risk.money_at_risk([issue("A-1", "Milestone ($2,000)", "2026-07-15")],
                               TODAY)
        self.assertEqual(r["overdue_total"], 2000.0)
        self.assertEqual(r["overdue"][0]["days"], 11)

    def test_due_soon_is_kept_separate(self):
        """'You missed this' and 'this is coming' prompt different behaviour."""
        r = risk.money_at_risk([
            issue("A-1", "Late ($1,000)", "2026-07-20"),
            issue("A-2", "Coming ($5,000)", "2026-08-01"),
        ], TODAY)
        self.assertEqual(r["overdue_total"], 1000.0)
        self.assertEqual(r["soon_total"], 5000.0)

    def test_far_future_is_neither(self):
        r = risk.money_at_risk([issue("A-1", "Later ($9,000)", "2026-12-01")],
                               TODAY)
        self.assertEqual(r["overdue_total"], 0)
        self.assertEqual(r["soon_total"], 0)

    def test_completed_issues_are_excluded(self):
        r = risk.money_at_risk(
            [issue("A-1", "Done ($8,000)", "2026-07-01", "completed")], TODAY)
        self.assertEqual(r["overdue_total"], 0)

    def test_canceled_issues_are_excluded(self):
        r = risk.money_at_risk(
            [issue("A-1", "Dropped ($8,000)", "2026-07-01", "canceled")], TODAY)
        self.assertEqual(r["overdue_total"], 0)

    def test_issues_without_money_do_not_appear(self):
        r = risk.money_at_risk([issue("A-1", "No fee here", "2026-07-01")],
                               TODAY)
        self.assertEqual(r["overdue"], [])

    def test_issues_without_a_due_date_are_skipped(self):
        r = risk.money_at_risk([issue("A-1", "Someday ($4,000)", None)], TODAY)
        self.assertEqual(r["overdue_total"], 0)

    def test_worst_first(self):
        r = risk.money_at_risk([
            issue("A-1", "Recent ($1,000)", "2026-07-25"),
            issue("A-2", "Ancient ($1,000)", "2026-06-01"),
        ], TODAY)
        self.assertEqual(r["overdue"][0]["id"], "A-2")
        self.assertEqual(r["worst_days"], 55)

    def test_malformed_date_does_not_crash(self):
        r = risk.money_at_risk([issue("A-1", "Broken ($100)", "not-a-date")],
                               TODAY)
        self.assertEqual(r["overdue_total"], 0)


def make_repo(path, remote=False, commits=1, dirty=False):
    os.makedirs(path, exist_ok=True)
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    subprocess.run(["git", "init", "-q"], cwd=path, check=True, env=env)
    for i in range(commits):
        with open(os.path.join(path, f"f{i}"), "w") as f:
            f.write("x")
        subprocess.run(["git", "add", "-A"], cwd=path, check=True, env=env)
        subprocess.run(["git", "commit", "-qm", f"c{i}"], cwd=path, check=True,
                       env=env)
    if remote:
        subprocess.run(["git", "remote", "add", "origin", "/tmp/nowhere.git"],
                       cwd=path, check=True, env=env)
    if dirty:
        with open(os.path.join(path, "dirty.txt"), "w") as f:
            f.write("uncommitted")
    return path


class TestBackupExposure(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.d.cleanup()

    def p(self, name):
        return os.path.join(self.d.name, name)

    def test_no_remote_is_the_worst_severity(self):
        """No remote means no second copy at all — disk failure is total."""
        make_repo(self.p("solo"), remote=False, commits=3)
        r = risk.backup_exposure([self.p("solo")])
        self.assertEqual(r["repos"][0]["severity"], "no-remote")
        self.assertEqual(r["repos"][0]["unbacked_commits"], 3,
                         "with no remote the entire history is unbacked")
        self.assertFalse(r["clean"])

    def test_repo_with_remote_and_nothing_ahead_is_ok(self):
        make_repo(self.p("safe"), remote=True)
        r = risk.backup_exposure([self.p("safe")])
        self.assertEqual(r["repos"][0]["severity"], "ok")
        self.assertTrue(r["clean"])

    def test_dirty_tree_is_flagged_but_not_at_risk(self):
        """Uncommitted work is worth noticing; it is not a backup failure."""
        make_repo(self.p("wip"), remote=True, dirty=True)
        r = risk.backup_exposure([self.p("wip")])
        self.assertEqual(r["repos"][0]["severity"], "dirty")
        self.assertEqual(r["at_risk"], [])
        self.assertEqual(len(r["dirty"]), 1)

    def test_non_repo_is_unreadable_not_a_failure(self):
        os.makedirs(self.p("plain"))
        r = risk.backup_exposure([self.p("plain")])
        self.assertEqual(r["repos"], [])
        self.assertEqual(len(r["unreadable"]), 1)

    def test_missing_path_is_unreadable(self):
        r = risk.backup_exposure([self.p("nope")])
        self.assertEqual(len(r["unreadable"]), 1)
        self.assertTrue(r["clean"], "a path we cannot read is not a known risk")

    def test_worst_sorts_first(self):
        make_repo(self.p("safe"), remote=True)
        make_repo(self.p("solo"), remote=False)
        r = risk.backup_exposure([self.p("safe"), self.p("solo")])
        self.assertEqual(r["repos"][0]["name"], "solo")


class TestProjectPaths(unittest.TestCase):

    def test_collects_and_dedupes(self):
        ps = [projects.Project("A", "Active", {"repos": "~/x, ~/y"}),
              projects.Project("B", "Active", {"repos": "~/y, ~/z"})]
        self.assertEqual(risk.project_paths(ps), ["~/x", "~/y", "~/z"])

    def test_projects_without_repos_contribute_nothing(self):
        ps = [projects.Project("A", "Active", {})]
        self.assertEqual(risk.project_paths(ps), [])


class TestHeadline(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.d.cleanup()

    def test_silent_when_nothing_is_wrong(self):
        make_repo(os.path.join(self.d.name, "safe"), remote=True)
        s = risk.summary([], [projects.Project(
            "A", "Active", {"repos": os.path.join(self.d.name, "safe")})], TODAY)
        self.assertIsNone(s["headline"], "no news is not a headline")

    def test_reports_money_and_backup_together(self):
        make_repo(os.path.join(self.d.name, "solo"), remote=False)
        s = risk.summary(
            [issue("A-1", "Late ($3,000)", "2026-07-01")],
            [projects.Project("A", "Active",
                              {"repos": os.path.join(self.d.name, "solo")})],
            TODAY)
        self.assertIn("$3,000 overdue", s["headline"])
        self.assertIn("1 repo with no remote", s["headline"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
